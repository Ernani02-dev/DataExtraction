import streamlit as st
import pandas as pd
from src.database import mongodb as db

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
st.subheader("Gestión de Perfiles")

schemas = db.get_all_schemas()

if not schemas:
    st.warning("Primero debes crear un Esquema de Documento en la pestaña de Esquemas.")
else:
    schema_options = {str(s["_id"]): s["name"] for s in schemas}
    
    tab_create, tab_edit, tab_delete = st.tabs(["✨ Crear Nuevo", "✏️ Editar Existente", "🗑️ Eliminar"])

    with tab_create:
        name = st.text_input("Nombre del Perfil (ej. Importación a SAP)", key="create_profile_name")
        selected_schema_id = st.selectbox("Selecciona el Esquema base:", options=list(schema_options.keys()), format_func=lambda x: schema_options[x], key="create_schema_select")
        
        if selected_schema_id:
            schema = db.get_schema_by_id(selected_schema_id)
            campos_esquema = [f["name"] for f in schema.get('fields', [])]
            
            st.write("**Define las columnas de tu Excel:**")
            
            default_columns = []
            for campo in campos_esquema:
                default_columns.append({
                    "Cabecera Excel": campo.upper(),
                    "Tipo de Origen": "Extraído por IA",
                    "Valor Fijo": "",
                    "Campo Extraído": campo
                })
                
            df_cols = pd.DataFrame(default_columns)
            
            edited_df = st.data_editor(
                df_cols,
                num_rows="dynamic",
                use_container_width=True,
                key="create_profile_editor",
                column_config={
                    "Cabecera Excel": st.column_config.TextColumn("Nombre de la Columna en Excel"),
                    "Tipo de Origen": st.column_config.SelectboxColumn("Origen del Dato", options=["Extraído por IA", "Fijo predeterminado"]),
                    "Valor Fijo": st.column_config.TextColumn("Escribe el valor si elegiste 'Fijo'"),
                    "Campo Extraído": st.column_config.SelectboxColumn("Selecciona el campo si elegiste 'Extraído'", options=campos_esquema)
                }
            )
            
            if st.button("Guardar Perfil Definitivo", type="primary", key="save_new_profile"):
                if not name:
                    st.error("El nombre del perfil es obligatorio.")
                else:
                    columns_to_save = []
                    mapped_fields = set()
                    
                    for index, row in edited_df.iterrows():
                        if pd.notna(row['Cabecera Excel']) and str(row['Cabecera Excel']).strip() != "":
                            source_type = "fixed" if row['Tipo de Origen'] == "Fijo predeterminado" else "extracted"
                            col_dict = {"excel_header": str(row['Cabecera Excel']).strip(), "source_type": source_type}
                            
                            if source_type == "fixed":
                                col_dict["value"] = str(row['Valor Fijo']) if pd.notna(row['Valor Fijo']) else ""
                            else:
                                campo = str(row['Campo Extraído']) if pd.notna(row['Campo Extraído']) else ""
                                col_dict["source_field"] = campo
                                mapped_fields.add(campo)
                                
                            columns_to_save.append(col_dict)
                    
                    esquema_set = set(campos_esquema)
                    missing_fields = esquema_set - mapped_fields
                    
                    if missing_fields:
                        missing_str = ", ".join(list(missing_fields))
                        st.error(f"⚠️ Error: Faltan asignar los siguientes campos: {missing_str}")
                    else:
                        profile_data = {"name": name, "schema_id": selected_schema_id, "columns": columns_to_save}
                        db.create_profile(profile_data)
                        st.success("Perfil guardado correctamente.")
                        st.rerun()

    with tab_edit:
        if not profiles:
            st.info("No hay perfiles para editar.")
        else:
            profile_opts = {str(p["_id"]): p["name"] for p in profiles}
            selected_edit_id = st.selectbox("Selecciona el perfil a editar:", options=list(profile_opts.keys()), format_func=lambda x: profile_opts[x], key="edit_profile_select")
            
            if selected_edit_id:
                profile_to_edit = next((p for p in profiles if str(p["_id"]) == selected_edit_id), None)
                edit_name = st.text_input("Nombre del Perfil", value=profile_to_edit.get("name", ""), key="edit_profile_name")
                
                # Para editar, mantenemos el esquema original asociado al perfil (no se permite cambiar el esquema de un perfil, es más seguro)
                schema_asociado_id = profile_to_edit.get("schema_id")
                schema_asociado = db.get_schema_by_id(schema_asociado_id)
                campos_esquema_edit = [f["name"] for f in schema_asociado.get('fields', [])] if schema_asociado else []
                
                st.write(f"**Esquema base:** {schema_options.get(schema_asociado_id, 'Desconocido')}")
                
                edit_columns_data = []
                for c in profile_to_edit.get("columns", []):
                    edit_columns_data.append({
                        "Cabecera Excel": c.get("excel_header", ""),
                        "Tipo de Origen": "Fijo predeterminado" if c.get("source_type") == "fixed" else "Extraído por IA",
                        "Valor Fijo": c.get("value", ""),
                        "Campo Extraído": c.get("source_field", "")
                    })
                
                if not edit_columns_data:
                    edit_columns_data = [{"Cabecera Excel": "", "Tipo de Origen": "Extraído por IA", "Valor Fijo": "", "Campo Extraído": ""}]
                
                df_edit_cols = pd.DataFrame(edit_columns_data)
                
                edited_edit_df = st.data_editor(
                    df_edit_cols,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="edit_profile_editor",
                    column_config={
                        "Cabecera Excel": st.column_config.TextColumn("Nombre de la Columna en Excel"),
                        "Tipo de Origen": st.column_config.SelectboxColumn("Origen del Dato", options=["Extraído por IA", "Fijo predeterminado"]),
                        "Valor Fijo": st.column_config.TextColumn("Escribe el valor si elegiste 'Fijo'"),
                        "Campo Extraído": st.column_config.SelectboxColumn("Selecciona el campo si elegiste 'Extraído'", options=campos_esquema_edit)
                    }
                )
                
                if st.button("Guardar Cambios del Perfil", type="primary", key="save_edit_profile"):
                    if not edit_name:
                        st.error("El nombre del perfil es obligatorio.")
                    else:
                        columns_to_save = []
                        mapped_fields = set()
                        
                        for index, row in edited_edit_df.iterrows():
                            if pd.notna(row['Cabecera Excel']) and str(row['Cabecera Excel']).strip() != "":
                                source_type = "fixed" if row['Tipo de Origen'] == "Fijo predeterminado" else "extracted"
                                col_dict = {"excel_header": str(row['Cabecera Excel']).strip(), "source_type": source_type}
                                
                                if source_type == "fixed":
                                    col_dict["value"] = str(row['Valor Fijo']) if pd.notna(row['Valor Fijo']) else ""
                                else:
                                    campo = str(row['Campo Extraído']) if pd.notna(row['Campo Extraído']) else ""
                                    col_dict["source_field"] = campo
                                    mapped_fields.add(campo)
                                    
                                columns_to_save.append(col_dict)
                        
                        esquema_set = set(campos_esquema_edit)
                        missing_fields = esquema_set - mapped_fields
                        
                        if missing_fields:
                            missing_str = ", ".join(list(missing_fields))
                            st.error(f"⚠️ Error: Faltan asignar los siguientes campos: {missing_str}")
                        else:
                            db.update_profile(selected_edit_id, {
                                "name": edit_name,
                                "columns": columns_to_save
                            })
                            st.success("Perfil actualizado correctamente.")
                            st.rerun()

    with tab_delete:
        if not profiles:
            st.info("No hay perfiles para eliminar.")
        else:
            profile_opts_del = {str(p["_id"]): p["name"] for p in profiles}
            selected_del_id = st.selectbox("Selecciona el perfil a eliminar:", options=list(profile_opts_del.keys()), format_func=lambda x: profile_opts_del[x], key="del_profile_select")
            
            if selected_del_id:
                st.warning("⚠️ ¿Estás seguro de eliminar este perfil de exportación?")
                if st.button("Sí, Eliminar Perfil", type="primary", key="btn_delete_profile"):
                    db.delete_profile(selected_del_id)
                    st.success("Perfil eliminado correctamente.")
                    st.rerun()
