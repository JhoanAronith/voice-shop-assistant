"""Store data used as grounding context for the assistant."""

# sku, nombre, categoria, marca, precio (S/), stock, garantia (meses), rating, terminos
PRODUCTS = [
    ("LT-001", "Laptop Nexo 14 i5 16GB 512GB SSD", "Laptops", "Nexo", 2899.00, 12, 24, 4.6,
     ["nexo 14", "laptop nexo"]),
    ("LT-002", "Laptop Nexo 16 Pro i7 32GB 1TB SSD", "Laptops", "Nexo", 4599.00, 4, 24, 4.8,
     ["nexo 16", "nexo pro"]),
    ("LT-003", "Laptop Aura Air 13 Ryzen 5 16GB 512GB", "Laptops", "Aura", 2399.00, 9, 12, 4.3,
     ["aura air", "laptop liviana", "ultrabook"]),
    ("LT-004", "Laptop gamer Vector RTX 4060 16GB 1TB", "Laptops", "Vector", 5899.00, 3, 24, 4.7,
     ["laptop gamer", "vector rtx", "portatil gamer", "gamer", "gaming", "juegos"]),
    ("PH-010", "Smartphone Orbit 5 128GB", "Smartphones", "Orbit", 1199.00, 27, 12, 4.4,
     ["orbit 5", "smartphone", "celular"]),
    ("PH-011", "Smartphone Orbit 5 Pro 256GB", "Smartphones", "Orbit", 1899.00, 14, 12, 4.6,
     ["orbit 5 pro", "orbit pro"]),
    ("PH-012", "Smartphone Lumo Lite 64GB", "Smartphones", "Lumo", 649.00, 31, 12, 4.0,
     ["lumo lite", "celular economico", "celular barato"]),
    ("TB-015", "Tablet Orbit Pad 11 128GB", "Tablets", "Orbit", 1349.00, 7, 12, 4.2,
     ["orbit pad", "tablet"]),
    ("AU-020", "Audifonos Orbit Buds ANC", "Audio", "Orbit", 349.00, 0, 12, 4.5,
     ["orbit buds", "audífonos", "audifonos", "earbuds"]),
    ("AU-021", "Audifonos over-ear Sonda Studio", "Audio", "Sonda", 599.00, 6, 24, 4.7,
     ["sonda studio", "over ear", "diadema"]),
    ("AU-022", "Parlante Bluetooth Sonda Go", "Audio", "Sonda", 229.00, 22, 12, 4.1,
     ["sonda go", "parlante", "bocina", "speaker"]),
    ("MN-030", 'Monitor Vista 27" 144Hz QHD', "Monitores", "Vista", 999.00, 8, 36, 4.6,
     ["vista 27", "monitor", "gaming", "144hz"]),
    ("MN-031", 'Monitor Vista 32" 4K', "Monitores", "Vista", 1699.00, 5, 36, 4.5,
     ["vista 32", "monitor 4k"]),
    ("TC-040", "Teclado mecanico Vista TKL", "Perifericos", "Vista", 279.00, 15, 12, 4.4,
     ["vista tkl", "teclado"]),
    ("MS-041", "Mouse inalambrico Vista Glide", "Perifericos", "Vista", 149.00, 34, 12, 4.3,
     ["vista glide", "mouse", "raton"]),
    ("WC-042", "Webcam Vista Stream 1080p", "Perifericos", "Vista", 199.00, 11, 12, 4.0,
     ["vista stream", "webcam", "camara web"]),
    ("GP-050", "Tarjeta grafica Vector 8GB", "Componentes", "Vector", 2199.00, 3, 36, 4.8,
     ["vector 8gb", "tarjeta gráfica", "tarjeta grafica", "gpu", "gamer", "gaming"]),
    ("SS-051", "SSD NVMe Celer 1TB", "Componentes", "Celer", 389.00, 26, 60, 4.7,
     ["ssd", "nvme", "celer 1tb", "disco solido"]),
    ("RM-052", "Memoria RAM Celer 16GB DDR5", "Componentes", "Celer", 329.00, 18, 60, 4.6,
     ["ram", "memoria", "ddr5"]),
    ("SW-060", "Smartwatch Orbit Fit 2", "Wearables", "Orbit", 449.00, 0, 12, 4.1,
     ["orbit fit", "smartwatch", "reloj"]),
    ("RT-070", "Router WiFi 6 Enlace AX3000", "Redes", "Enlace", 419.00, 13, 24, 4.4,
     ["router", "wifi 6", "enlace ax"]),
    ("PR-080", "Impresora multifuncional Trazo 400", "Impresion", "Trazo", 729.00, 6, 12, 4.0,
     ["impresora", "trazo 400", "multifuncional"]),
]

