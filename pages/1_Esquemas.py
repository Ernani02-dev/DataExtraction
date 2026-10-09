import streamlit as st
import pandas as pd
import os
import gc
from PIL import Image
import json

from src.database import mongodb as db
from src.services.document_parser import pdf_to_image, image_to_base64
from src.services.ai_extractor import process_single_invoice

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
                
            schema_export = dict(schema)
            schema_export['_id'] = str(schema_export['_id'])
            json_str = json.dumps(schema_export, indent=2, ensure_ascii=False)
            
            st.download_button(
                label="⬇️ Exportar Esquema (JSON)",
                data=json_str,
                file_name=f"esquema_{schema.get('name', 'sin_nombre').replace(' ', '_')}.json",
                mime="application/json",
                key=f"export_{schema_export['_id']}"
            )
else:
    st.info("No hay esquemas definidos todavía.")

st.write("---")
st.subheader("Gestión de Esquemas")

tab_create, tab_edit, tab_delete = st.tabs(["✨ Crear Nuevo", "✏️ Editar Existente", "🗑️ Eliminar"])

with tab_create:
    st.write("### Crear Nuevo Esquema Personalizado")
    name = st.text_input("Nombre del Documento (ej. Factura Compra)", key="create_name")
    description = st.text_area("Descripción General (ej. Factura normal de compras)", key="create_desc")
    
    st.write("**Define los campos a extraer:** (Puedes agregar o eliminar filas en la tabla)")
    
    default_fields = [
        {"Nombre": "nro_factura", "Tipo": "string", "Descripción": "Número de la factura"},
        {"Nombre": "monto_total", "Tipo": "number", "Descripción": "Suma total de la factura"}
    ]
    df_fields = pd.DataFrame(default_fields)
    
    edited_df = st.data_editor(
        df_fields, 
        num_rows="dynamic", 
        use_container_width=True,
        key="create_editor",
        column_config={
            "Nombre": st.column_config.TextColumn("Nombre del Campo (snake_case)"),
            "Tipo": st.column_config.SelectboxColumn("Tipo de Dato", options=["string", "number"]),
            "Descripción": st.column_config.TextColumn("Instrucción para la IA")
        }
    )
    
    if st.button("Guardar Nuevo Esquema", type="primary", key="save_new_schema"):
        if not name:
            st.error("El nombre del esquema es obligatorio.")
        else:
            fields = []
            for index, row in edited_df.iterrows():
                if pd.notna(row['Nombre']) and str(row['Nombre']).strip() != "":
                    fields.append({
                        "name": str(row['Nombre']).strip(),
                        "type": str(row['Tipo']),
                        "description": str(row['Descripción']) if pd.notna(row['Descripción']) else ""
                    })
            
            schema_data = {
                "name": name,
                "description": description,
                "fields": fields
            }
            db.create_schema(schema_data)
            st.success("Esquema guardado correctamente.")
            st.rerun()
            
    st.write("---")
    st.subheader("🧪 Probar Extracción (Solo Vista Previa)")
    test_file = st.file_uploader("Archivo de prueba", type=["pdf", "png", "jpg", "jpeg"], key="test_file_create")
    if st.button("Probar Extracción", type="secondary", key="test_extract"):
        if not test_file:
            st.warning("Sube un archivo primero.")
        else:
            temp_fields = []
            for index, row in edited_df.iterrows():
                if pd.notna(row['Nombre']) and str(row['Nombre']).strip() != "":
                    temp_fields.append({
                        "name": str(row['Nombre']).strip(),
                        "type": str(row['Tipo']),
                        "description": str(row['Descripción']) if pd.notna(row['Descripción']) else ""
                    })
            temp_schema = {"name": name if name else "Prueba", "description": description, "fields": temp_fields}
            
            with st.spinner("Consultando a la IA..."):
                if not os.path.exists("tmp"): os.makedirs("tmp")
                temp_path = os.path.join("tmp", test_file.name)
                with open(temp_path, "wb") as f: f.write(test_file.getbuffer())
                try:
                    ext = os.path.splitext(test_file.name)[1].lower()
                    if ext == '.pdf':
                        img = pdf_to_image(temp_path, is_bytes=False, page_num=0)
                    else:
                        img = Image.open(temp_path).convert("RGB")
                    img_b64 = image_to_base64(img)
                    del img
                    gc.collect()
                    data_dict = process_single_invoice(img_b64, test_file.name, "compra", temp_schema)
                    st.success("Extracción completada (Vista Previa):")
                    st.json(data_dict)
                except Exception as e:
                    st.error(f"Error procesando: {str(e)}")
                finally:
                    if os.path.exists(temp_path): os.remove(temp_path)


