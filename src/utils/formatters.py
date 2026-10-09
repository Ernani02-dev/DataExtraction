from typing import Optional, Tuple

def clean_ruc_and_get_type(ruc_raw: Optional[str], default_tipo_registro: str) -> Tuple[str, int]:
    """Limpia el RUC o Cédula y devuelve el número sin DV y el tipo de identificación (11=RUC, 12=Cédula, 15=Sin Nombre)."""
    if not ruc_raw or str(ruc_raw).strip().lower() in ["null", "none", "sin nombre", ""]:
        return "", 15
    
    raw_str = str(ruc_raw).strip()
    
    if "-" in raw_str:
        parts = raw_str.split("-")
        num = parts[0].strip()
        num_clean = "".join(filter(str.isalnum, num))
        return num_clean, 11
        
    num_clean = "".join(filter(str.isalnum, raw_str))
    
    if default_tipo_registro == "compra":
        return num_clean, 11
        
    if num_clean.isdigit():
        if len(num_clean) >= 8 or num_clean.startswith("80"):
            return num_clean, 11
        return num_clean, 12
        
    return num_clean, 11


def format_invoice_number(nro: Optional[str]) -> str:
    """Formatea el número de factura a la estructura obligatoria ###-###-#######."""
    if not nro:
        return ""
    
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
