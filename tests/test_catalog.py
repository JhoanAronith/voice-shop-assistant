"""Unit: grounding context, demand counting and inventory alerts."""
import catalog


def skus(products):
    return {p["sku"] for p in products}


def test_relevant_matches_product_terms():
    assert "LT-004" in skus(catalog._relevant("¿tienen laptop gamer?"))
    assert "PH-010" in skus(catalog._relevant("busco un celular"))


def test_relevant_returns_full_catalog_for_generic_questions():
    assert len(catalog._relevant("qué venden")) == len(catalog.CATALOG)
    assert len(catalog._relevant("")) == len(catalog.CATALOG)


def test_relevant_is_empty_when_nothing_matches():
    assert catalog._relevant("hola buenas tardes") == []


def test_context_falls_back_to_category_summary():
    context = catalog.as_context("hola buenas tardes")
    assert "CATALOGO POR CATEGORIA" in context
    assert "Laptops: 4 modelos" in context


def test_context_includes_only_touched_store_blocks():
    context = catalog.as_context("¿puedo pagar con yape?")
    assert "MEDIOS DE PAGO:" in context
    assert "SUCURSALES:" not in context


def test_context_uses_default_blocks_when_none_match():
    context = catalog.as_context("monitor")
    assert "MN-030" in context
    for title in ("MEDIOS DE PAGO:", "ENVIOS:", "PROMOCIONES VIGENTES:", "POLITICAS:"):
        assert title in context
    assert "SUCURSALES:" not in context


def test_demand_counts_mentions_and_sorts_desc():
    rows = catalog.demand(["quiero un mouse", "el mouse vista glide", "una impresora"])
    assert rows[0]["sku"] == "MS-041"
    assert rows[0]["menciones"] == 2
    by_sku = {r["sku"]: r["menciones"] for r in rows}
    assert by_sku["PR-080"] == 1
    assert by_sku["LT-001"] == 0


def test_inventory_flags_low_and_out_of_stock():
    inv = catalog.inventory()
    assert inv["products"] == len(catalog.CATALOG)
    assert inv["out_of_stock"] == 2
    assert all(row["stock"] < 5 for row in inv["risky"])
    assert [r["stock"] for r in inv["risky"]] == sorted(r["stock"] for r in inv["risky"])
