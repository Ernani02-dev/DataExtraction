import os
import glob
import base64
from typing import Optional
from dotenv import load_dotenv
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import io

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# Cargar variables de entorno
load_dotenv()

class InvoiceData(BaseModel):
    """Esquema de datos para la extracción de información de la factura."""
    nro_factura: Optional[str] = Field(description="Número identificador de la factura con formato xxx-xxx-xxxxxxx.")
    ruc_vendedor: Optional[str] = Field(description="RUC de la empresa que vende o emite la factura. Incluir dígito verificador si está disponible.")
    ruc_cliente: Optional[str] = Field(description="RUC del cliente que compra o a quien va dirigida la factura. Incluir dígito verificador si está disponible.")
    nombre_vendedor: Optional[str] = Field(description="Razón social o nombre de la empresa que emite la factura (vendedor).")
    nombre_cliente: Optional[str] = Field(description="Razón social o nombre del cliente a quien va dirigida la factura (comprador).")
    fecha: Optional[str] = Field(description="Fecha de emisión en formato DD/MM/YYYY.")
    timbrado: Optional[str] = Field(description="Número de timbrado legal de 8 dígitos.")
    monto_total: Optional[float] = Field(description="Suma total de la factura.")
    gravado_10: Optional[float] = Field(description="Monto imponible al 10% (IVA incluido).")
    gravado_5: Optional[float] = Field(description="Monto imponible al 5% (IVA incluido).")
    exenta: Optional[float] = Field(description="Monto de artículos o servicios exentos de impuestos.")
    condicion_operacion: Optional[str] = Field(description="Condición de la operación. Debe ser estrictamente 'Contado' o 'Crédito'.")
    tipo_comprobante: Optional[str] = Field(description="Tipo de comprobante. Debe ser 'Factura', 'Nota de Crédito', 'Autofactura', 'Boleta de Venta' o 'Ticket'.")
    nro_comprobante_asociado: Optional[str] = Field(description="Número de comprobante asociado (xxx-xxx-xxxxxxx) si es una Nota de Crédito/Débito.")
    timbrado_asociado: Optional[str] = Field(description="Número de timbrado asociado (8 dígitos) si es una Nota de Crédito/Débito.")
    es_factura_electronica: Optional[bool] = Field(description="Verdadero si es una factura electrónica (suele decir KuDE o Documento Electrónico). Falso si es preimpresa o autoimpresor.")

def clean_ruc_and_get_type(ruc_raw: Optional[str], default_tipo_registro: str) -> tuple[str, int]:
    """Limpia el RUC o Cédula y devuelve el número sin DV y el tipo de identificación (11=RUC, 12=Cédula, 15=Sin Nombre)."""
    if not ruc_raw or str(ruc_raw).strip().lower() in ["null", "none", "sin nombre", ""]:
        return "", 15
    
    raw_str = str(ruc_raw).strip()
    
    # Si contiene guión, se asume RUC (11). Se separa el número del DV.
    if "-" in raw_str:
        parts = raw_str.split("-")
        num = parts[0].strip()
        num_clean = "".join(filter(str.isalnum, num))
        return num_clean, 11
        
    # Eliminar cualquier carácter que no sea alfanumérico
    num_clean = "".join(filter(str.isalnum, raw_str))
    
    # Para compras, el vendedor siempre tiene RUC (11)
    if default_tipo_registro == "compra":
        return num_clean, 11
        
    # Para ventas, si la longitud es mayor o igual a 8 o comienza con 800 (empresas paraguayas), asumimos RUC (11).
    # De lo contrario, si tiene dígitos, asumimos Cédula de Identidad (12).
    if num_clean.isdigit():
        if len(num_clean) >= 8 or num_clean.startswith("80"):
            return num_clean, 11
        return num_clean, 12
        
    return num_clean, 11

def format_invoice_number(nro: Optional[str]) -> str:
    """Formatea el número de factura a la estructura obligatoria ###-###-#######."""
    if not nro:
        return ""
    
    # Limpiar y extraer solo dígitos
    digits = "".join(filter(str.isdigit, str(nro)))
    
    if len(digits) == 13:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:13]}"
    elif len(digits) > 0:
        clean_str = str(nro).strip()
        parts = [p.strip() for p in clean_str.split("-") if p.strip()]
        if len(parts) == 3:
            try:
                p1 = parts[0].zfill(3)
                p2 = parts[1].zfill(3)
                p3 = parts[2].zfill(7)
                return f"{p1}-{p2}-{p3}"
            except Exception:
                pass
    return str(nro).strip()

