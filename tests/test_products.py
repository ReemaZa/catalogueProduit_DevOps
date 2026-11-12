"""Tests de l'API produits : cas nominaux ET cas limites."""
from tests.conftest import make_product


# ---------- CREATE ----------
async def test_create_product_ok(client):
    resp = await client.post(
        "/products",
        json={"name": "Clavier", "price_cents": 8990, "category": "electronics", "stock": 25},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["active"] is True
    assert body["price_cents"] == 8990


async def test_create_duplicate_name_returns_409(client):
    await make_product(client)
    resp = await client.post(
        "/products", json={"name": "Clavier", "price_cents": 1, "category": "books"}
    )
    assert resp.status_code == 409


async def test_create_negative_price_returns_422(client):
    resp = await client.post(
        "/products", json={"name": "X", "price_cents": -5, "category": "books"}
    )
    assert resp.status_code == 422


async def test_create_unknown_category_returns_422(client):
    resp = await client.post(
        "/products", json={"name": "X", "price_cents": 5, "category": "jouets"}
    )
    assert resp.status_code == 422


# ---------- READ ----------
async def test_get_product_ok(client):
    created = await make_product(client)
    resp = await client.get(f"/products/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Clavier"


# ---------- LIST + filtres ----------
async def test_list_filters_by_category(client):
    await make_product(client, name="Clavier", category="electronics")
    await make_product(client, name="Roman", category="books", price_cents=1500)
    resp = await client.get("/products", params={"category": "books"})
    assert [p["name"] for p in resp.json()] == ["Roman"]


async def test_list_filters_by_price_range(client):
    await make_product(client, name="Cher", price_cents=10000)
    await make_product(client, name="Pas cher", price_cents=500)
    resp = await client.get(
        "/products", params={"min_price_cents": 1000, "max_price_cents": 20000}
    )
    assert [p["name"] for p in resp.json()] == ["Cher"]


async def test_list_in_stock_true_and_false(client):
    await make_product(client, name="Dispo", stock=3)
    await make_product(client, name="Epuise", stock=0)
    in_stock = await client.get("/products", params={"in_stock": True})
    out_of_stock = await client.get("/products", params={"in_stock": False})
    assert [p["name"] for p in in_stock.json()] == ["Dispo"]
    assert [p["name"] for p in out_of_stock.json()] == ["Epuise"]


async def test_list_search_is_case_insensitive(client):
    await make_product(client, name="Clavier mecanique")
    resp = await client.get("/products", params={"search": "CLAVIER"})
    assert len(resp.json()) == 1


async def test_list_pagination_limit(client):
    for i in range(3):
        await make_product(client, name=f"P{i}")
    resp = await client.get("/products", params={"limit": 2})
    assert len(resp.json()) == 2


async def test_list_limit_out_of_bounds_returns_422(client):
    resp = await client.get("/products", params={"limit": 0})
    assert resp.status_code == 422


# ---------- STATS (exercice 1 de la phase 1) ----------
async def test_stats_empty_catalog(client):
    resp = await client.get("/products/stats")
    assert resp.status_code == 200
    assert resp.json() == {"by_category": [], "top_expensive": []}


async def test_stats_with_data(client):
    await make_product(client, name="A", category="books", price_cents=1000, stock=2)
    await make_product(client, name="B", category="books", price_cents=3000, stock=4)
    await make_product(client, name="C", category="home", price_cents=9000, stock=1)
    body = (await client.get("/products/stats")).json()
    books = next(c for c in body["by_category"] if c["_id"] == "books")
    assert books["count"] == 2
    assert books["avg_price_cents"] == 2000
    assert books["total_stock"] == 6
    assert body["top_expensive"][0]["name"] == "C"


# ---------- LOW STOCK (exercice 2 de la phase 1) ----------
async def test_low_stock_default_threshold(client):
    await make_product(client, name="Bas", stock=2)
    await make_product(client, name="Haut", stock=50)
    resp = await client.get("/products/low-stock")
    assert [p["name"] for p in resp.json()] == ["Bas"]


async def test_low_stock_sorted_ascending(client):
    await make_product(client, name="Cinq", stock=5)
    await make_product(client, name="Un", stock=1)
    resp = await client.get("/products/low-stock", params={"threshold": 10})
    assert [p["name"] for p in resp.json()] == ["Un", "Cinq"]
