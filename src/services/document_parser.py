import io
import base64
import fitz  # PyMuPDF
from PIL import Image

def pdf_to_image(pdf_input, is_bytes: bool = False, page_num: int = 0) -> Image.Image:
    """Convierte una página de un PDF a imagen. Acepta un path, bytes o un objeto fitz.Document ya abierto."""
    doc = None
    if isinstance(pdf_input, fitz.Document):
        doc = pdf_input
    elif is_bytes:
        doc = fitz.open("pdf", pdf_input)
    else:
        doc = fitz.open(pdf_input)
        
    page = doc.load_page(page_num)
    
    # Zoom 2.0x
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Si lo abrimos aquí (no se pasó un Document), lo cerramos
    if not isinstance(pdf_input, fitz.Document):
        doc.close()
        
    return img

def image_to_base64(img: Image.Image) -> str:
    """Convierte una imagen PIL a base64 con compresión para reducir latencia de red."""
    buffered = io.BytesIO()
    # Guardar con calidad reducida pero suficiente para OCR (ahorra ~50% de payload)
    img.save(buffered, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")