def map_tipo_comprobante(tipo_str: Optional[str]) -> int:
    """Mapea la descripción del comprobante al código numérico de la SET (Tabla 4)."""
    if not tipo_str:
        return 109 # Por defecto Factura
        
    t_lower = tipo_str.lower()
    if "nota de crédito" in t_lower or "nota de credito" in t_lower or "credito" in t_lower or "crédito" in t_lower:
        return 110
    elif "nota de débito" in t_lower or "nota de debito" in t_lower or "debito" in t_lower or "débito" in t_lower:
        return 111
    elif "autofactura" in t_lower:
        return 101
    elif "boleta resimple" in t_lower or "resimple" in t_lower:
        return 104
    elif "boleta de venta" in t_lower:
        return 103
    elif "ticket" in t_lower:
        return 112
    elif "despacho" in t_lower:
        return 107
    
    return 109 # Por defecto Factura

def map_condicion(condicion_str: Optional[str]) -> int:
    """Mapea la condición a 1 (Contado) o 2 (Crédito)."""
    if not condicion_str:
        return 1 # Default Contado
        
    c_lower = condicion_str.lower()
    if "crédito" in c_lower or "credito" in c_lower or "2" in c_lower:
        return 2
    return 1 # Contado

def pdf_to_image(pdf_input, is_bytes: bool = False, page_num: int = 0) -> Image.Image:
    """Convierte una página específica de un PDF a una imagen de alta resolución usando PyMuPDF."""
    if is_bytes:
        doc = fitz.open("pdf", pdf_input)
    else:
        doc = fitz.open(pdf_input)
    page = doc.load_page(page_num)
    
    # Renderizar a alta resolución (zoom 2x es generalmente suficiente)
    zoom_x = 2.0
    zoom_y = 2.0
    mat = fitz.Matrix(zoom_x, zoom_y)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    # Convertir a imagen PIL
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img

def image_to_base64(img: Image.Image) -> str:
    """Convierte una imagen PIL a base64."""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def extract_invoice_data(img_base64: str, tipo_factura: str = "compra") -> InvoiceData:
    """Envía la imagen a Gemini usando Langchain y extrae el JSON estructurado."""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview",
        temperature=0.0
    )
    
    # Forzar el output a nuestra clase Pydantic
    structured_llm = llm.with_structured_output(InvoiceData)
    
    contexto = (
        "Esta es una factura de VENTA (emitida por nosotros). Extrae el RUC del CLIENTE (comprador) en 'ruc_cliente' "
        "y su nombre/razón social en 'nombre_cliente'."
        if tipo_factura == "venta" else
        "Esta es una factura de COMPRA (recibida por nosotros). Extrae el RUC del VENDEDOR (emisor) en 'ruc_vendedor' "
        "y su nombre/razón social en 'nombre_vendedor'. También extrae el RUC del CLIENTE (comprador) en 'ruc_cliente'."
    )
    
    prompt_text = (
        "Actúa como un experto en contabilidad paraguaya. Analiza la imagen de la factura adjunta "
        "y extrae la información requerida estrictamente según el esquema JSON especificado. Si un dato no está presente, devuelve null.\n"
        f"CONTEXTO IMPORTANTE: {contexto}\n"
        "Asegúrate de extraer:\n"
        "- 'condicion_operacion': Debe ser 'Contado' o 'Crédito'. Busca términos como 'Condición de venta', 'Contado', 'Crédito'.\n"
        "- 'tipo_comprobante': Determina si es 'Factura', 'Nota de Crédito', 'Autofactura', 'Boleta de Venta' o 'Ticket'.\n"
        "- Si el comprobante es una Nota de Crédito o Débito, busca y extrae en 'nro_comprobante_asociado' y 'timbrado_asociado' los datos de la factura original que se está afectando.\n"
        "Regla de oro: No incluyas texto explicativo, solo el objeto JSON puro estructurado."
    )
    
    # Crear mensaje multimodal para Langchain
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
            }
        ]
    )
    
    response = structured_llm.invoke([message])
    return response