with tab_edit:
    if not schemas:
        st.info("No hay esquemas para editar.")
    else:
        schema_opts = {str(s["_id"]): s["name"] for s in schemas}
        selected_edit_id = st.selectbox("Selecciona el esquema a editar:", options=list(schema_opts.keys()), format_func=lambda x: schema_opts[x], key="edit_select")
        
        if selected_edit_id:
            schema_to_edit = next((s for s in schemas if str(s["_id"]) == selected_edit_id), None)
            
            edit_name = st.text_input("Nombre del Documento", value=schema_to_edit.get("name", ""), key="edit_name")
            edit_desc = st.text_area("Descripción General", value=schema_to_edit.get("description", ""), key="edit_desc")
            
            st.write("**Campos a extraer:**")
            
            edit_fields_data = []
            for f in schema_to_edit.get("fields", []):
                edit_fields_data.append({
                    "Nombre": f.get("name", ""),
                    "Tipo": f.get("type", "string"),
                    "Descripción": f.get("description", "")
                })
            if not edit_fields_data:
                edit_fields_data = [{"Nombre": "", "Tipo": "string", "Descripción": ""}]
                
            df_edit_fields = pd.DataFrame(edit_fields_data)
            
            edited_edit_df = st.data_editor(
                df_edit_fields, 
                num_rows="dynamic", 
                use_container_width=True,
                key="edit_editor",
                column_config={
                    "Nombre": st.column_config.TextColumn("Nombre del Campo (snake_case)"),
                    "Tipo": st.column_config.SelectboxColumn("Tipo de Dato", options=["string", "number"]),
                    "Descripción": st.column_config.TextColumn("Instrucción para la IA")
                }
            )
            
            if st.button("Guardar Cambios", type="primary", key="save_edit_schema"):
                if not edit_name:
                    st.error("El nombre del esquema es obligatorio.")
                else:
                    new_fields = []
                    for index, row in edited_edit_df.iterrows():
                        if pd.notna(row['Nombre']) and str(row['Nombre']).strip() != "":
                            new_fields.append({
                                "name": str(row['Nombre']).strip(),
                                "type": str(row['Tipo']),
                                "description": str(row['Descripción']) if pd.notna(row['Descripción']) else ""
                            })
                    
                    db.update_schema(selected_edit_id, {
                        "name": edit_name,
                        "description": edit_desc,
                        "fields": new_fields
                    })
                    st.success("Esquema actualizado correctamente.")
                    st.rerun()

with tab_delete:
    if not schemas:
        st.info("No hay esquemas para eliminar.")
    else:
        schema_opts_del = {str(s["_id"]): s["name"] for s in schemas}
        selected_del_id = st.selectbox("Selecciona el esquema a eliminar:", options=list(schema_opts_del.keys()), format_func=lambda x: schema_opts_del[x], key="del_select")
        
        if selected_del_id:
            st.warning("⚠️ ¿Estás seguro de eliminar este esquema? Los perfiles de exportación y registros asociados podrían perder su referencia principal.")
            if st.button("Sí, Eliminar Esquema", type="primary", key="btn_delete_schema"):
                db.delete_schema(selected_del_id)
                st.success("Esquema eliminado correctamente.")
                st.rerun()
