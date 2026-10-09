import pandas as pd
import io

def generate_excel_from_profile(records: list, profile: dict) -> bytes:
    """Genera un archivo Excel basado en un perfil de exportación y registros extraídos."""
    columns_config = profile.get("columns", [])
    
    # Preparar filas
    rows = []
    for record in records:
        row = {}
        for col in columns_config:
            header = col.get("excel_header", "Unknown")
            source_type = col.get("source_type")
            
            if source_type == "fixed":
                row[header] = col.get("value", "")
            elif source_type == "extracted":
                source_field = col.get("source_field")
                # Obtener el dato del diccionario extraído
                row[header] = record.get(source_field, "")
            else:
                row[header] = ""
                
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    # Exportar a Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    return output.getvalue()
