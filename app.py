import streamlit as st
from src.database.mongodb import db

st.set_page_config(page_title="Facturas Premium - Dashboard", page_icon="📄", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 2.5rem;
        background: linear-gradient(135deg, #1E3A8A, #3B82F6, #10B981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    
    .card {
        background-color: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        text-align: center;
        border: 1px solid #e5e7eb;
    }
    
    .card-value {
        font-size: 3rem;
        font-weight: 700;
        color: #1f2937;
        margin: 10px 0;
    }
    
    .card-title {
        font-size: 1.2rem;
        color: #6b7280;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📄 Dashboard Principal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Bienvenido al procesador de facturas y documentos inteligentes con PostgreSQL.</div>', unsafe_allow_html=True)

# Métricas
try:
    total_clients = db.clients_collection.count_documents({})
    total_schemas = db.document_schemas.count_documents({})
    total_profiles = db.export_profiles.count_documents({})
    total_records = db.extracted_records.count_documents({})
except Exception as e:
    total_clients = 0
    total_schemas = 0
    total_profiles = 0
    total_records = 0
    st.error(f"Error conectando a PostgreSQL: {e}. Asegúrate de que la base de datos esté corriendo.")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="card"><div class="card-title">Clientes Activos</div><div class="card-value">{total_clients}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="card"><div class="card-title">Tipos de Documento</div><div class="card-value">{total_schemas}</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="card"><div class="card-title">Perfiles de Exportación</div><div class="card-value">{total_profiles}</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="card"><div class="card-title">Documentos Procesados</div><div class="card-value">{total_records}</div></div>', unsafe_allow_html=True)

st.write("---")
st.subheader("Navegación Rápida")
c0, c1, c2, c3 = st.columns(4)

if c0.button("🧑‍💼 Gestionar Clientes", use_container_width=True, type="primary"):
    st.switch_page("pages/0_Clientes.py")
    
if c1.button("🛠️ Configurar Esquemas", use_container_width=True, type="primary"):
    st.switch_page("pages/1_Esquemas.py")
    
if c2.button("📊 Configurar Exportación", use_container_width=True, type="primary"):
    st.switch_page("pages/2_Exportacion.py")
    
if c3.button("🚀 Procesar Documentos", use_container_width=True, type="primary"):
    st.switch_page("pages/3_Procesador.py")
