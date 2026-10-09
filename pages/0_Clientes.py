import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import mongodb as db

st.set_page_config(page_title="Gestión de Clientes", page_icon="🧑‍💼", layout="wide")
st.title("🧑‍💼 Gestión de Clientes")
st.write("Registra los clientes para poder asociarles los documentos procesados.")

# Listar clientes actuales
st.subheader("Clientes Registrados")
clients = db.get_all_clients()

if clients:
    # Preparar datos para la tabla
    client_data = []
    for c in clients:
        client_data.append({
            "ID": str(c["_id"]),
            "Nombre / Razón Social": c.get("nombre", ""),
            "RUC": c.get("ruc", ""),
            "Fecha Registro": c.get("created_at", "").strftime("%Y-%m-%d %H:%M") if isinstance(c.get("created_at"), datetime) else c.get("created_at", "")
        })
    
    df_clients = pd.DataFrame(client_data)
    st.dataframe(df_clients, use_container_width=True, hide_index=True)
    
    st.write("---")
    st.subheader("Modificar o Eliminar Cliente")
    client_options = {str(c["_id"]): f"{c.get('nombre')} (RUC: {c.get('ruc')})" for c in clients}
    
    selected_client_id = st.selectbox("Selecciona un cliente:", options=list(client_options.keys()), format_func=lambda x: client_options[x])
    
    if selected_client_id:
        client_to_edit = next((c for c in clients if str(c["_id"]) == selected_client_id), None)
        
        tab_edit, tab_delete = st.tabs(["✏️ Editar", "🗑️ Eliminar"])
        
        with tab_edit:
            with st.form("edit_client_form"):
                edit_nombre = st.text_input("Nombre o Razón Social *", value=client_to_edit.get("nombre", ""))
                edit_ruc = st.text_input("RUC (con o sin DV) *", value=client_to_edit.get("ruc", ""))
                submit_edit = st.form_submit_button("Guardar Cambios", type="primary")
                
                if submit_edit:
                    if not edit_nombre.strip() or not edit_ruc.strip():
                        st.error("Por favor, completa todos los campos requeridos (*).")
                    else:
                        db.update_client(selected_client_id, {
                            "nombre": edit_nombre.strip(),
                            "ruc": edit_ruc.strip()
                        })
                        st.success("Cliente actualizado correctamente.")
                        st.rerun()
                        
        with tab_delete:
            st.warning("⚠️ ¿Estás seguro de que deseas eliminar este cliente? Esta acción no se puede deshacer.")
            if st.button("Sí, Eliminar Cliente", type="primary"):
                db.delete_client(selected_client_id)
                st.success("Cliente eliminado correctamente.")
                st.rerun()

else:
    st.info("No hay clientes registrados todavía.")

st.write("---")
st.subheader("Registrar Nuevo Cliente")

with st.form("new_client_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre o Razón Social *")
    with col2:
        ruc = st.text_input("RUC (con o sin DV) *")
        
    submit_btn = st.form_submit_button("Guardar Cliente", type="primary")
    
    if submit_btn:
        if not nombre.strip() or not ruc.strip():
            st.error("Por favor, completa todos los campos requeridos (*).")
        else:
            new_client = {
                "nombre": nombre.strip(),
                "ruc": ruc.strip(),
                "created_at": datetime.utcnow()
            }
            db.create_client(new_client)
            st.success("Cliente guardado correctamente.")
            st.rerun()
