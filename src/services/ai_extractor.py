from typing import Any
from langchain_core.messages import HumanMessage
from src.models.schemas import InvoiceData, create_dynamic_model
from src.utils.formatters import clean_ruc_and_get_type, format_invoice_number, map_tipo_comprobante, map_condicion
from src.services.llm_manager import llm_manager

def extract_invoice_data(img_base64: str, tipo_factura: str = "compra", schema_def: dict = None) -> Any:
    """Envía la imagen a la IA y extrae el JSON estructurado reutilizando la instancia del LLM."""
    llm = llm_manager.get_llm()
    
    # Determinar el modelo estructurado (utilizando el caché implementado)
    if schema_def:
        TargetModel = create_dynamic_model(schema_def)
    else:
        TargetModel = InvoiceData
        
    structured_llm = llm.with_structured_output(TargetModel)
    
    if schema_def:
        prompt_text = (
            f"Analiza la imagen adjunta y extrae la información requerida estrictamente "
            f"según el esquema JSON. Si un dato no está presente, devuelve null.\n"
            f"Descripción general del documento: {schema_def.get('description', '')}\n"
            "Regla de oro: No incluyas texto explicativo, solo el objeto JSON puro estructurado."
        )
    else:
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

def process_single_invoice(img_b64: str, file_name: str, tipo_factura: str = "compra", schema_def: dict = None) -> dict:
    """Extrae y valida los datos de una sola factura, devolviendo un diccionario estructurado."""
    invoice_data = extract_invoice_data(img_b64, tipo_factura, schema_def)
    
    try:
        data_dict = invoice_data.model_dump()
    except AttributeError:
        data_dict = invoice_data.dict()
    
    # Solo hacer la validación de sumas si estamos usando el modelo default y existen los campos
    if not schema_def or all(k in data_dict for k in ['gravado_10', 'gravado_5', 'exenta', 'monto_total']):
        gravado_10 = data_dict.get('gravado_10') or 0.0
        gravado_5 = data_dict.get('gravado_5') or 0.0
        exenta = data_dict.get('exenta') or 0.0
        monto_total = data_dict.get('monto_total') or 0.0
        
        suma_parciales = gravado_10 + gravado_5 + exenta
        
        is_valid = False
        if abs(suma_parciales - monto_total) <= 1.0:
            is_valid = True
            
        data_dict['suma_validada'] = is_valid
    else:
        data_dict['suma_validada'] = True # Omitir validación estricta para esquemas libres
        
    data_dict['archivo_origen'] = file_name
    
    # Procesar campos para Marangatu solo si existen en el diccionario (retrocompatibilidad)
    if 'ruc_vendedor' in data_dict or 'ruc_cliente' in data_dict:
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
