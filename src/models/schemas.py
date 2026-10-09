from typing import Optional
from pydantic import BaseModel, Field, create_model

# Se mantiene InvoiceData estático por si se necesita fallback o retrocompatibilidad
class InvoiceData(BaseModel):
    """Esquema de datos por defecto (estático)."""
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
    es_factura_electronica: Optional[bool] = Field(description="Verdadero si es una factura electrónica. Falso si es preimpresa o autoimpresor.")

import json
from functools import lru_cache

@lru_cache(maxsize=32)
def _create_dynamic_model_cached(schema_def_str: str):
    schema_def = json.loads(schema_def_str)
    fields = {}
    for field in schema_def.get("fields", []):
        field_type = str if field.get("type") == "string" else float if field.get("type") == "number" else str
        fields[field["name"]] = (Optional[field_type], Field(description=field.get("description", "")))
    
    return create_model(schema_def.get("name", "DynamicSchema"), **fields)

def create_dynamic_model(schema_def: dict):
    """Crea un modelo Pydantic dinámicamente, utilizando caché interno para mejor rendimiento."""
    schema_def_str = json.dumps(schema_def, default=str, sort_keys=True)
    return _create_dynamic_model_cached(schema_def_str)
