import os
import zipfile
import tempfile
import shutil
import fitz
from datetime import datetime

from src.celery_app import celery_app
from src.database import mongodb as db
from src.services.pipeline_orchestrator import _worker_process_document

@celery_app.task(bind=True)
def process_zip_batch(self, batch_id: str, zip_path: str, schema_id: str, client_id: str):
    """
    Tarea de Celery para procesar un archivo ZIP en segundo plano.
    """
    try:
        db.update_batch_status(batch_id, "processing")
        schema_def = db.get_schema_by_id(schema_id)
        if not schema_def:
            raise ValueError(f"Schema {schema_id} not found")

        temp_dir = tempfile.mkdtemp()
        try:
            # Descomprimir
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Recopilar tareas
            tasks = []
            opened_docs = []
            
            for root, _, files in os.walk(temp_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    ext = os.path.splitext(file_name)[1].lower()
                    
                    if ext == '.pdf':
                        doc = fitz.open(file_path)
                        opened_docs.append(doc)
                        num_pages = len(doc)
                        for page_num in range(num_pages):
                            tasks.append({
                                'temp_path': file_path,
                                'file_name': file_name,
                                'page_num': page_num,
                                'num_pages': num_pages,
                                'pdf_doc': doc,
                                'schema_def': schema_def,
                                'schema_id': schema_id,
                                'client_id': client_id,
                                'batch_id': batch_id
                            })
                    elif ext in ['.png', '.jpg', '.jpeg']:
                        tasks.append({
                            'temp_path': file_path,
                            'file_name': file_name,
                            'page_num': None,
                            'pdf_doc': None,
                            'schema_def': schema_def,
                            'schema_id': schema_id,
                            'client_id': client_id,
                            'batch_id': batch_id
                        })
            
            # Procesar secuencialmente en el worker o usando ThreadPoolExecutor
            # Para simplificar en Celery (que ya es concurrente), procesamos en un hilo o con ThreadPool
            import concurrent.futures
            completed = 0
            total = len(tasks)
            
            client_data = db.get_client_by_id(client_id)
            if not client_data or not client_data.get("is_active", True):
                raise ValueError("Empresa inactiva. No se pueden procesar documentos.")
                
            limit = client_data.get("monthly_doc_limit", 1000)
            usage = client_data.get("current_month_usage", 0)
            if usage + total > limit:
                raise ValueError(f"Límite mensual excedido. Intenta procesar {total} docs pero solo quedan {limit - usage} disponibles.")
            
            if total > 0:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {executor.submit(_worker_process_document, task): task for task in tasks}
                    for future in concurrent.futures.as_completed(futures):
                        success, data, name = future.result()
                        if success:
                            completed += 1
                            db.increment_client_usage(client_id, 1)
                        
                        db.update_batch_status(batch_id, "processing", {"progress": f"{completed}/{total}"})

            # Cerrar docs
            for doc in opened_docs:
                try: doc.close()
                except: pass

            db.update_batch_status(batch_id, "completed", {"completed_at": datetime.utcnow()})

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            # Borrar el ZIP temporal para ahorrar espacio
            if os.path.exists(zip_path):
                os.remove(zip_path)
                
    except Exception as e:
        db.update_batch_status(batch_id, "failed", {"error": str(e), "completed_at": datetime.utcnow()})
        raise e
