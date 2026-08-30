import streamlit as st
import database as db

st.set_page_config(page_title="Configurar Esquemas", page_icon="⚙️", layout="wide")
st.title("⚙️ Tipos de Documento (Schemas)")
st.write("Define qué campos extraer de los documentos mediante Inteligencia Artificial.")

# Listar esquemas existentes
st.subheader("Esquemas Actuales")
schemas = db.get_all_schemas()

if schemas:
    for schema in schemas:
        with st.expander(f"📄 {schema.get('name', 'Sin nombre')}"):
            st.write(f"**Descripción:** {schema.get('description', '')}")
            st.write("**Campos:**")
            for field in schema.get('fields', []):
                st.markdown(f"- `{field['name']}` ({field['type']}): {field.get('description', '')}")
else:
    st.info("No hay esquemas definidos todavía.")

st.write("---")
st.subheader("Crear Nuevo Esquema")

with st.form("new_schema_form"):
    name = st.text_input("Nombre del Documento (ej. Factura Compra)")
    description = st.text_area("Descripción General (ej. Factura normal de compras)")
    
    st.write("Para agregar campos, debes guardar el esquema primero y luego editarlos (En esta versión rápida crearemos algunos campos por defecto).")
    
    campos_default = st.radio("Plantilla inicial de campos:", ["Básico (Nro y Total)", "Factura Completa", "Vacío"])
    
    submit = st.form_submit_button("Guardar Esquema", type="primary")
    
    if submit and name:
        fields = []
        if campos_default == "Básico (Nro y Total)":
            fields = [
                {"name": "nro_factura", "type": "string", "description": "Número identificador del documento"},
                {"name": "monto_total", "type": "number", "description": "Monto total a pagar"}
            ]
        elif campos_default == "Factura Completa":
            fields = [
                {"name": "nro_factura", "type": "string", "description": "Número de la factura xxx-xxx-xxxxxxx"},
                {"name": "ruc_emisor", "type": "string", "description": "RUC del vendedor"},
                {"name": "nombre_emisor", "type": "string", "description": "Razón social del vendedor"},
                {"name": "monto_total", "type": "number", "description": "Suma total de la factura"},
                {"name": "fecha", "type": "string", "description": "Fecha de emisión"}
            ]
            
        schema_data = {
            "name": name,
            "description": description,
            "fields": fields
        }
        db.create_schema(schema_data)
        st.success("Esquema guardado correctamente.")
        st.rerun()
