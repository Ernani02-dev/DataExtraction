import streamlit as st
import database as db

st.set_page_config(page_title="Configurar Exportación", page_icon="📊", layout="wide")
st.title("📊 Perfiles de Exportación")
st.write("Diseña la estructura de tu archivo Excel. Mapea campos extraídos por IA o agrega valores fijos.")

# Listar perfiles existentes
st.subheader("Perfiles Actuales")
profiles = db.get_all_profiles()

if profiles:
    for profile in profiles:
        with st.expander(f"📥 {profile.get('name', 'Sin nombre')}"):
            schema = db.get_schema_by_id(str(profile.get('schema_id')))
            schema_name = schema.get('name') if schema else "Desconocido"
            st.write(f"**Asociado al esquema:** {schema_name}")
            st.write("**Columnas (Excel):**")
            
            cols = profile.get('columns', [])
            for c in cols:
                if c.get('source_type') == 'fixed':
                    st.markdown(f"- `{c['excel_header']}` -> Fijo: *{c.get('value')}*")
                else:
                    st.markdown(f"- `{c['excel_header']}` -> Extraído: *{c.get('source_field')}*")
else:
    st.info("No hay perfiles de exportación definidos todavía.")

st.write("---")
st.subheader("Crear Nuevo Perfil")

schemas = db.get_all_schemas()
if not schemas:
    st.warning("Primero debes crear un Esquema de Documento en la pestaña de Esquemas.")
else:
    schema_options = {str(s["_id"]): s["name"] for s in schemas}
    
    with st.form("new_profile_form"):
        name = st.text_input("Nombre del Perfil (ej. Importación a SAP)")
        selected_schema_id = st.selectbox("Asociar al Esquema:", options=list(schema_options.keys()), format_func=lambda x: schema_options[x])
        
        st.write("En esta versión rápida crearemos un mapeo básico. Para configuraciones avanzadas se debe guardar primero.")
        
        plantilla_export = st.radio("Plantilla inicial de columnas:", ["Copiar Esquema Exacto", "Plantilla Marangatu (Ventas)"])
        
        submit = st.form_submit_button("Guardar Perfil", type="primary")
        
        if submit and name:
            columns = []
            if plantilla_export == "Copiar Esquema Exacto":
                schema = db.get_schema_by_id(selected_schema_id)
                for field in schema.get('fields', []):
                    columns.append({
                        "excel_header": field["name"].upper(),
                        "source_type": "extracted",
                        "source_field": field["name"]
                    })
            elif plantilla_export == "Plantilla Marangatu (Ventas)":
                columns = [
                    {"excel_header": "Tipo Registro", "source_type": "fixed", "value": "1"},
                    {"excel_header": "Tipo Identificación", "source_type": "fixed", "value": "11"},
                    {"excel_header": "Identificación", "source_type": "extracted", "source_field": "ruc_cliente"},
                    {"excel_header": "Monto Total", "source_type": "extracted", "source_field": "monto_total"},
                ]
                
            profile_data = {
                "name": name,
                "schema_id": selected_schema_id,
                "columns": columns
            }
            db.create_profile(profile_data)
            st.success("Perfil de exportación guardado correctamente.")
            st.rerun()
