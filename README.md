# 📄 FacturasAutomatizacionPro - Plataforma Inteligente de Extracción de Documentos

Plataforma SaaS para la extracción automatizada y estructurada de datos desde facturas, recibos y documentos digitales (PDF e imágenes) impulsada por Modelos de Lenguaje (Google Gemini / OpenAI), persistencia en MongoDB y procesamiento asíncrono en segundo plano mediante Celery y Redis.

---

## 🚀 Características Principales

1. **Gestión Multitenant (Empresas y Clientes)**:
   - Control de empresas/clientes con límites mensuales parametrizados de procesamiento.
   - Kill switch para suspender o reactivar empresas en tiempo real.
2. **Esquemas Dinámicos de Extracción**:
   - Diseña esquemas personalizados sin tocar código: define campos (texto, numérico, fecha) y descripciones semánticas para orientar a la IA.
3. **Mapeo y Exportación Flexible**:
   - Creación de perfiles de exportación en Excel/CSV asignando columnas personalizadas a partir de los datos extraídos.
4. **Procesamiento de Documentos**:
   - **Modo Directo**: Subida manual y visualización inmediata en tiempo real.
   - **Modo Asíncrono por Lote (.ZIP)**: Carga paquetes de cientos/miles de archivos comprimidos procesados en segundo plano con Celery + Redis, sin congelar el navegador.
5. **Panel SuperAdmin**:
   - Vista global de métricas del sistema, auditoría de lotes procesados, control de cuotas y estado de empresas.

---

## 🛠️ Requisitos Previos

- **Python 3.10 o superior**
- **MongoDB** (instancia local en puerto `27017` o clúster MongoDB Atlas)
- **Redis** (instancia local en puerto `6379` o servicio gestionado tipo Redis Cloud)
- Clave de API de **Google Gemini** o **OpenAI**

> 💡 **Tip rápido para dependencias de infraestructura:**
> Si tienes Docker instalado, puedes levantar MongoDB y Redis en segundos:
> ```bash
> docker run -d --name mongo-dev -p 27017:27017 -e MONGO_INITDB_ROOT_USERNAME=sa -e MONGO_INITDB_ROOT_PASSWORD=123456 mongo:latest
> docker run -d --name redis-dev -p 6379:6379 redis:alpine
> ```

---

## ⚙️ Instalación y Configuración

### 1. Clonar el repositorio y entrar al proyecto
```bash
git clone https://github.com/Ernani02-dev/DataExtraction.git
cd FacturasAutomatizacionPro
```

### 2. Crear y activar un entorno virtual
**En Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**En Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar las dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar las variables de entorno
Copia la plantilla `.env.example` y renómbrala a `.env`:
```bash
cp .env.example .env
```
*(En Windows PowerShell: `copy .env.example .env`)*

Edita el archivo `.env` con tus credenciales:
```env
# Conexión MongoDB
MONGODB_URI=mongodb://sa:123456@localhost:27017/extraction_db

# Conexión Redis (para Celery)
REDIS_URL=redis://localhost:6379/0

# Proveedor de IA: "gemini" o "openai"
AI_PROVIDER=gemini

# Credenciales de API
GEMINI_API_KEY=tu_api_key_aqui
# OPENAI_API_KEY=tu_api_key_aqui (si usas OpenAI)
```

---

## 🏃‍♂️ Cómo Iniciar la Aplicación

Para un funcionamiento completo (interfaz + procesamiento de lotes ZIP en segundo plano), debes iniciar **dos terminales**:

### Terminal 1: Iniciar el Worker de Celery
El worker escucha y procesa las tareas pesadas en segundo plano (descompresión de `.zip`, llamadas concurrentes a la IA y guardado en MongoDB).

- **En Windows:**
  ```powershell
  celery -A src.celery_app worker --loglevel=info -P solo
  ```
  *(Nota: en Windows el parámetro `-P solo` o `--pool=solo` es indispensable para evitar bloqueos del multiproceso de Celery).*

- **En Linux / macOS:**
  ```bash
  celery -A src.celery_app worker --loglevel=info --concurrency=4
  ```

### Terminal 2: Iniciar Streamlit (Interfaz Web)
```bash
streamlit run app.py
```
La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`.

---

## 🧭 Flujo de Uso Paso a Paso

1. **Dashboard Principal (`app.py`)**:
   - Consulta el estado general: cantidad de clientes, esquemas, perfiles y total de documentos procesados.
2. **Paso 1: Clientes / Empresas (`pages/0_Clientes.py`)**:
   - Crea una empresa (ejemplo: "Acme Corp"). El sistema asignará automáticamente una cuota mensual de documentos (por defecto 1,000) y el estado activo.
3. **Paso 2: Esquemas de Extracción (`pages/1_Esquemas.py`)**:
   - Selecciona la empresa y crea un esquema para su tipo de documento (por ejemplo: "Factura A").
   - Agrega los campos que la IA debe extraer: `numero_factura`, `fecha_emision`, `cuit_emisor`, `total`, `iva`, etc.
4. **Paso 3: Perfiles de Exportación (`pages/2_Exportacion.py`)**:
   - Define qué columnas y con qué formato deseas exportar los datos a Excel/CSV.
5. **Paso 4: Procesamiento (`pages/3_Procesador.py`)**:
   - **Subida Directa**: Arrastra 1 a 20 archivos (PDF o imágenes) para procesarlos y ver los resultados en pantalla al instante.
   - **Lotes Masivos (.ZIP)**: Sube un archivo `.zip` con cientos de facturas. El archivo se envía a Celery, se procesa en segundo plano y podrás cerrar o cambiar de pestaña en el navegador sin interrumpir el proceso. Monitorea el progreso con el botón de refrescar lotes.
6. **Paso 5: SuperAdmin (`pages/4_SuperAdmin.py`)**:
   - Accede a las métricas del sistema, ajusta los límites mensuales de cada empresa o activa/desactiva el acceso con el switch de habilitación inmediata.

---

## 📂 Estructura del Proyecto

```
FacturasAutomatizacionPro/
│
├── app.py                       # Página principal y Dashboard de bienvenida
├── requirements.txt             # Dependencias del proyecto
├── .env.example                 # Plantilla de variables de entorno
│
├── pages/                       # Módulos de la aplicación Streamlit
│   ├── 0_Clientes.py            # Gestión de empresas y cuotas
│   ├── 1_Esquemas.py            # Definición de esquemas de extracción dinámicos
│   ├── 2_Exportacion.py         # Configuración de perfiles y mapeo a Excel
│   ├── 3_Procesador.py          # Procesador directo y procesamiento ZIP con Celery
│   └── 4_SuperAdmin.py          # Dashboard de administración global y kill-switch
│
└── src/                         # Arquitectura modular desacoplada
    ├── celery_app.py            # Instancia y configuración de Celery
    ├── tasks.py                 # Tareas asíncronas en segundo plano
    ├── config.py                # Carga de variables de entorno
    ├── database/
    │   └── mongodb.py           # Capa de datos con PyMongo
    ├── models/
    │   └── schemas.py           # Modelos Pydantic para validación
    ├── services/
    │   ├── ai_extractor.py      # Integración con Google Gemini / OpenAI
    │   ├── document_parser.py   # Parseo y conversión de PDFs e imágenes (PyMuPDF)
    │   ├── exporter.py          # Generador de reportes Excel / CSV
    │   ├── llm_manager.py       # Fábrica y gestor de clientes LLM
    │   └── pipeline_orchestrator.py # Orquestador con control de cuotas y validaciones
    └── utils/
        └── formatters.py        # Utilidades de formateo
```
