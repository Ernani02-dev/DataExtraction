import streamlit as st
import pandas as pd
from src.database import mongodb as db

st.set_page_config(page_title="Super Admin", page_icon="🔐", layout="wide")
st.title("🔐 Panel Super-Administrador")
st.write("Gestiona todas las empresas, sus límites de tokens y accesos.")

# (Para un sistema real, aquí habría un login forzado para el SuperAdmin)
# Por ahora simularemos la vista.

clients = db.get_all_clients()

if not clients:
    st.info("No hay empresas/clientes registrados en la plataforma.")
    st.stop()

# Tarjetas de resumen
total_companies = len(clients)
total_active = sum(1 for c in clients if c.get("is_active", True))
total_docs_used = sum(c.get("current_month_usage", 0) for c in clients)

col1, col2, col3 = st.columns(3)
col1.metric("Empresas Totales", total_companies)
col2.metric("Empresas Activas", total_active)
col3.metric("Total Docs Procesados (Mes)", total_docs_used)

st.write("---")
st.subheader("🏢 Gestión de Empresas (Tenants)")

for c in clients:
    client_id = str(c["_id"])
    nombre = c.get("nombre", "Sin Nombre")
    is_active = c.get("is_active", True)
    limit = c.get("monthly_doc_limit", 1000)
    usage = c.get("current_month_usage", 0)
    
    with st.expander(f"{'🟢' if is_active else '🔴'} {nombre} - Uso: {usage}/{limit}"):
        form_col1, form_col2 = st.columns(2)
        
        with st.form(f"admin_form_{client_id}"):
            st.write(f"**ID:** {client_id} | **RUC:** {c.get('ruc', 'N/A')}")
            
            new_is_active = st.checkbox("Empresa Activa (Puede procesar documentos)", value=is_active)
            new_limit = st.number_input("Límite de documentos mensuales", min_value=0, max_value=1000000, value=limit)
            
            if st.form_submit_button("Guardar Cambios", type="primary"):
                db.update_client(client_id, {
                    "is_active": new_is_active,
                    "monthly_doc_limit": new_limit
                })
                st.success(f"Configuración guardada para {nombre}.")
                st.rerun()
