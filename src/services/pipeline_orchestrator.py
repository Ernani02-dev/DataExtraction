import os
import gc
import tempfile
import concurrent.futures
from datetime import datetime
from PIL import Image
import fitz

from src.database import mongodb as db
from src.services.document_parser import pdf_to_image, image_to_base64
from src.services.ai_extractor import process_single_invoice

def _worker_process_document(task_info):
    """Procesa un solo documento (o página) de forma independiente."""
    temp_path = task_info['temp_path']
    file_name = task_info['file_name']
    page_num = task_info.get('page_num')
    schema_def = task_info['schema_def']
    selected_schema_id = task_info['schema_id']
    pdf_doc = task_info.get('pdf_doc')
    
    try:
        if page_num is not None:
            # Es un PDF, le pasamos el documento ya abierto para no re-abrirlo
            img = pdf_to_image(pdf_doc if pdf_doc else temp_path, is_bytes=False, page_num=page_num)
            img_b64 = image_to_base64(img)
            del img
            
            nombre_mostrar = f"{file_name} (Pág. {page_num+1})" if task_info.get('num_pages', 1) > 1 else file_name
            data_dict = process_single_invoice(img_b64, nombre_mostrar, "compra", schema_def)
            del img_b64
        else:
            # Es una imagen
            img = Image.open(temp_path).convert("RGB")
            img_b64 = image_to_base64(img)
            del img
            
            nombre_mostrar = file_name
            data_dict = process_single_invoice(img_b64, nombre_mostrar, "compra", schema_def)
            del img_b64
            
        # Guardar en base de datos
        record = {
            "schema_id": selected_schema_id,
            "client_id": task_info.get('client_id'),
            "batch_id": task_info.get('batch_id'),
            "filename": nombre_mostrar,
            "extracted_data": data_dict,
            "created_at": datetime.utcnow()
        }
        db.save_extracted_record(record)
        
        flat_record = data_dict.copy()
        flat_record["_filename"] = nombre_mostrar
        return True, flat_record, nombre_mostrar
        
    except Exception as e:
        return False, str(e), file_name

def process_uploaded_files(uploaded_files, schema_def, selected_schema_id, selected_client_id, progress_callback=None, log_callback=None):
    """
    Orquesta el pipeline completo de procesamiento: 
    Escritura temporal, parseo de hojas, concurrencia, extracción y limpieza.
    """
    results = []
    tasks = []
    temp_dir = tempfile.mkdtemp()
    
    try:
        if log_callback: log_callback("Preparando archivos...")
        
        opened_docs = [] # Para mantener los fitz.Document abiertos y cerrarlos al final
        
        for u_file in uploaded_files:
            temp_path = os.path.join(temp_dir, u_file.name)
            with open(temp_path, "wb") as f:
                f.write(u_file.getvalue())
                
            ext = os.path.splitext(u_file.name)[1].lower()
            if ext == '.pdf':
                doc = fitz.open(temp_path)
                opened_docs.append(doc)
                num_pages = len(doc)
                
                for page_num in range(num_pages):
                    tasks.append({
                        'temp_path': temp_path,
                        'file_name': u_file.name,
                        'page_num': page_num,
                        'num_pages': num_pages,
                        'pdf_doc': doc, # Pasamos el doc abierto!
                        'schema_def': schema_def,
                        'schema_id': selected_schema_id,
                        'client_id': selected_client_id
                    })
            else:
                tasks.append({
                    'temp_path': temp_path,
                    'file_name': u_file.name,
                    'page_num': None,
                    'pdf_doc': None,
                    'schema_def': schema_def,
                    'schema_id': selected_schema_id,
                    'client_id': selected_client_id
                })
                
        total_tasks = len(tasks)
        completed_tasks = 0
        
        client_data = db.get_client_by_id(selected_client_id)
        if not client_data or not client_data.get("is_active", True):
            if log_callback: log_callback("Error: Empresa inactiva.", is_error=True)
            return []
            
        limit = client_data.get("monthly_doc_limit", 1000)
        usage = client_data.get("current_month_usage", 0)
        if usage + total_tasks > limit:
            if log_callback: log_callback(f"Error: Límite mensual excedido. Quedan {limit - usage} docs.", is_error=True)
            return []
        
        if total_tasks > 0:
            if log_callback: log_callback(f"Procesando {total_tasks} elementos con IA (en paralelo)...")
            
            MAX_WORKERS = min(10, total_tasks)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_task = {executor.submit(_worker_process_document, task): task for task in tasks}
                
                for future in concurrent.futures.as_completed(future_to_task):
                    success, data, name_info = future.result()
                    
                    if success:
                        results.append(data)
                        db.increment_client_usage(selected_client_id, 1)
                    else:
                        if log_callback: log_callback(f"Error procesando {name_info}: {data}", is_error=True)
                    
                    completed_tasks += 1
                    if progress_callback: progress_callback(completed_tasks, total_tasks)
                    if log_callback: log_callback(f"Completado {completed_tasks}/{total_tasks}...")
                    
        # Cerrar los PDFs abiertos
        for doc in opened_docs:
            try:
                doc.close()
            except:
                pass
                
        if log_callback: log_callback("¡Procesamiento finalizado!")
        
    finally:
        # Limpieza robusta del directorio temporal
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
            
    return results
