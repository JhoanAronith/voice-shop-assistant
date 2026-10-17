// Read text from a photo, entirely in the browser: pick a region, tap the lines you want, send to the chat.
(() => {
  const get = (id) => document.getElementById(id);
  const dialog = get("document-scanner");
  const text = get("scanner-text");
  const status = get("scanner-status");
  const progress = get("scanner-progress");
  const preview = get("scanner-preview");
  const use = get("scanner-use");
  const camera = get("scanner-camera");
  const upload = get("scanner-upload");
  const crop = get("scanner-crop");
  const cropTools = get("scanner-crop-tools");
  const selectionBox = get("scanner-selection");
  const linesLayer = get("scanner-lines");
  const readButton = get("scanner-read");
  const resetCrop = get("scanner-reset-crop");
  const edges = ["left", "top", "right", "bottom"];
  const cropInputs = edges.map((edge) => get(`crop-${edge}`));

  const LIBRARY_URL = "https://cdn.jsdelivr.net/npm/tesseract.js@6.0.1/dist/tesseract.min.js";
  const LANGUAGES = ["spa", "eng"]; // store text mixes Spanish with English model names
  const MAX_SIDE = 2000; // larger images only slow Tesseract down
  const MIN_SIDE = 1400; // small crops are enlarged so letters are tall enough to read
  const MIN_BOX = 0.03; // smallest selectable box, as a fraction of the image
  const GRAB_PX = 24; // reach of the edge handles on touch screens
  const AUTO_READ_DELAY_MS = 450; // wait for the user to stop adjusting before reading
  const MIN_LINE_CONFIDENCE = 45; // weaker lines (drawings, borders) start unselected
  const TIMEOUT_MS = 120000;

  const WHOLE = { left: 0, top: 0, right: 1, bottom: 1 };
  let selection = { ...WHOLE };
  let sourceImage = null;
  let previewUrl = null;
  let drag = null;
  let lines = [];
  let job = 0;
  let processing = false;
  let readTimer = null;
  let libraryPromise = null;
  let workerPromise = null;
  let onProgress = () => {};

  function message(value, error = false) {
    status.textContent = value;
    status.dataset.error = String(error);
  }

  function setProcessing(value) {
    processing = value;
    camera.disabled = upload.disabled = text.disabled = value;
    progress.hidden = !value;
    use.disabled = value || !text.value.trim();
    readButton.disabled = value || !sourceImage;
  }

  function clearPreview() {
    preview.hidden = true;
    preview.removeAttribute("src");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    sourceImage = null;
    crop.hidden = cropTools.hidden = true;
    readButton.disabled = true;
    drag = null;
    clearResult();
  }

  function clearResult() {
    lines = [];
    linesLayer.replaceChildren();
    text.value = "";
    use.disabled = true;
  }

  function loadLibrary() {
    if (window.Tesseract) return Promise.resolve(window.Tesseract);
    if (libraryPromise) return libraryPromise;
    libraryPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      const fail = () => {
        clearTimeout(timeout);
        script.remove();
        reject(new Error("No se pudo descargar el lector. Comprueba tu conexión e inténtalo de nuevo."));
      };
      const timeout = setTimeout(fail, 30000);
      script.src = LIBRARY_URL;
      script.onload = () => {
        clearTimeout(timeout);
        if (window.Tesseract) resolve(window.Tesseract);
        else fail();
      };
      script.onerror = fail;
      document.head.append(script);
    }).catch((error) => {
      libraryPromise = null;
      throw error;
    });
    return libraryPromise;
  }

  // One worker is created when the dialog opens and reused for every read, so the language data
  // is loaded once instead of on each press.
  function getWorker() {
    if (!workerPromise) {
      workerPromise = loadLibrary()
        .then((library) =>
          library.createWorker(LANGUAGES, 1, {
            logger: (event) => {
              if (event.status === "recognizing text") onProgress(event.progress);
            },
          })
        )
        .catch((error) => {
          workerPromise = null;
          throw error;
        });
    }
    return workerPromise;
  }

  function releaseWorker() {
    const pending = workerPromise;
    workerPromise = null;
    pending?.then((worker) => worker.terminate()).catch(() => {});
  }

  // --- Selection box: draw a new one, drag it, or pull its edges and corners. ---

  function showSelection() {
    const { left, top, right, bottom } = selection;
    Object.assign(selectionBox.style, {
      left: `${left * 100}%`, top: `${top * 100}%`,
      width: `${(right - left) * 100}%`, height: `${(bottom - top) * 100}%`,
    });
    cropInputs.forEach((control, index) => { control.value = Math.round(selection[edges[index]] * 100); });
  }

  // The selection changed for good: drop the old result and read the new area shortly.
  function commitSelection() {
    showSelection();
    job += 1; // a read still in flight belongs to the previous area
    setProcessing(false);
    clearResult();
    clearTimeout(readTimer);
    readTimer = setTimeout(readSelection, AUTO_READ_DELAY_MS);
    message("Ajustando…");
  }

  const isWhole = () =>
    selection.left <= 0 && selection.top <= 0 && selection.right >= 1 && selection.bottom >= 1;

  function point(event) {
    const bounds = crop.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
      y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
    };
  }

  // What is under the finger: an edge or corner to pull, the inside to move, or empty space to draw.
  function grab(event) {
    if (isWhole()) return { mode: "draw" }; // nothing to pull yet: a drag starts a fresh box
    const bounds = crop.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    const y = event.clientY - bounds.top;
    const box = {
      left: selection.left * bounds.width, right: selection.right * bounds.width,
      top: selection.top * bounds.height, bottom: selection.bottom * bounds.height,
    };
    const reachX = Math.min(GRAB_PX, (box.right - box.left) / 3);
    const reachY = Math.min(GRAB_PX, (box.bottom - box.top) / 3);
    const withinX = x >= box.left - reachX && x <= box.right + reachX;
    const withinY = y >= box.top - reachY && y <= box.bottom + reachY;
    const pulled = {
      left: withinY && Math.abs(x - box.left) <= reachX,
      right: withinY && Math.abs(x - box.right) <= reachX,
      top: withinX && Math.abs(y - box.top) <= reachY,
      bottom: withinX && Math.abs(y - box.bottom) <= reachY,
    };
    if (Object.values(pulled).some(Boolean)) return { mode: "resize", pulled };
    const inside = x > box.left && x < box.right && y > box.top && y < box.bottom;
    return { mode: inside ? "move" : "draw", pulled };
  }

  crop.addEventListener("pointerdown", (event) => {
    if (!sourceImage || !event.isPrimary || event.button !== 0) return;
    const start = point(event);
    drag = { ...grab(event), start, origin: { ...selection }, moved: false, pointerId: event.pointerId };
    crop.setPointerCapture(event.pointerId);
  });

  crop.addEventListener("pointermove", (event) => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const now = point(event);
    const dx = now.x - drag.start.x;
    const dy = now.y - drag.start.y;
    const bounds = crop.getBoundingClientRect();
    if (!drag.moved && Math.hypot(dx * bounds.width, dy * bounds.height) < 6) return; // still a tap
    drag.moved = true;

    const next = { ...drag.origin };
    if (drag.mode === "draw") {
      Object.assign(next, {
        left: Math.min(drag.start.x, now.x), right: Math.max(drag.start.x, now.x),
        top: Math.min(drag.start.y, now.y), bottom: Math.max(drag.start.y, now.y),
      });
    } else if (drag.mode === "move") {
      const width = next.right - next.left;
      const height = next.bottom - next.top;
      next.left = Math.max(0, Math.min(1 - width, next.left + dx));
      next.top = Math.max(0, Math.min(1 - height, next.top + dy));
      next.right = next.left + width;
      next.bottom = next.top + height;
    } else {
      const { pulled } = drag;
      if (pulled.left) next.left = Math.max(0, Math.min(next.right - MIN_BOX, next.left + dx));
      if (pulled.right) next.right = Math.min(1, Math.max(next.left + MIN_BOX, next.right + dx));
      if (pulled.top) next.top = Math.max(0, Math.min(next.bottom - MIN_BOX, next.top + dy));
      if (pulled.bottom) next.bottom = Math.min(1, Math.max(next.top + MIN_BOX, next.bottom + dy));
    }
    selection = next;
    showSelection();
  });

  function endDrag(event) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const finished = drag;
    drag = null;
    if (crop.hasPointerCapture(event.pointerId)) crop.releasePointerCapture(event.pointerId);

    if (event.type === "pointercancel") {
      selection = finished.origin;
      showSelection();
      return;
    }
    if (!finished.moved) {
      toggleLineAt(point(event)); // a tap picks a recognized line
      return;
    }
    if (selection.right - selection.left < MIN_BOX || selection.bottom - selection.top < MIN_BOX) {
      selection = finished.origin; // a stray tiny box is not a selection
      showSelection();
      return;
    }
    commitSelection();
  }
  crop.addEventListener("pointerup", endDrag);
  crop.addEventListener("pointercancel", endDrag);

  resetCrop.onclick = () => {
    selection = { ...WHOLE };
    commitSelection();
  };
  cropInputs.forEach((control, index) => {
    control.oninput = () => {
      selection[edges[index]] = Number(control.value) / 100;
      if (index === 0) selection.left = Math.min(selection.left, selection.right - MIN_BOX);
      if (index === 1) selection.top = Math.min(selection.top, selection.bottom - MIN_BOX);
      if (index === 2) selection.right = Math.max(selection.right, selection.left + MIN_BOX);
      if (index === 3) selection.bottom = Math.max(selection.bottom, selection.top + MIN_BOX);
      commitSelection();
    };
  });

  // --- Recognized lines drawn over the photo; tapping one includes or drops it. ---

  function textFromLines() {
    const chosen = lines.filter((line) => line.on);
    return chosen
      .map((line, index) => {
        const previous = chosen[index - 1];
        const gap = previous && previous.paragraph !== line.paragraph ? "\n\n" : previous ? "\n" : "";
        return gap + line.text;
      })
      .join("");
  }

  function paintLines() {
    linesLayer.replaceChildren(
      ...lines.map((line) => {
        const box = document.createElement("div");
        box.className = `scan-line${line.on ? "" : " off"}`;
        Object.assign(box.style, {
          left: `${line.box.left * 100}%`, top: `${line.box.top * 100}%`,
          width: `${(line.box.right - line.box.left) * 100}%`, height: `${(line.box.bottom - line.box.top) * 100}%`,
        });
        line.node = box;
        return box;
      })
    );
  }

  function toggleLineAt({ x, y }) {
    const hit = lines.find(
      (line) => x >= line.box.left && x <= line.box.right && y >= line.box.top && y <= line.box.bottom
    );
    if (!hit || processing) return;
    hit.on = !hit.on;
    hit.node.classList.toggle("off", !hit.on);
    text.value = textFromLines();
    use.disabled = !text.value.trim();
  }

  function collectLines(data, area, canvas) {
    const width = area.right - area.left;
    const height = area.bottom - area.top;
    const result = [];
    (data.blocks || []).forEach((block, blockIndex) => {
      (block.paragraphs || []).forEach((paragraph, paragraphIndex) => {
        (paragraph.lines || []).forEach((line) => {
          const value = line.text.replace(/\s+/g, " ").trim();
          if (!value || !line.bbox) return;
          result.push({
            text: value,
            paragraph: `${blockIndex}.${paragraphIndex}`,
            on: line.confidence >= MIN_LINE_CONFIDENCE && /[\p{L}\p{N}]/u.test(value),
            box: {
              left: area.left + (line.bbox.x0 / canvas.width) * width,
              right: area.left + (line.bbox.x1 / canvas.width) * width,
              top: area.top + (line.bbox.y0 / canvas.height) * height,
              bottom: area.top + (line.bbox.y1 / canvas.height) * height,
            },
          });
        });
      });
    });
    return result;
  }

  // --- Image preparation: crop from the original, then flatten shadows and boost contrast. ---

  function cropToCanvas(image, area) {
    const x = Math.floor(area.left * image.naturalWidth);
    const y = Math.floor(area.top * image.naturalHeight);
    const width = Math.max(1, Math.round((area.right - area.left) * image.naturalWidth));
    const height = Math.max(1, Math.round((area.bottom - area.top) * image.naturalHeight));
    const longest = Math.max(width, height);
    const scale = longest > MAX_SIDE ? MAX_SIDE / longest : Math.min(2, MIN_SIDE / longest);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    const context = canvas.getContext("2d");
    context.imageSmoothingQuality = "high";
    context.fillStyle = "white";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, x, y, width, height, 0, 0, canvas.width, canvas.height);
    return canvas;
  }

  // Phone photos have uneven light. Dividing each pixel by a blurred copy of the page removes the
  // shadows, and stretching the histogram makes the ink clearly darker than the paper.
  function enhance(canvas) {
    const { width, height } = canvas;
    const context = canvas.getContext("2d", { willReadFrequently: true });

    const blurred = document.createElement("canvas");
    blurred.width = Math.max(1, Math.round(width / 24));
    blurred.height = Math.max(1, Math.round(height / 24));
    const small = blurred.getContext("2d");
    small.imageSmoothingQuality = "high";
    small.drawImage(canvas, 0, 0, blurred.width, blurred.height);
    const background = document.createElement("canvas");
    background.width = width;
    background.height = height;
    const large = background.getContext("2d", { willReadFrequently: true });
    large.imageSmoothingQuality = "high";
    large.drawImage(blurred, 0, 0, width, height);

    const pixels = context.getImageData(0, 0, width, height);
    const paper = large.getImageData(0, 0, width, height).data;
    const data = pixels.data;
    const gray = new Float32Array(width * height);
    const histogram = new Uint32Array(256);
    for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
      const ink = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      const light = 0.299 * paper[i] + 0.587 * paper[i + 1] + 0.114 * paper[i + 2];
      const flat = Math.min(255, (ink * 255) / Math.max(light, 40));
      gray[p] = flat;
      histogram[Math.round(flat)] += 1;
    }

    const total = gray.length;
    let low = 0;
    let high = 255;
    for (let sum = 0; low < 255 && (sum += histogram[low]) < total * 0.01; low += 1);
    for (let sum = 0; high > 0 && (sum += histogram[high]) < total * 0.3; high -= 1);
    high = Math.max(high, low + 40);
    for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
      const value = Math.max(0, Math.min(255, ((gray[p] - low) * 255) / (high - low)));
      data[i] = data[i + 1] = data[i + 2] = value;
    }
    context.putImageData(pixels, 0, 0);
    return canvas;
  }

  async function prepare(file) {
    if (!file) return;
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      message("Elige una imagen JPG, PNG o WebP.", true);
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      message("La imagen supera los 20 MB. Usa una foto más pequeña.", true);
      return;
    }

    clearTimeout(readTimer);
    const current = ++job;
    clearPreview();
    setProcessing(true);
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    preview.hidden = false;
    message("Cargando la imagen…");
    try {
      const image = new Image();
      image.src = previewUrl;
      await image.decode();
      if (current !== job) return;
      sourceImage = image;
      crop.hidden = cropTools.hidden = false;
      selection = { ...WHOLE };
      showSelection();
      setProcessing(false);
      readSelection();
    } catch {
      if (current === job) {
        clearPreview();
        setProcessing(false);
        message("No pude abrir la imagen. Prueba otra foto JPG, PNG o WebP.", true);
      }
    }
  }

  async function readSelection() {
    if (!sourceImage) return;
    const current = ++job;
    const area = { ...selection };
    clearResult();
    progress.value = 0;
    setProcessing(true);
    message("Preparando el lector…");
    let timeout;
    try {
      const canvas = enhance(cropToCanvas(sourceImage, area));
      const recognize = async () => {
        const worker = await getWorker();
        if (current !== job) return null;
        // A selected block reads best as one uniform block; a whole page needs layout analysis.
        await worker.setParameters({
          tessedit_pageseg_mode: isWholeArea(area) ? "3" : "6",
          preserve_interword_spaces: "1",
          user_defined_dpi: "300",
        });
        onProgress = (value) => {
          if (current !== job) return;
          progress.value = Math.round(value * 100);
          message(`Leyendo… ${progress.value}%`);
        };
        message("Leyendo…");
        return worker.recognize(canvas, {}, { text: true, blocks: true });
      };
      const result = await Promise.race([
        recognize(),
        new Promise((_, reject) => {
          timeout = setTimeout(() => reject(new Error("La lectura tardó demasiado. Prueba con una imagen más pequeña.")), TIMEOUT_MS);
        }),
      ]);
      if (current !== job || !result) return;

      lines = collectLines(result.data, area, canvas);
      if (lines.length) {
        paintLines();
        text.value = textFromLines();
      } else {
        text.value = result.data.text.trim();
      }
      message(text.value
        ? "Toca una línea de la foto para incluirla o quitarla. Puedes editar el texto."
        : "No se detectó texto. Prueba otra foto más nítida o ajusta el recuadro.");
    } catch (error) {
      if (current === job) {
        releaseWorker(); // a failed worker may be stuck: start fresh next time
        message(`No pude leer la imagen. ${error.message || "Prueba con otra foto."}`, true);
      }
    } finally {
      clearTimeout(timeout);
      if (current === job) setProcessing(false);
    }
  }

  const isWholeArea = (area) =>
    area.left <= 0.02 && area.top <= 0.02 && area.right >= 0.98 && area.bottom >= 0.98;

  get("scan-document").onclick = () => {
    dialog.showModal();
    getWorker().catch(() => {}); // warm up while the user takes the photo
  };
  camera.onclick = () => get("scanner-photo").click();
  upload.onclick = () => get("scanner-file").click();
  for (const id of ["scanner-photo", "scanner-file"]) {
    get(id).onchange = (event) => {
      const file = event.target.files[0];
      event.target.value = ""; // Allow selecting the same photo again.
      prepare(file);
    };
  }
  readButton.onclick = () => {
    clearTimeout(readTimer);
    readSelection();
  };
  text.oninput = () => { use.disabled = processing || !text.value.trim(); };
  get("scanner-close").onclick = () => dialog.close();
  dialog.addEventListener("close", () => {
    job += 1;
    clearTimeout(readTimer);
    releaseWorker();
    setProcessing(false);
    clearPreview();
    message("");
  });
  use.onclick = () => {
    if (processing || !text.value.trim()) return;
    const input = get("input");
    const extracted = text.value.trim();
    input.value = input.value.trim() ? `${input.value.trim()}\n\n${extracted}` : extracted;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    dialog.close();
    input.focus();
  };
})();
