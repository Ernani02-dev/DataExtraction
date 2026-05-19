import streamlit as st
import pandas as pd
import io
import os
from PIL import Image

# Importar funciones de main.py
from main import pdf_to_image, image_to_base64, process_single_invoice

st.set_page_config(page_title="Procesador de Facturas", page_icon="📄", layout="wide")

st.title("📄 Automatización de Extracción de Facturas")
st.write("Sube tus facturas (PDF, PNG, JPG) y extrae automáticamente los datos en formato Excel utilizando la IA de Gemini.")

st.markdown("### Configuración")
tipo_factura_ui = st.radio("Selecciona el tipo de facturas que vas a procesar:", ["Compras (Recibidas)", "Ventas (Emitidas)"], horizontal=True)
tipo_factura_str = "compra" if "Compras" in tipo_factura_ui else "venta"

uploaded_files = st.file_uploader(
    "Arrastra y suelta tus facturas aquí", 
    type=["pdf", "png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("Procesar Facturas", type="primary"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Procesando: {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            try:
                # Determinar extensión
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                
                # Leer bytes del archivo subido
                file_bytes = uploaded_file.read()
                
                # Convertir a imagen y extraer según el tipo de archivo
                if file_ext == '.pdf':
                    import fitz  # PyMuPDF
                    # Abrir el PDF desde los bytes en memoria para contar páginas
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    num_pages = len(doc)
                    
                    for page_num in range(num_pages):
                        status_text.text(f"Procesando: {uploaded_file.name} (Pág. {page_num+1}/{num_pages})")
                        
                        # Convertir la página actual a imagen PIL
                        img = pdf_to_image(file_bytes, is_bytes=True, page_num=page_num)
                        img_b64 = image_to_base64(img)
                        
                        # Nombre para identificar el origen y la página
                        nombre_mostrar = f"{uploaded_file.name} (Pág. {page_num+1})" if num_pages > 1 else uploaded_file.name
                        
                        # Extraer datos con Gemini
                        data_dict = process_single_invoice(img_b64, nombre_mostrar, tipo_factura_str)
                        
                        # Filtrar páginas que no contienen facturas (nro_factura y monto_total nulos)
                        if data_dict.get('nro_factura') is None and data_dict.get('monto_total') is None:
                            continue
                            
                        results.append(data_dict)
                    doc.close()
                else:
                    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
                    img_b64 = image_to_base64(img)
                    data_dict = process_single_invoice(img_b64, uploaded_file.name, tipo_factura_str)
                    results.append(data_dict)
                
            except Exception as e:
                st.error(f"Error procesando {uploaded_file.name}: {str(e)}")
                
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.text("¡Procesamiento finalizado!")
        
        if results:
            st.success(f"Se procesaron {len(results)} facturas con éxito.")
            df_new = pd.DataFrame(results)
            
            # Reordenar columnas para mejor lectura
            ruc_col = 'ruc_cliente' if tipo_factura_str == 'venta' else 'ruc_vendedor'
            cols_order = ['archivo_origen', 'nro_factura', ruc_col, 'fecha', 'timbrado', 
                          'monto_total', 'gravado_10', 'gravado_5', 'exenta', 'suma_validada']
            
            # Asegurar que todas las columnas existan
            for c in cols_order:
                if c not in df_new.columns:
                    df_new[c] = None
            df_new = df_new[cols_order]
            
            # Mostrar tabla interactiva
            st.dataframe(df_new, use_container_width=True)
            
            # Preparar archivo Excel para descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_new.to_excel(writer, index=False)
            
            excel_data = output.getvalue()
            
            nombre_excel = f"facturas_procesadas_{tipo_factura_str}s_web.xlsx"
            
            st.download_button(
                label="📥 Descargar Excel",
                data=excel_data,
                file_name=nombre_excel,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
