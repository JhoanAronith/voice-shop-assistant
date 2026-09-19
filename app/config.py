import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b-instruct")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_LANG = os.getenv("WHISPER_LANG", "es")
DB_PATH = os.getenv("DB_PATH", "/data/assistant.db")
STORE_NAME = os.getenv("STORE_NAME", "TecnoStore")

CATEGORIES = {
    "consulta_producto": "Consulta de producto",
    "precio": "Precio y ofertas",
    "stock": "Disponibilidad",
    "compra": "Intención de compra",
    "envio": "Envío y entrega",
    "garantia": "Garantía y devolución",
    "soporte_tecnico": "Soporte técnico",
    "reclamo": "Reclamo",
    "otro": "Otro",
}

TTS_ENABLED = os.getenv("TTS_ENABLED", "1") not in ("0", "false", "False")
PIPER_VOICE = os.getenv("PIPER_VOICE", "es_ES-davefx-medium")
PIPER_VOICE_URL = os.getenv(
    "PIPER_VOICE_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
)
