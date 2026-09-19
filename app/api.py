"""HTTP API for the voice assistant: transcription, streaming answers, history, stats."""
import json
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import catalog
import db
import llm
import stt
import tts
from config import CATEGORIES, STORE_NAME

WEB_DIR = Path(__file__).with_name("web")

app = FastAPI(title=f"{STORE_NAME} · Asistente", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    db.init()
    db.prune_empty()


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    source: str = "text"
    language: str | None = None
    audio_seconds: float | None = None


class SpeakRequest(BaseModel):
    text: str


@app.get("/api/config")
def read_config() -> dict:
    return {"store": STORE_NAME, "categories": CATEGORIES, "tts": tts.available()}


@app.post("/api/speak")
def speak(request: SpeakRequest) -> Response:
    """Return the answer as a WAV clip synthesized offline by Piper."""
    if not tts.available():
        raise HTTPException(status_code=503, detail="Voz deshabilitada")
    try:
        audio = tts.speak(request.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No pude generar la voz ({exc})") from exc
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health() -> dict:
    return {"model": llm.health()}


@app.get("/api/conversations")
def list_conversations() -> list[dict]:
    return [
        {
            "id": row["id"],
            "title": (row["summary"] or row["first_message"] or "Conversación").strip(),
            "category": row["category"],
            "category_label": CATEGORIES.get(row["category"], row["category"]),
            "updated_at": row["updated_at"],
        }
        for row in db.recent_conversations()
    ]


@app.get("/api/conversations/{conversation_id}")
def read_conversation(conversation_id: int) -> dict:
    messages = db.history(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"id": conversation_id, "messages": messages}


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def remove_conversation(conversation_id: int) -> None:
    db.delete_conversation(conversation_id)


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio vacío")
    suffix = Path(audio.filename or "clip.webm").suffix or ".webm"
    return stt.transcribe(payload, suffix=suffix)


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    """Stream the answer as server-sent events, then persist and classify it."""
    text = request.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Mensaje vacío")

    conversation_id = request.conversation_id or db.start_conversation("web")
    db.add_message(
        conversation_id,
        "user",
        text,
        source=request.source,
        language=request.language,
        audio_seconds=request.audio_seconds,
    )
    history = db.history(conversation_id)

    def event(name: str, data: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def stream():
        yield event("start", {"conversation_id": conversation_id})
        parts: list[str] = []
        started = time.perf_counter()
        try:
            for chunk in llm.stream_reply(history):
                parts.append(chunk)
                yield event("token", {"text": chunk})
        except Exception as exc:
            yield event("error", {"detail": f"No pude responder ahora mismo ({exc})."})
            return

        reply = "".join(parts).strip()
        latency_ms = int((time.perf_counter() - started) * 1000)
        db.add_message(conversation_id, "assistant", reply, latency_ms=latency_ms)
        result = llm.classify(history + [{"role": "assistant", "content": reply}])
        db.set_classification(
            conversation_id, result["category"], result["confidence"], result["summary"]
        )
        yield event(
            "done",
            {
                "conversation_id": conversation_id,
                "category": result["category"],
                "category_label": CATEGORIES.get(result["category"], result["category"]),
                "title": result["summary"] or text,
            },
        )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/stats")
def read_stats(days: int = 14) -> dict:
    raw = db.stats(days=min(max(days, 1), 90))
    texts = raw.pop("user_texts")
    totals = raw["totals"]
    conversations = totals["conversations"] or 0
    messages = totals["messages"] or 0

    return {
        **raw,
        "totals": {
            "conversations": conversations,
            "messages": messages,
            "user_messages": totals["user_messages"] or 0,
            "audio_messages": totals["audio_messages"] or 0,
            "audio_minutes": round((totals["audio_seconds"] or 0) / 60, 1),
            "avg_latency_ms": int(totals["avg_latency_ms"] or 0),
            "avg_confidence": round(totals["avg_confidence"] or 0, 2),
            "messages_per_conversation": round(messages / conversations, 1) if conversations else 0,
        },
        "categories": [
            {
                **row,
                "label": CATEGORIES.get(row["category"], row["category"]),
                "share": round(100 * row["total"] / conversations) if conversations else 0,
                "confidence": round(row["confidence"] or 0, 2),
            }
            for row in raw["categories"]
        ],
        "recent": [
            {
                **row,
                "label": CATEGORIES.get(row["category"], row["category"]),
                "title": (row["summary"] or row["first_message"] or "Conversación").strip(),
                "confidence": round(row["confidence"] or 0, 2),
            }
            for row in raw["recent"]
        ],
        "products": catalog.demand(texts),
        "inventory": catalog.inventory(),
        "days": min(max(days, 1), 90),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/report")
def report() -> FileResponse:
    return FileResponse(WEB_DIR / "report.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
