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
    nro_factura: Optional[str] = Field(description="Número identificador de la factura.")
    ruc_vendedor: Optional[str] = Field(description="RUC de la empresa que vende o emite la factura.")
    ruc_cliente: Optional[str] = Field(description="RUC del cliente que compra o a quien va dirigida la factura.")
    fecha: Optional[str] = Field(description="Fecha de emisión en formato DD/MM/YYYY.")
    timbrado: Optional[str] = Field(description="Número de timbrado legal.")
    monto_total: Optional[float] = Field(description="Suma total de la factura.")
    gravado_10: Optional[float] = Field(description="Monto imponible al 10%.")
    gravado_5: Optional[float] = Field(description="Monto imponible al 5%.")
    exenta: Optional[float] = Field(description="Monto de artículos o servicios exentos de impuestos.")

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
        "Esta es una factura de VENTA. Extrae el RUC del CLIENTE (a quien le facturamos) en 'ruc_cliente'." 
        if tipo_factura == "venta" else 
        "Esta es una factura de COMPRA. Extrae el RUC del VENDEDOR (quien emite la factura) en 'ruc_vendedor'."
    )
    
    prompt_text = (
        "Actúa como un experto en contabilidad. Analiza la imagen de la factura adjunta "
        "y extrae la siguiente información estrictamente en formato JSON. Si un dato no está presente, devuelve null.\n"
        f"CONTEXTO IMPORTANTE: {contexto}\n"
        "Regla de oro: No incluyas texto explicativo, solo el objeto JSON puro."
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
                # 1. Convertir primera página a imagen
                img = pdf_to_image(file_path, is_bytes=False)
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
