"""Ollama client: assistant replies and conversation classification."""
import json
import re

import httpx

from catalog import as_context
from config import CATEGORIES, LLM_MODEL, OLLAMA_URL, STORE_NAME


def system_prompt(query: str = "") -> str:
    """Instructions after the data: the rules stay close to the answer."""
    return f"""Eres el asistente de compras de {STORE_NAME}, una tienda de productos tecnológicos.

{as_context(query)}

REGLAS:
- Responde en español, en 2 a 4 frases, con datos concretos del contexto (SKU, precio en S/, stock, garantía).
- Medios de pago, envíos, promociones y sucursales se responden citando las secciones de arriba tal como están.
- Si el producto no está en el catálogo, dilo y ofrece la alternativa más cercana que sí esté.
- Si el stock es 0, indícalo y propón reposición o un sustituto.
- No inventes precios, plazos, medios de pago ni promociones que no estén en el contexto."""

CLASSIFY_PROMPT = """Clasifica el objetivo de la conversación de un cliente de una tienda de tecnología.
Categorías válidas: {cats}
Responde SOLO con JSON: {{"category": "<categoria>", "confidence": <0..1>, "summary": "<resumen de max 12 palabras>"}}"""

KEYWORDS = {
    "precio": ("precio", "cuesta", "cuánto", "cuanto", "oferta", "descuento", "cuotas"),
    "stock": ("stock", "disponible", "hay", "quedan", "inventario"),
    "envio": ("envío", "envio", "entrega", "delivery", "llega", "despacho"),
    "garantia": ("garantía", "garantia", "devolución", "devolucion", "cambio", "factura"),
    "soporte_tecnico": ("no funciona", "falla", "error", "soporte", "reparar", "lento"),
    "reclamo": ("reclamo", "queja", "molesto", "demora", "nunca llegó", "nunca llego"),
    "compra": ("comprar", "quiero llevar", "reservar", "pedido", "pagar"),
    "consulta_producto": ("laptop", "monitor", "teclado", "audífonos", "audifonos", "celular", "smartphone", "tarjeta"),
}


def health() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def _chat(messages: list[dict], temperature: float = 0.3, timeout: float = 180) -> str:
    r = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 300},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def reply(history: list[dict]) -> str:
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    messages = [{"role": "system", "content": system_prompt(last_user)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-8:]]
    return _chat(messages)


def _fallback_category(text: str) -> tuple[str, float]:
    low = text.lower()
    for category, words in KEYWORDS.items():
        if any(w in low for w in words):
            return category, 0.4
    return "otro", 0.2


def classify(history: list[dict]) -> dict:
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    prompt = CLASSIFY_PROMPT.format(cats=", ".join(CATEGORIES))
    try:
        raw = _chat(
            [{"role": "system", "content": prompt}, {"role": "user", "content": transcript}],
            temperature=0.0,
            timeout=60,
        )
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
        category = data.get("category", "otro")
        if category not in CATEGORIES:
            raise ValueError(category)
        return {
            "category": category,
            "confidence": float(data.get("confidence", 0.5)),
            "summary": str(data.get("summary", ""))[:120],
        }
    except Exception:
        user_text = " ".join(m["content"] for m in history if m["role"] == "user")
        category, confidence = _fallback_category(user_text)
        return {"category": category, "confidence": confidence, "summary": user_text[:120]}


def stream_reply(history: list[dict]):
    """Yield the answer token by token so the UI can render it as it arrives."""
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    messages = [{"role": "system", "content": system_prompt(last_user)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-8:]]
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": 0.3, "num_predict": 300},
    }
    with httpx.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload, timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break