FIELDS = ("sku", "nombre", "categoria", "marca", "precio", "stock", "garantia", "rating", "terminos")

CATALOG = [dict(zip(FIELDS, product, strict=True)) for product in PRODUCTS]

STORE = {
    "sucursales": [
        "Lima Centro — Av. Abancay 512, lun-sáb 10:00-20:00",
        "San Isidro — Av. Camino Real 340, lun-sáb 10:00-21:00",
        "Arequipa — Calle Mercaderes 118, lun-vie 10:00-19:00",
    ],
    "canales": [
        "WhatsApp de ventas: +51 1 700-4500 (lun-dom 9:00-21:00)",
        "Soporte técnico: soporte@tecnostore.pe, respuesta en 24 h hábiles",
    ],
    "pagos": [
        "Tarjeta de crédito y débito, transferencia, Yape y Plin.",
        "Hasta 12 cuotas sin intereses con bancos afiliados desde S/ 800.",
        "Factura o boleta electrónica emitida al instante.",
    ],
    "envios": [
        "Envío gratis en compras mayores a S/ 500.",
        "Lima Metropolitana 24-48 h; provincias 3-5 días hábiles vía agencia.",
        "Retiro en tienda disponible en 2 h si hay stock en esa sucursal.",
    ],
    "promociones": [
        "10% de descuento en periféricos al comprar cualquier laptop.",
        "Segunda unidad de accesorios de audio a mitad de precio.",
        "Trade-in: hasta S/ 400 por tu equipo usado al comprar un smartphone.",
    ],
    "politicas": [
        "Devolución sin costo dentro de 7 días si el producto está sin uso y con embalaje.",
        "Garantía atendida en tienda o con recojo a domicilio en Lima.",
        "Productos sin stock se reponen en 5-7 días hábiles y se pueden reservar con 20%.",
    ],
}


def _lines(products: list[dict]) -> list[str]:
    return [
        f"- {p['sku']} | {p['nombre']} | {p['categoria']} | {p['marca']} | S/ {p['precio']:.2f}"
        f" | stock: {p['stock']} | garantía: {p['garantia']}m | rating: {p['rating']}"
        for p in products
    ]


def _block(title: str, items: list[str]) -> str:
    return title + "\n" + "\n".join(f"- {item}" for item in items)


ALL_PRODUCTS_HINTS = (
    "todo",
    "todos",
    "catalogo",
    "catálogo",
    "lista",
    "que venden",
    "qué venden",
    "que tienen",
    "qué tienen",
)


def _relevant(query: str) -> list[dict]:
    """Products worth putting in the prompt for this question."""
    text = (query or "").lower()
    if not text or any(hint in text for hint in ALL_PRODUCTS_HINTS):
        return CATALOG

    return [
        product
        for product in CATALOG
        if any(term in text for term in product["terminos"])
        or product["categoria"].lower() in text
        or product["marca"].lower() in text
    ]


