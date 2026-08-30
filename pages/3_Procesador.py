import streamlit as st
import pandas as pd
import os
import gc
from datetime import datetime
from PIL import Image

import database as db
import export_engine
from main import pdf_to_image, image_to_base64, process_single_invoice

st.set_page_config(page_title="Procesador IA", page_icon="🚀", layout="wide")
st.title("🚀 Procesador de Documentos")
st.write("Sube tus documentos y deja que la IA extraiga los datos basándose en el esquema seleccionado.")

# Cargar configuración desde DB
schemas = db.get_all_schemas()
profiles = db.get_all_profiles()

if not schemas or not profiles:
    st.warning("⚠️ Debes configurar al menos un Esquema y un Perfil de Exportación antes de procesar archivos.")
    st.stop()

schema_opts = {str(s["_id"]): s for s in schemas}
profile_opts = {str(p["_id"]): p for p in profiles}

col1, col2 = st.columns(2)
with col1:
    selected_schema_id = st.selectbox("1. Tipo de Documento (Esquema):", options=list(schema_opts.keys()), format_func=lambda x: schema_opts[x]["name"])
with col2:
    # Filtrar perfiles por esquema
    valid_profiles = [p for p in profiles if str(p.get("schema_id")) == selected_schema_id]
    if not valid_profiles:
        st.warning("No hay perfiles de exportación compatibles con este esquema.")
        selected_profile_id = None
    else:
        profile_opts_filtered = {str(p["_id"]): p for p in valid_profiles}
        selected_profile_id = st.selectbox("2. Perfil de Exportación (Excel):", options=list(profile_opts_filtered.keys()), format_func=lambda x: profile_opts_filtered[x]["name"])

uploaded_files = st.file_uploader("3. Sube tus facturas (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

if "results" not in st.session_state:
    st.session_state["results"] = []

if uploaded_files and selected_profile_id:
    if st.button("Procesar Archivos con IA", type="primary", use_container_width=True):
        schema_def = schema_opts[selected_schema_id]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        
        if not os.path.exists("tmp"):
            os.makedirs("tmp")
            
        for i, u_file in enumerate(uploaded_files):
            status_text.text(f"Procesando: {u_file.name} ({i+1}/{len(uploaded_files)})")
            
            # Estrategia de Memoria: Guardar en disco temporalmente
            temp_path = os.path.join("tmp", u_file.name)
            with open(temp_path, "wb") as f:
                f.write(u_file.getbuffer())
                
            try:
                ext = os.path.splitext(u_file.name)[1].lower()
                
                if ext == '.pdf':
                    import fitz
                    doc = fitz.open(temp_path)
                    num_pages = len(doc)
                    doc.close()
                    
                    for page_num in range(num_pages):
                        status_text.text(f"Procesando: {u_file.name} (Pág. {page_num+1}/{num_pages})")
                        
                        img = pdf_to_image(temp_path, is_bytes=False, page_num=page_num)
                        img_b64 = image_to_base64(img)
                        
                        # Limpiar imagen pesada de memoria
                        del img
                        gc.collect()
                        
                        nombre_mostrar = f"{u_file.name} (Pág. {page_num+1})" if num_pages > 1 else u_file.name
                        
                        # Llamada a IA
                        data_dict = process_single_invoice(img_b64, nombre_mostrar, "compra", schema_def)
                        
                        # Guardar en base de datos
                        record = {
                            "schema_id": selected_schema_id,
                            "filename": nombre_mostrar,
                            "extracted_data": data_dict,
                            "created_at": datetime.utcnow()
                        }
                        db.save_extracted_record(record)
                        
                        # Preparar para visualización
                        flat_record = data_dict.copy()
                        flat_record["_filename"] = nombre_mostrar
                        results.append(flat_record)
                        
                        # Limpiar string base64
                        del img_b64
                        gc.collect()
                        
                else:
                    img = Image.open(temp_path).convert("RGB")
                    img_b64 = image_to_base64(img)
                    del img
                    gc.collect()
                    
                    data_dict = process_single_invoice(img_b64, u_file.name, "compra", schema_def)
                    
                    record = {
                        "schema_id": selected_schema_id,
                        "filename": u_file.name,
                        "extracted_data": data_dict,
                        "created_at": datetime.utcnow()
                    }
                    db.save_extracted_record(record)
                    
                    flat_record = data_dict.copy()
                    flat_record["_filename"] = u_file.name
                    results.append(flat_record)
                    
                    del img_b64
                    gc.collect()
                    
            except Exception as e:
                st.error(f"Error procesando {u_file.name}: {str(e)}")
            
            finally:
                # Borrar archivo temporal
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.text("¡Procesamiento finalizado!")
        st.session_state["results"] = results
        st.rerun()

if st.session_state["results"]:
    st.subheader("📊 Resultados Extraídos")
    
    # Mostrar tabla
    df_results = pd.DataFrame(st.session_state["results"])
    edited_df = st.data_editor(df_results, use_container_width=True)
    
    # Descargar Excel
    profile_def = profile_opts_filtered[selected_profile_id]
    
    # Convertir dataframe editado de vuelta a lista de diccionarios para el motor de exportación
    edited_records = edited_df.to_dict('records')
    
    excel_data = export_engine.generate_excel_from_profile(edited_records, profile_def)
    
    st.download_button(
        label="📥 Descargar Excel Dinámico",
        data=excel_data,
        file_name=f"exportacion_{profile_def['name']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    if st.button("🧹 Limpiar resultados"):
        st.session_state["results"] = []
        st.rerun()
