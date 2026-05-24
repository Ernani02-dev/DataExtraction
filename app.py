import streamlit as st
import pandas as pd
import io
import os
import zipfile
import datetime
from PIL import Image

# Importar funciones y helpers de main.py
from main import (
    pdf_to_image, 
    image_to_base64, 
    process_single_invoice,
    clean_ruc_and_get_type,
    format_invoice_number,
    map_tipo_comprobante,
    map_condicion
)

st.set_page_config(page_title="Procesador de Facturas Premium", page_icon="📄", layout="wide")

# Estilos CSS personalizados para mejorar la estética de la aplicación
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
    
    .section-header {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        font-size: 1.4rem;
        color: #1F2937;
        border-bottom: 2px solid #E5E7EB;
        padding-bottom: 0.4rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📄 Automatización de Extracción de Facturas</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sube tus facturas (PDF, PNG, JPG) y exporta automáticamente los datos procesados en formato Excel estándar o listos para el sistema Marangatu de la SET paraguaya.</div>', unsafe_allow_html=True)

# Inicializar estados de sesión
if "extracted_results" not in st.session_state:
    st.session_state["extracted_results"] = []
if "processing_done" not in st.session_state:
    st.session_state["processing_done"] = False
if "current_files" not in st.session_state:
    st.session_state["current_files"] = []
if "tipo_factura_anterior" not in st.session_state:
    st.session_state["tipo_factura_anterior"] = ""

st.markdown('<div class="section-header">⚙️ Configuración de Procesamiento</div>', unsafe_allow_html=True)

col_cfg1, col_cfg2 = st.columns(2)

with col_cfg1:
    tipo_factura_ui = st.radio(
        "Selecciona el tipo de facturas que vas a procesar:", 
        ["Compras (Recibidas)", "Ventas (Emitidas)"], 
        horizontal=True
    )
    tipo_factura_str = "compra" if "Compras" in tipo_factura_ui else "venta"

# Resetear si cambia el tipo de factura
if st.session_state["tipo_factura_anterior"] != tipo_factura_str:
    st.session_state["tipo_factura_anterior"] = tipo_factura_str
    st.session_state["processing_done"] = False
    st.session_state["extracted_results"] = []

with col_cfg2:
    tipo_exportacion = st.selectbox("Formato de Exportación Objetivo:", ["Normal", "Marangatu"])

# Variables y controles específicos para Marangatu
informante_ruc = "80000000"
periodo_fiscal = "05/2026"
archivo_id = "V0001"
default_imputations = {'iva': 'S', 'ire': 'N', 'irp': 'N', 'no_imputa': 'N'}

if tipo_exportacion == "Marangatu":
    st.markdown('<div class="section-header">🇵🇾 Parámetros Requeridos para Marangatu</div>', unsafe_allow_html=True)
    col_mar1, col_mar2, col_mar3 = st.columns(3)
    
    informante_ruc = col_mar1.text_input(
        "RUC del Informante (sin DV)", 
        value="80000000",
        help="El RUC de tu empresa o de la persona física informante, sin el guion ni el dígito verificador."
    )
    
    now = datetime.datetime.now()
    default_period = now.strftime("%m/%Y")
    periodo_fiscal = col_mar2.text_input(
        "Periodo Fiscal (MM/AAAA)", 
        value=default_period,
        help="El mes y año correspondiente al periodo que vas a declarar."
    )
    
    default_id = "V0001" if tipo_factura_str == "venta" else "C0001"
    archivo_id = col_mar3.text_input(
        "Identificador del Archivo (máx. 5 char)", 
        value=default_id,
        max_chars=5,
        help="Código único para diferenciar tus archivos importados en Marangatu."
    )
    
    st.markdown("**Imputaciones impositivas por defecto:**")
    col_imp1, col_imp2, col_imp3, col_imp4 = st.columns(4)
    imp_iva = col_imp1.checkbox("Imputa IVA", value=True)
    imp_ire = col_imp2.checkbox("Imputa IRE", value=False)
    imp_irp = col_imp3.checkbox("Imputa IRP-RSP", value=False)
    
    default_imputations = {
        'iva': 'S' if imp_iva else 'N',
        'ire': 'S' if imp_ire else 'N',
        'irp': 'S' if imp_irp else 'N'
    }
    
    if tipo_factura_str == "compra":
        imp_no = col_imp4.checkbox("No Imputa", value=False)
        default_imputations['no_imputa'] = 'S' if imp_no else 'N'

st.markdown('<div class="section-header">📁 Carga de Documentos</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    "Arrastra y suelta tus facturas aquí (PDF, PNG, JPG, JPEG)", 
    type=["pdf", "png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

# Controlar si cambia la lista de archivos subidos
uploaded_file_names = [f.name for f in uploaded_files] if uploaded_files else []
if uploaded_file_names != st.session_state["current_files"]:
    st.session_state["current_files"] = uploaded_file_names
    st.session_state["processing_done"] = False
    st.session_state["extracted_results"] = []

# Botón para disparar el procesamiento
if uploaded_files and not st.session_state["processing_done"]:
    if st.button("🚀 Procesar Facturas con IA", type="primary", use_container_width=True):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Procesando: {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            try:
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                file_bytes = uploaded_file.read()
                
                if file_ext == '.pdf':
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    num_pages = len(doc)
                    
                    for page_num in range(num_pages):
                        status_text.text(f"Procesando: {uploaded_file.name} (Pág. {page_num+1}/{num_pages})")
                        
                        img = pdf_to_image(file_bytes, is_bytes=True, page_num=page_num)
                        img_b64 = image_to_base64(img)
                        
                        nombre_mostrar = f"{uploaded_file.name} (Pág. {page_num+1})" if num_pages > 1 else uploaded_file.name
                        data_dict = process_single_invoice(img_b64, nombre_mostrar, tipo_factura_str)
                        
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
            st.session_state["extracted_results"] = results
            st.session_state["processing_done"] = True
            st.rerun()

# Helpers para el formateo de tablas y descargas
def prepare_marangatu_df(results, tipo_factura_str, default_imputations, informante_ruc=None):
    from main import clean_ruc_and_get_type
    rows = []
    for item in results:
        def to_int(val):
            if val is None or pd.isna(val) or val == "":
                return 0
            try:
                return int(round(float(val)))
            except ValueError:
                return 0
                
        tipo_comp = item.get('tipo_comprobante_marangatu') or 109
        monto_tot = to_int(item.get('monto_total'))
        
        # Regla Marangatu de Compras para comprobantes sin IVA desagregado
        if tipo_factura_str == "compra" and tipo_comp in [101, 104, 112, 105]:
            g10 = 0
            g5 = 0
            ex = 0
        else:
            g10 = to_int(item.get('gravado_10'))
            g5 = to_int(item.get('gravado_5'))
            ex = to_int(item.get('exenta'))
            # Forzar suma consistente si hay descuadres menores
            if g10 + g5 + ex != monto_tot and monto_tot > 0:
                ex = monto_tot - (g10 + g5)
                if ex < 0:
                    g10 = monto_tot
                    g5 = 0
                    ex = 0
        
        if tipo_factura_str == "venta":
            row = {
                "Tipo Registro": 1,
                "Tipo Identificación": item.get('tipo_identificacion_marangatu', 11),
                "Identificación": item.get('identificacion_marangatu', ""),
                "Razón Social": item.get('nombre_marangatu', ""),
                "Tipo Comprobante": tipo_comp,
                "Fecha Emisión": item.get('fecha', ""),
                "Timbrado": str(to_int(item.get('timbrado'))),
                "Número Comprobante": item.get('nro_comprobante_marangatu', ""),
                "Gravado 10%": g10,
                "Gravado 5%": g5,
                "Exento": ex,
                "Monto Total": monto_tot,
                "Condición": item.get('condicion_marangatu', 1),
                "Moneda Extranjera": "N",
                "Imputa IVA": default_imputations.get('iva', 'S'),
                "Imputa IRE": default_imputations.get('ire', 'N'),
                "Imputa IRP-RSP": default_imputations.get('irp', 'N'),
                "Comprobante Asociado": item.get('nro_comprobante_asociado_marangatu', ""),
                "Timbrado Asociado": str(to_int(item.get('timbrado_asociado'))) if item.get('timbrado_asociado') else ""
            }
        else: # compra
            # --- NUEVOS CONTROLES ---
            # 1. No debe ser factura electrónica
            if item.get('es_factura_electronica'):
                continue
                
            # 2. El RUC del comprador debe coincidir con el RUC cargado en pantalla
            if informante_ruc:
                ruc_comprador_limpio, _ = clean_ruc_and_get_type(item.get('ruc_cliente'), "compra")
                inf_ruc_limpio, _ = clean_ruc_and_get_type(informante_ruc, "compra")
                # Solo excluimos si realmente logramos extraer un RUC de comprador y es distinto
                if ruc_comprador_limpio and inf_ruc_limpio and ruc_comprador_limpio != inf_ruc_limpio:
                    continue
            
            row = {
                "Tipo Registro": 2,
                "Tipo Identificación": item.get('tipo_identificacion_marangatu', 11),
                "Identificación": item.get('identificacion_marangatu', ""),
                "Razón Social": item.get('nombre_marangatu', ""),
                "Tipo Comprobante": tipo_comp,
                "Fecha Emisión": item.get('fecha', ""),
                "Timbrado": str(to_int(item.get('timbrado'))),
                "Número Comprobante": item.get('nro_comprobante_marangatu', ""),
                "Gravado 10%": g10,
                "Gravado 5%": g5,
                "Exento": ex,
                "Monto Total": monto_tot,
                "Condición": item.get('condicion_marangatu', 1),
                "Moneda Extranjera": "N",
                "Imputa IVA": default_imputations.get('iva', 'S'),
                "Imputa IRE": default_imputations.get('ire', 'N'),
                "Imputa IRP-RSP": default_imputations.get('irp', 'N'),
                "No Imputa": default_imputations.get('no_imputa', 'N'),
                "Comprobante Asociado": item.get('nro_comprobante_asociado_marangatu', ""),
                "Timbrado Asociado": str(to_int(item.get('timbrado_asociado'))) if item.get('timbrado_asociado') else ""
            }
        rows.append(row)
    return pd.DataFrame(rows)

def generate_marangatu_zip(df_data, informante_ruc, periodo_fiscal, archivo_id):
    ruc_clean = "".join(filter(str.isalnum, str(informante_ruc)))
    period_clean = "".join(filter(str.isdigit, str(periodo_fiscal)))
    id_clean = "".join(filter(str.isalnum, str(archivo_id)))
    
    filename_base = f"{ruc_clean}_REG_{period_clean}_{id_clean}"
    csv_filename = f"{filename_base}.csv"
    zip_filename = f"{filename_base}.zip"
    
    df_temp = df_data.copy()
    
    # Reemplazar valores nulos o NaNs por vacío antes del CSV
    for col in df_temp.columns:
        df_temp[col] = df_temp[col].apply(lambda x: "" if pd.isna(x) or x is None or str(x).lower() in ["nan", "none"] else str(x))
    
    csv_buffer = io.StringIO()
    # Escribir con terminadores correctos
    try:
        df_temp.to_csv(csv_buffer, sep=';', index=False, header=False, lineterminator='\r\n')
    except TypeError:
        df_temp.to_csv(csv_buffer, sep=';', index=False, header=False, line_terminator='\r\n')
        
    csv_data = csv_buffer.getvalue().encode('utf-8')
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(csv_filename, csv_data)
        
    return zip_buffer.getvalue(), zip_filename

# Mostrar interfaz si el procesamiento finalizó
if st.session_state["processing_done"] and st.session_state["extracted_results"]:
    st.markdown('<div class="section-header">📊 Resultados del Procesamiento</div>', unsafe_allow_html=True)
    st.info("💡 Consejo: Puedes hacer doble clic en cualquier celda de la tabla para editar y corregir cualquier dato leído incorrectamente.")
    
    results = st.session_state["extracted_results"]
    
    if tipo_exportacion == "Normal":
        # Formatear DataFrame Normal para que sea amigable
        df_normal = pd.DataFrame(results)
        
        # Identificar la columna de RUC y Razón Social adecuada
        ruc_col = 'ruc_cliente' if tipo_factura_str == 'venta' else 'ruc_vendedor'
        nombre_col = 'nombre_cliente' if tipo_factura_str == 'venta' else 'nombre_vendedor'
        
        cols_normal = [
            'archivo_origen', 
            'tipo_comprobante',
            'nro_factura', 
            ruc_col, 
            nombre_col,
            'fecha', 
            'timbrado', 
            'monto_total', 
            'gravado_10', 
            'gravado_5', 
            'exenta', 
            'condicion_operacion',
            'suma_validada'
        ]
        
        # Asegurar columnas existentes
        for col in cols_normal:
            if col not in df_normal.columns:
                df_normal[col] = None
                
        df_normal = df_normal[cols_normal]
        
        # Mostrar tabla editable
        edited_df = st.data_editor(df_normal, use_container_width=True)
        
        # Descarga de Excel Normal
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            edited_df.to_excel(writer, index=False)
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Descargar Planilla Excel (Normal)",
            data=excel_data,
            file_name=f"facturas_procesadas_{tipo_factura_str}s.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    else:
        # Formatear DataFrame para Marangatu
        df_marangatu = prepare_marangatu_df(results, tipo_factura_str, default_imputations, informante_ruc=informante_ruc)
        
        if len(df_marangatu) < len(results) and tipo_factura_str == "compra":
            omitidas = len(results) - len(df_marangatu)
            st.warning(f"⚠️ Se omitieron {omitidas} facturas de la tabla Marangatu porque son electrónicas o el RUC del comprador no coincide con el Informante.")
            
        # Configurar los tipos de datos de las columnas para st.data_editor
        column_config = {
            "Tipo Registro": st.column_config.NumberColumn("Registro", disabled=True),
            "Tipo Identificación": st.column_config.SelectboxColumn(
                "Tipo ID", 
                options=[11, 12, 13, 14, 15, 16, 17], 
                help="11=RUC, 12=CI, 15=Sin Nombre, 17=Id Tributaria Exterior"
            ),
            "Identificación": st.column_config.TextColumn("Nro. Identificación"),
            "Razón Social": st.column_config.TextColumn("Razón Social"),
            "Tipo Comprobante": st.column_config.SelectboxColumn(
                "Tipo Comp.", 
                options=[101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112],
                help="109=Factura, 110=NC, 101=Autofactura, 112=Ticket"
            ),
            "Fecha Emisión": st.column_config.TextColumn("Fecha (DD/MM/YYYY)"),
            "Timbrado": st.column_config.TextColumn("Timbrado"),
            "Número Comprobante": st.column_config.TextColumn("Nro. Comprobante"),
            "Gravado 10%": st.column_config.NumberColumn("Gravado 10%", min_value=0),
            "Gravado 5%": st.column_config.NumberColumn("Gravado 5%", min_value=0),
            "Exento": st.column_config.NumberColumn("Exento", min_value=0),
            "Monto Total": st.column_config.NumberColumn("Monto Total", min_value=0),
            "Condición": st.column_config.SelectboxColumn("Condición", options=[1, 2], help="1=Contado, 2=Crédito"),
            "Moneda Extranjera": st.column_config.SelectboxColumn("Moneda Extr.", options=["S", "N"]),
            "Imputa IVA": st.column_config.SelectboxColumn("Imp. IVA", options=["S", "N"]),
            "Imputa IRE": st.column_config.SelectboxColumn("Imp. IRE", options=["S", "N"]),
            "Imputa IRP-RSP": st.column_config.SelectboxColumn("Imp. IRP", options=["S", "N"]),
            "Comprobante Asociado": st.column_config.TextColumn("Comp. Asociado"),
            "Timbrado Asociado": st.column_config.TextColumn("Timbrado Asoc."),
        }
        if tipo_factura_str == "compra":
            column_config["No Imputa"] = st.column_config.SelectboxColumn("No Imp.", options=["S", "N"])
            
        edited_df = st.data_editor(df_marangatu, column_config=column_config, use_container_width=True)
        
        # Botones de descarga de Marangatu
        col_dl1, col_dl2 = st.columns(2)
        
        # 1. Excel de Marangatu con cabeceras para control visual
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            edited_df.to_excel(writer, index=False)
        excel_data = output.getvalue()
        
        col_dl1.download_button(
            label="📥 Descargar Excel Marangatu (Con cabeceras)",
            data=excel_data,
            file_name=f"facturas_marangatu_{tipo_factura_str}s.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        # 2. ZIP de Marangatu para importación directa en el sistema
        zip_data, zip_filename = generate_marangatu_zip(edited_df, informante_ruc, periodo_fiscal, archivo_id)
        
        col_dl2.download_button(
            label="⚡ Descargar ZIP Importación Marangatu (Sin cabeceras)",
            data=zip_data,
            file_name=zip_filename,
            mime="application/zip",
            use_container_width=True
        )
    
    # Botón para reiniciar
    if st.button("🧹 Limpiar resultados y procesar otros archivos", use_container_width=True):
        st.session_state["extracted_results"] = []
        st.session_state["processing_done"] = False
        st.rerun()
elif not uploaded_files:
    st.info("👋 Sube algunas facturas en la sección de arriba para comenzar a extraer la información.")
