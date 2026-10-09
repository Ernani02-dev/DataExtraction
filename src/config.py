import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://sa:123456@localhost:27017/extraction_db")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Configuración de IA
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()
OPENAI_API_KEY = os.environ.get("CHATGPT_KEY") or os.environ.get("OPENAI_API_KEY")

if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Extraer el nombre de la DB
parsed_db_name = MONGODB_URI.split('/')[-1].split('?')[0]
DB_NAME = parsed_db_name if parsed_db_name else "extraction_db"
