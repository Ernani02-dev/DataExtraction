import os
from dotenv import load_dotenv

load_dotenv()

# ========================================================
# BASE DE DATOS: POSTGRESQL 16 (SQLAlchemy 2.0 + JSONB)
# ========================================================
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres_secret_123@localhost:5432/files_processor_db"
)

# Configuración Legacy MongoDB (por compatibilidad)
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://sa:123456@localhost:27017/extraction_db")

# Proveedor de Inteligencia Artificial
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()
OPENAI_API_KEY = os.environ.get("CHATGPT_KEY") or os.environ.get("OPENAI_API_KEY")

if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Extraer el nombre de la base de datos
parsed_db_name = DATABASE_URL.split('/')[-1].split('?')[0] if DATABASE_URL else "files_processor_db"
DB_NAME = parsed_db_name if parsed_db_name else "files_processor_db"