def _summary_lines() -> list[str]:
    """One line per category, for questions that name no product."""
    lines = []
    for name in dict.fromkeys(p["categoria"] for p in CATALOG):
        items = [p for p in CATALOG if p["categoria"] == name]
        prices = [p["precio"] for p in items]
        lines.append(
            f"- {name}: {len(items)} modelos, desde S/ {min(prices):.2f} hasta S/ {max(prices):.2f}"
        )
    return lines


BLOCKS = (
    ("sucursales", "SUCURSALES:", ("tienda", "sucursal", "direccion", "dirección", "horario",
                                   "abren", "cierran", "ubicacion", "ubicación", "arequipa", "isidro")),
    ("canales", "CONTACTO:", ("whatsapp", "telefono", "teléfono", "correo", "email", "contacto",
                              "soporte", "llamar", "escribir")),
    ("pagos", "MEDIOS DE PAGO:", ("pago", "pagar", "pagos", "yape", "plin", "tarjeta", "cuota",
                                  "cuotas", "transferencia", "factura", "boleta", "credito", "crédito")),
    ("envios", "ENVIOS:", ("envio", "envío", "entrega", "llega", "delivery", "despacho",
                           "provincia", "provincias", "lima", "retiro", "recojo")),
    ("promociones", "PROMOCIONES VIGENTES:", ("descuento", "descuentos", "promocion", "promoción",
                                              "promociones", "oferta", "ofertas", "rebaja",
                                              "trade", "canje")),
    ("politicas", "POLITICAS:", ("devolucion", "devolución", "devolver", "garantia", "garantía",
                                 "cambio", "cambiar", "reponen", "reposicion", "reposición",
                                 "reservar", "reserva")),
)

DEFAULT_BLOCKS = ("pagos", "envios", "promociones", "politicas")


def _relevant_blocks(query: str) -> list[tuple[str, str]]:
    """Keep the store sections the question actually touches, to stay short."""
    text = (query or "").lower()
    matched = [(key, title) for key, title, hints in BLOCKS if any(h in text for h in hints)]
    if matched:
        return matched
    return [(key, title) for key, title, _ in BLOCKS if key in DEFAULT_BLOCKS]


def as_context(query: str = "") -> str:
    """Grounding context: matching catalog lines first, then the store facts in play."""
    products = _relevant(query)
    if products:
        header = "CATALOGO (SKU | producto | categoría | marca | precio | stock | garantía | rating):"
        catalog_section = header + "\n" + "\n".join(_lines(products))
    else:
        catalog_section = (
            "CATALOGO POR CATEGORIA (pide una categoría o producto para ver precios y stock):\n"
            + "\n".join(_summary_lines())
        )
    sections = [catalog_section]
    sections += [_block(title, STORE[key]) for key, title in _relevant_blocks(query)]
    return "\n\n".join(sections)


def demand(texts: list[str]) -> list[dict]:
    """Count how many customer messages mention each product."""
    lowered = [text.lower() for text in texts]
    rows = [
        {
            "sku": p["sku"],
            "nombre": p["nombre"],
            "categoria": p["categoria"],
            "precio": p["precio"],
            "stock": p["stock"],
            "menciones": sum(1 for text in lowered if any(term in text for term in p["terminos"])),
        }
        for p in CATALOG
    ]
    return sorted(rows, key=lambda row: (-row["menciones"], row["nombre"]))


def inventory() -> dict:
    """Catalog size and the items that need restocking."""
    risky = sorted(
        (
            {
                "sku": p["sku"],
                "nombre": p["nombre"],
                "categoria": p["categoria"],
                "stock": p["stock"],
                "precio": p["precio"],
            }
            for p in CATALOG
            if p["stock"] < 5
        ),
        key=lambda row: row["stock"],
    )
    return {
        "products": len(CATALOG),
        "categories": len({p["categoria"] for p in CATALOG}),
        "units": sum(p["stock"] for p in CATALOG),
        "out_of_stock": sum(1 for p in CATALOG if p["stock"] == 0),
        "risky": risky,
    }
