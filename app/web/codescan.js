// Scan a QR or barcode with the camera and ask the assistant about that product.
(() => {
  const get = (id) => document.getElementById(id);
  const dialog = get("code-scanner");
  const video = get("code-video");
  const status = get("code-status");

  const ZXING_URL = "https://cdn.jsdelivr.net/npm/@zxing/library@0.21.3/umd/index.min.js";
  const FORMATS = ["qr_code", "ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39"];
  const NATIVE_EVERY_MS = 120;
  const FALLBACK_EVERY_MS = 220;
  const FALLBACK_WIDTH = 640;
  const RETRY_SAME_CODE_MS = 2500;
  const PROMPT = "Apunta al código QR o de barras.";

  let stream = null;
  let timer = null;
  let session = 0;
  let zxingPromise = null;

  function loadZxing() {
    if (window.ZXing) return Promise.resolve(window.ZXing);
    zxingPromise ??= new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = ZXING_URL;
      script.onload = () => (window.ZXing ? resolve(window.ZXing) : reject(new Error("zxing")));
      script.onerror = () => reject(new Error("zxing"));
      document.head.append(script);
    }).catch((error) => {
      zxingPromise = null;
      throw error;
    });
    return zxingPromise;
  }

  // Chrome on Android decodes natively; elsewhere a JavaScript decoder reads the same frames.
  async function createReader() {
    if ("BarcodeDetector" in window) {
      try {
        const supported = await BarcodeDetector.getSupportedFormats();
        const formats = FORMATS.filter((format) => supported.includes(format));
        if (formats.length) {
          const detector = new BarcodeDetector({ formats });
          return {
            every: NATIVE_EVERY_MS,
            read: async () => (await detector.detect(video))[0]?.rawValue ?? null,
          };
        }
      } catch {
        // fall through to the JavaScript decoder
      }
    }

    const ZXing = await loadZxing();
    const hints = new Map([
      [ZXing.DecodeHintType.POSSIBLE_FORMATS, [
        ZXing.BarcodeFormat.QR_CODE, ZXing.BarcodeFormat.EAN_13, ZXing.BarcodeFormat.EAN_8,
        ZXing.BarcodeFormat.UPC_A, ZXing.BarcodeFormat.UPC_E, ZXing.BarcodeFormat.CODE_128,
        ZXing.BarcodeFormat.CODE_39,
      ]],
      [ZXing.DecodeHintType.TRY_HARDER, true],
    ]);
    const reader = new ZXing.MultiFormatReader();
    reader.setHints(hints);
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { willReadFrequently: true });
    return {
      every: FALLBACK_EVERY_MS,
      read: async () => {
        if (!video.videoWidth) return null;
        canvas.width = Math.min(FALLBACK_WIDTH, video.videoWidth);
        canvas.height = Math.round((canvas.width * video.videoHeight) / video.videoWidth);
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const bitmap = new ZXing.BinaryBitmap(
          new ZXing.HybridBinarizer(new ZXing.HTMLCanvasElementLuminanceSource(canvas))
        );
        try {
          return reader.decode(bitmap).getText();
        } catch {
          return null; // no code in this frame
        }
      },
    };
  }

  function stopCamera() {
    session += 1;
    clearTimeout(timer);
    timer = null;
    stream?.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
  }

  // Resolve the code to a product and ask the assistant about it. False means keep scanning.
  async function handle(code) {
    status.textContent = "Buscando el producto…";
    try {
      const response = await fetch(`/api/product?code=${encodeURIComponent(code)}`);
      if (response.status === 404) {
        status.textContent = "Ese código no es de un producto de la tienda. Prueba con otro.";
        return false;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const product = await response.json();
      navigator.vibrate?.(80);
      dialog.close();
      window.send(`Quiero información de ${product.nombre} (${product.sku}): precio, stock y garantía.`);
      return true;
    } catch {
      status.textContent = "No pude consultar el producto. Inténtalo de nuevo.";
      return false;
    }
  }

  async function start() {
    const mine = ++session;
    status.textContent = "Abriendo la cámara…";
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
        audio: false,
      });
    } catch {
      status.textContent = "Sin acceso a la cámara.";
      return;
    }
    if (mine !== session) {
      stopCamera();
      return;
    }
    video.srcObject = stream;
    await video.play().catch(() => {});

    let reader;
    try {
      reader = await createReader();
    } catch {
      status.textContent = "No se pudo cargar el lector de códigos. Comprueba tu conexión.";
      return;
    }
    if (mine !== session) return;
    status.textContent = PROMPT;

    let last = null;
    const tick = async () => {
      if (mine !== session) return;
      const code = video.readyState >= 2 ? await reader.read().catch(() => null) : null;
      if (mine !== session) return;
      if (code && code !== last) {
        last = code;
        if (await handle(code)) return;
        setTimeout(() => { last = null; }, RETRY_SAME_CODE_MS);
      }
      timer = setTimeout(tick, reader.every);
    };
    tick();
  }

  get("scan-code").onclick = () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      window.toast?.("Este navegador no permite usar la cámara");
      return;
    }
    dialog.showModal();
    start();
  };
  get("code-close").onclick = () => dialog.close();
  dialog.addEventListener("close", stopCamera);
})();