def process_single_invoice(img_b64: str, file_name: str, tipo_factura: str = "compra") -> dict:
    """Extrae y valida los datos de una sola factura, devolviendo un diccionario estructurado."""
    invoice_data = extract_invoice_data(img_b64, tipo_factura)
    
    try:
        data_dict = invoice_data.model_dump()
    except AttributeError:
        data_dict = invoice_data.dict()
    
    gravado_10 = data_dict.get('gravado_10') or 0.0
    gravado_5 = data_dict.get('gravado_5') or 0.0
    exenta = data_dict.get('exenta') or 0.0
    monto_total = data_dict.get('monto_total') or 0.0
    
    suma_parciales = gravado_10 + gravado_5 + exenta
    
    is_valid = False
    if abs(suma_parciales - monto_total) <= 1.0:
        is_valid = True
        
    data_dict['suma_validada'] = is_valid
    data_dict['archivo_origen'] = file_name
    
    # Procesar campos para Marangatu
    tipo_reg = 2 if tipo_factura == "compra" else 1
    ruc_raw = data_dict.get('ruc_vendedor') if tipo_factura == "compra" else data_dict.get('ruc_cliente')
    nombre_raw = data_dict.get('nombre_vendedor') if tipo_factura == "compra" else data_dict.get('nombre_cliente')
    
    identificacion_clean, tipo_id = clean_ruc_and_get_type(ruc_raw, tipo_factura)
    
    data_dict['tipo_registro_marangatu'] = tipo_reg
    data_dict['tipo_identificacion_marangatu'] = tipo_id
    data_dict['identificacion_marangatu'] = identificacion_clean
    data_dict['nombre_marangatu'] = str(nombre_raw or "").strip()
    data_dict['tipo_comprobante_marangatu'] = map_tipo_comprobante(data_dict.get('tipo_comprobante'))
    data_dict['nro_comprobante_marangatu'] = format_invoice_number(data_dict.get('nro_factura'))
    data_dict['condicion_marangatu'] = map_condicion(data_dict.get('condicion_operacion'))
    data_dict['nro_comprobante_asociado_marangatu'] = format_invoice_number(data_dict.get('nro_comprobante_asociado'))
    data_dict['es_factura_electronica'] = data_dict.get('es_factura_electronica', False)
    
    return data_dict



def process_invoices(input_folder: str = "input_facturas", output_excel: str = "facturas_procesadas.xlsx", tipo_factura: str = "compra"):
    """Procesa todas las facturas en la carpeta de entrada y las guarda en Excel."""
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        print(f"Carpeta '{input_folder}' creada. Por favor, coloca tus facturas PDF aquí.")
        return

    extensions = ("*.pdf", "*.png", "*.jpg", "*.jpeg")
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(input_folder, ext)))
        
    if not files:
        print(f"No se encontraron archivos (PDF, PNG, JPG) en '{input_folder}'.")
        return

    results = []
    
    for file_path in files:
        print(f"Procesando: {file_path}...")
        try:
            ext_lower = os.path.splitext(file_path)[1].lower()
            if ext_lower == '.pdf':
                # Procesar todas las páginas del PDF
                doc = fitz.open(file_path)
                num_pages = len(doc)
                doc.close()
                
                for page_num in range(num_pages):
                    img = pdf_to_image(file_path, is_bytes=False, page_num=page_num)
                    img_b64 = image_to_base64(img)
                    
                    nombre_mostrar = f"{os.path.basename(file_path)} (Pág. {page_num+1})" if num_pages > 1 else os.path.basename(file_path)
                    
                    data_dict = process_single_invoice(img_b64, nombre_mostrar, tipo_factura)
                    
                    # Filtrar páginas que no parecen facturas
                    if data_dict.get('nro_factura') is None and data_dict.get('monto_total') is None:
                        continue
                        
                    results.append(data_dict)
                    print(f"  -> Pág. {page_num+1}: Éxito. Validado (Suma correcta): {data_dict['suma_validada']}")
            else:
                # 1. Cargar imagen directamente
                img = Image.open(file_path).convert("RGB")
                img_b64 = image_to_base64(img)
                
                # 2. Extraer y validar datos
                data_dict = process_single_invoice(img_b64, os.path.basename(file_path), tipo_factura)
                
                results.append(data_dict)
                print(f"  -> Éxito. Validado (Suma correcta): {data_dict['suma_validada']}")
            
        except Exception as e:
            print(f"  -> Error procesando {file_path}: {e}")
            
    if results:
        # 4. Exportar a Excel
        df_new = pd.DataFrame(results)
        
        # Reordenar columnas para mejor lectura
        ruc_col = 'ruc_cliente' if tipo_factura == 'venta' else 'ruc_vendedor'
        cols_order = ['archivo_origen', 'nro_factura', ruc_col, 'fecha', 'timbrado', 
                      'monto_total', 'gravado_10', 'gravado_5', 'exenta', 'suma_validada']
        
        # Asegurar que todas las columnas existan en el DataFrame
        for c in cols_order:
            if c not in df_new.columns:
                df_new[c] = None
        df_new = df_new[cols_order]
        
        if os.path.exists(output_excel):
            print(f"Actualizando el archivo existente: {output_excel}")
            try:
                # Leer Excel existente y hacer append
                df_existing = pd.read_excel(output_excel)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined.to_excel(output_excel, index=False)
            except Exception as e:
                print(f"Error al intentar actualizar el Excel. Guardando resultado parcial: {e}")
                df_new.to_excel("recuperacion_" + output_excel, index=False)
        else:
            print(f"Creando nuevo archivo Excel: {output_excel}")
            df_new.to_excel(output_excel, index=False)
            
        print("Procesamiento finalizado con éxito.")

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: La variable de entorno GEMINI_API_KEY no está configurada.")
        print("Por favor, renombra .env.example a .env e inserta tu clave.")
    else:
        process_invoices()
