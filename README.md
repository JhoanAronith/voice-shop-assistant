# Asistente de voz — tienda de tecnología

[![CI](https://github.com/JhoanAronith/voice-shop-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/JhoanAronith/voice-shop-assistant/actions/workflows/ci.yml)

FastAPI + faster-whisper (STT) + Ollama (LLM) + SQLite, con frontend propio en HTML/CSS/JS sin
build step. El usuario graba un audio, el backend lo transcribe, responde en streaming con datos del
catálogo y guarda la conversación clasificada por categoría.

## Ejecutar

```bash
docker compose up --build
```

Abrir http://localhost:8000 para el chat y http://localhost:8000/report para el panel.
La primera vez se descargan el modelo de lenguaje (~1 GB) y el modelo
Whisper (~75 MB para `base`); quedan en volúmenes de Docker y no se repiten.

## Automatizaciones (n8n)

`docker compose up` también levanta n8n en http://localhost:5678. La primera vez pide crear la cuenta
de propietario (es local). Los flujos y credenciales se guardan en el volumen `n8n_data`.

Desde los nodos HTTP Request de n8n, los otros servicios se alcanzan por su nombre en la red de Docker:

| Servicio | URL desde n8n |
|---|---|
| API del asistente | `http://app:8000/api/...` (ej. `/api/report`, `/api/stats`) |
| Ollama | `http://ollama:11434` |

Los webhooks quedan en `http://localhost:5678/webhook/...`. Solo para levantar n8n:
`docker compose up -d n8n`.

## Pruebas

```bash
docker compose --profile test run --rm tests
```

Corre `pytest` sobre `tests/` en la imagen de la app, con una SQLite temporal por prueba y Ollama,
Whisper y Piper simulados (no hace falta tener los modelos). Unitarias: `test_catalog`, `test_llm`,
`test_db`, `test_tts`. Funcionales (endpoints HTTP de punta a punta): `test_api`.

## Integración continua

`.github/workflows/ci.yml` corre en cada push a `master`, en cada pull request y a mano desde la
pestaña Actions:

| Job | Qué valida |
|---|---|
| Lint | `ruff check` (reglas en `ruff.toml`), sintaxis de `app/web/*.js` y que `docker-compose.yml` sea válido |
| Pruebas | `pytest tests` en Python 3.11 con las dependencias de `requirements.txt` |
| Imagen Docker | Construye la imagen y la arranca: `/api/health`, `/`, `/report` y `/api/stats` deben responder |

La imagen no se publica en ningún registro; el despliegue continuo queda para cuando haya servidor.

## Configuración

Variables (ver `.env.example`, copiar a `.env` para sobreescribir):

| Variable | Default | Uso |
|---|---|---|
| `LLM_MODEL` | `qwen2.5:1.5b-instruct` | Modelo Ollama |
| `WHISPER_MODEL` | `base` | `tiny`, `base`, `small`, `medium` |
| `WHISPER_LANG` | `es` | Idioma forzado; vacío = autodetección |
| `TTS_ENABLED` | `1` | `0` desactiva la voz y oculta el botón |
| `PIPER_VOICE` | `es_ES-davefx-medium` | Voz Piper; cambiarla requiere ajustar `PIPER_VOICE_URL` |
| `STORE_NAME` | `TecnoStore` | Nombre mostrado |
| `DB_PATH` | `/data/assistant.db` | SQLite dentro del contenedor |

## API

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/api/health` | Disponibilidad del LLM |
| `GET` | `/api/config` | Nombre de tienda y catálogo de categorías |
| `GET` | `/api/conversations` | Historial, más recientes primero |
| `GET` | `/api/conversations/{id}` | Mensajes de una conversación |
| `DELETE` | `/api/conversations/{id}` | Borrar una conversación |
| `POST` | `/api/transcribe` | `multipart/form-data` con campo `audio` → `{text, language, duration}` |
| `POST` | `/api/chat` | Respuesta en server-sent events: `start`, `token`, `done` (o `error`) |
| `GET` | `/api/stats?days=N` | Agregados del panel (rango de 1 a 90 días) |
| `GET` | `/api/report?days=N` | Una fila plana por conversación para hojas de cálculo (rango de 1 a 365 días) |
| `POST` | `/api/speak` | `{"text"}` → clip WAV generado offline por Piper |

## Panel (`/report`)

Seis indicadores (conversaciones, mensajes, mensajes por conversación, consultas por voz y minutos
de audio, confianza media de la clasificación, tiempo medio de respuesta) más seis vistas:
objetivo de la conversación por categoría, canal de entrada (voz frente a texto), actividad diaria,
franja horaria, menciones por producto (en rojo lo que se pide y está sin stock) e inventario en
riesgo. Cierra con las 12 conversaciones más recientes. Rango de 7, 14 o 30 días; se refresca cada
30 s.

## Base de datos

`data/assistant.db`, dos tablas:

- `conversations` — `session_id`, `category`, `confidence`, `summary`, timestamps.
- `messages` — `role`, `content`, `source` (`audio` / `text`), `language`, `audio_seconds`, `latency_ms`.

Categorías: `consulta_producto`, `precio`, `stock`, `compra`, `envio`, `garantia`, `soporte_tecnico`,
`reclamo`, `otro`. Las asigna el LLM en JSON al cerrar cada turno; si el JSON falla, cae a
coincidencia por palabras clave.

```bash
docker compose exec app python -c "import db;print(db.recent_conversations(5))"
```

## Estructura

```
app/
  api.py       endpoints FastAPI y streaming SSE
  stt.py       faster-whisper (CPU, int8)
  tts.py       Piper: síntesis de voz offline con caché en memoria
  llm.py       cliente Ollama: respuesta, streaming y clasificación
  db.py        esquema y consultas SQLite
  catalog.py   catálogo (22 SKU), datos de tienda y selección de contexto por consulta
  config.py    variables de entorno
  web/         frontend: chat (index.html, app.js, styles.css),
               panel (report.html, report.js, report.css) y tokens.css compartido
```

## Notas

- Todo corre en CPU; sin GPU ni PyTorch.
- El micrófono del navegador requiere `localhost` o HTTPS (`MediaRecorder` + `getUserMedia`).
- Tema claro/oscuro con detección del sistema y conmutador manual guardado en `localStorage`.
- `catalog.py` es la fuente de verdad del contexto: reemplazarlo por una consulta real al ERP cuando aplique.

## Contexto enviado al modelo

`catalog.py` no manda las 22 fichas en cada turno: filtra los productos que la consulta menciona
(por término, categoría o marca) y solo las secciones de tienda en juego (pagos, envíos, sucursales,
contacto, promociones, políticas). Si la consulta no nombra ningún producto, envía un resumen por
categoría en lugar del catálogo completo. Esto baja el prompt de ~4300 a ~1400 caracteres y la
respuesta de ~45 s a ~13 s con `qwen2.5:1.5b-instruct`, además de evitar que el modelo pierda datos
en un contexto largo.

## Llevarlo a otra máquina

### Con internet en el destino

1. Copiar la carpeta del proyecto sin `data/` (ahí vive el historial de este equipo).
2. Instalar Docker Desktop (Windows/macOS) o Docker Engine + plugin compose (Linux).
3. `docker compose up --build -d`
4. Abrir http://localhost:8000.

La primera vez se descargan el modelo de lenguaje (~1 GB, al levantar), Whisper (~75 MB, al primer
audio) y la voz Piper (~63 MB, al primer clic en el altavoz). Reserva ~6 GB de disco y 4 GB de RAM.

### Sin internet en el destino

En este equipo:

```bash
docker save -o images.tar voice-shop-assistant-app:latest ollama/ollama:latest alpine:latest
docker run --rm -v voice-shop-assistant_ollama:/from -v "$PWD:/to" alpine tar czf /to/vol-ollama.tgz -C /from .
docker run --rm -v voice-shop-assistant_whisper:/from -v "$PWD:/to" alpine tar czf /to/vol-models.tgz -C /from .
```

En el destino, junto a la carpeta del proyecto:

```bash
docker load -i images.tar
docker volume create voice-shop-assistant_ollama
docker volume create voice-shop-assistant_whisper
docker run --rm -v voice-shop-assistant_ollama:/to -v "$PWD:/from" alpine tar xzf /from/vol-ollama.tgz -C /to
docker run --rm -v voice-shop-assistant_whisper:/to -v "$PWD:/from" alpine tar xzf /from/vol-models.tgz -C /to
docker compose up -d
```

Sin `--build`, para que use la imagen cargada. El servicio `model-init` detecta que el modelo ya
está en el volumen y no intenta descargarlo. El nombre de los volúmenes lleva el nombre de la
carpeta como prefijo: si la renombras, ajusta los comandos o exporta `COMPOSE_PROJECT_NAME`.

### Micrófono fuera de localhost

`getUserMedia` solo funciona en `localhost` o con HTTPS: si entras desde otro equipo por IP
(`http://192.168.x.x:8000`) el chat y el panel cargan, pero el botón de grabar queda inhabilitado.
Opciones: usar el navegador en la misma máquina, poner un proxy con TLS delante, o en Chrome
habilitar el origen en `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
