from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from src.config import AI_PROVIDER
import threading

class LLMManager:
    _instance = None
    _lock = threading.Lock()
    _llm = None

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LLMManager, cls).__new__(cls)
                cls._instance._initialize_llm()
        return cls._instance

    def _initialize_llm(self):
        """Inicializa el modelo de lenguaje de forma única (Singleton)."""
        if AI_PROVIDER == "chatgpt":
            self._llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0
            )
        else:
            self._llm = ChatGoogleGenerativeAI(
                model="gemini-3.1-flash-lite",
                temperature=0.0
            )

    def get_llm(self):
        return self._llm

# Instancia global para importar fácilmente
llm_manager = LLMManager()
