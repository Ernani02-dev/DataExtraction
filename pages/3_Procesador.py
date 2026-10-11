import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import mongodb as db
from src.services import exporter as export_engine
from src.services.pipeline_orchestrator import process_uploaded_files

st.set_page_config(page_title="Procesador IA", page_icon="🚀", layout="wide")
st.title("🚀 Procesador de Documentos")
st.write("Sube tus documentos y deja que la IA extraiga los datos basándose en el esquema seleccionado.")

# Cargar configuración desde DB
clients = db.get_all_clients()
schemas = db.get_all_schemas()
profiles = db.get_all_profiles()

if not clients:
    st.warning("⚠️ Debes registrar al menos un Cliente (en la pestaña Clientes) antes de procesar archivos.")
    st.stop()

if not schemas or not profiles:
    st.warning("⚠️ Debes configurar al menos un Esquema y un Perfil de Exportación antes de procesar archivos.")
    st.stop()

client_opts = {str(c["_id"]): c for c in clients}
schema_opts = {str(s["_id"]): s for s in schemas}
profile_opts = {str(p["_id"]): p for p in profiles}

col0, col1, col2 = st.columns(3)
with col0:
    selected_client_id = st.selectbox("1. Cliente:", options=list(client_opts.keys()), format_func=lambda x: client_opts[x]["nombre"])
with col1:
    selected_schema_id = st.selectbox("2. Tipo de Documento (Esquema):", options=list(schema_opts.keys()), format_func=lambda x: schema_opts[x]["name"])
with col2:
    valid_profiles = [p for p in profiles if str(p.get("schema_id")) == selected_schema_id]
    if not valid_profiles:
        st.warning("No hay perfiles de exportación compatibles con este esquema.")
        selected_profile_id = None
    else:
        profile_opts_filtered = {str(p["_id"]): p for p in valid_profiles}
        selected_profile_id = st.selectbox("3. Perfil de Exportación (Excel):", options=list(profile_opts_filtered.keys()), format_func=lambda x: profile_opts_filtered[x]["name"])

if "results" not in st.session_state:
    st.session_state["results"] = []

tab1, tab2 = st.tabs(["⚡ Procesamiento Directo (Pocos archivos)", "🚀 Procesamiento en Lotes (ZIP / Segundo Plano)"])

with tab1:
    uploaded_files = st.file_uploader("Sube tus facturas sueltas (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    
    if uploaded_files and selected_profile_id:
        if st.button("Procesar Directamente", type="primary", use_container_width=True):
            schema_def = schema_opts[selected_schema_id]
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_callback(completed, total):
                progress_bar.progress(completed / total)
                
            def log_callback(msg, is_error=False):
                if is_error:
                    st.error(msg)
                else:
                    status_text.text(msg)
            
            results = process_uploaded_files(
                uploaded_files=uploaded_files,
                schema_def=schema_def,
                selected_schema_id=selected_schema_id,
                selected_client_id=selected_client_id,
                progress_callback=progress_callback,
                log_callback=log_callback
            )
            
            st.session_state["results"] = results
            st.rerun()

with tab2:
    st.info("Sube un archivo .zip con todas tus imágenes/PDFs. Se procesará en segundo plano.")
    uploaded_zip = st.file_uploader("Sube tu archivo .zip", type=["zip"])
    
    if uploaded_zip and selected_profile_id:
        if st.button("Enviar a Procesar en Segundo Plano", type="primary", use_container_width=True):
            import os
            import tempfile
            from datetime import datetime
            from src.tasks import process_zip_batch
            
            # Guardar zip temporalmente
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, uploaded_zip.name)
            with open(zip_path, "wb") as f:
                f.write(uploaded_zip.getvalue())
                
            # Crear batch en DB
            batch_data = {
                "client_id": selected_client_id,
                "schema_id": selected_schema_id,
                "file_name": uploaded_zip.name,
                "status": "pending",
                "upload_date": datetime.utcnow()
            }
            batch_id = db.create_batch(batch_data)
            
            # Enviar a Celery
            process_zip_batch.delay(batch_id, zip_path, selected_schema_id, selected_client_id)
            
            st.success(f"¡Lote enviado! ID: {batch_id}. Puedes seguir usando la plataforma, el proceso corre en segundo plano.")
            
    # Mostrar lotes del cliente
    if selected_client_id:
        st.subheader("Tus Lotes Recientes")
        batches = db.get_batches_by_client(selected_client_id)
        if batches:
            for b in batches:
                status_color = "🟢" if b['status'] == 'completed' else "🟡" if b['status'] == 'processing' else "🔴" if b['status'] == 'failed' else "⚪"
                progress = b.get('progress', '')
                st.write(f"{status_color} **{b['file_name']}** - Estado: {b['status']} {progress}")
        else:
            st.write("No tienes lotes procesados.")


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
