"""CORRECTION de l'exercice Phase 2 : cas limites et erreurs.

Chaque test vise des lignes que `pytest --cov` montrait en rouge :
404, 422 (id invalide), PATCH, DELETE, et surtout le rollback de /checkout.
"""
import pytest

from app.database import get_db
from app.main import app
from tests.conftest import make_product

UNKNOWN_ID = "0" * 24  # ObjectId valide (24 hex) mais qui n'existe pas


# Le but de cette fixture est d'accélérer drastiquement l'exécution des tests en supprimant les temps d'attente artificiels.
@pytest.fixture(autouse=True)
def fast_checkout(monkeypatch):
    """Supprime la latence simulée (100-600 ms) de /checkout dans tous les tests de ce fichier."""

    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.routers.ops.asyncio.sleep", no_sleep)


# ---------- PATCH ----------
async def test_patch_updates_stock(client):
    p = await make_product(client)
    resp = await client.patch(f"/products/{p['id']}", json={"stock": 3})
    assert resp.status_code == 200
    assert resp.json()["stock"] == 3
    assert resp.json()["name"] == "Clavier"  # les autres champs ne bougent pas


async def test_patch_empty_body_returns_422(client):
    p = await make_product(client)
    resp = await client.patch(f"/products/{p['id']}", json={})
    assert resp.status_code == 422


async def test_patch_unknown_id_returns_404(client):
    resp = await client.patch(f"/products/{UNKNOWN_ID}", json={"stock": 1})
    assert resp.status_code == 404


async def test_patch_duplicate_name_returns_409(client):
    await make_product(client, name="A")
    b = await make_product(client, name="B")
    resp = await client.patch(f"/products/{b['id']}", json={"name": "A"})
    assert resp.status_code == 409


# ---------- GET / DELETE ----------
async def test_get_unknown_id_returns_404(client):
    assert (await client.get(f"/products/{UNKNOWN_ID}")).status_code == 404


async def test_get_malformed_id_returns_422(client):
    assert (await client.get("/products/pas-un-id")).status_code == 422


async def test_delete_then_get_returns_404(client):
    p = await make_product(client)
    assert (await client.delete(f"/products/{p['id']}")).status_code == 204
    assert (await client.get(f"/products/{p['id']}")).status_code == 404


async def test_delete_unknown_id_returns_404(client):
    assert (await client.delete(f"/products/{UNKNOWN_ID}")).status_code == 404


# ---------- CHECKOUT : erreurs et rollback ----------
async def test_checkout_insufficient_stock_returns_409_and_keeps_stock(client):
    p = await make_product(client, stock=2)
    resp = await client.post(
        "/checkout", json={"items": [{"product_id": p["id"], "quantity": 5}]}
    )
    assert resp.status_code == 409
    assert (await client.get(f"/products/{p['id']}")).json()["stock"] == 2


async def test_checkout_rolls_back_first_item_when_second_fails(client):
    a = await make_product(client, name="A", stock=10)
    b = await make_product(client, name="B", stock=1)
    resp = await client.post(
        "/checkout",
        json={
            "items": [
                {"product_id": a["id"], "quantity": 4},  # réussit (stock 10 -> 6)
                {"product_id": b["id"], "quantity": 5},  # échoue (stock 1 < 5)
            ]
        },
    )
    assert resp.status_code == 409
    # Le stock de A doit avoir été RESTITUÉ par la compensation
    assert (await client.get(f"/products/{a['id']}")).json()["stock"] == 10



async def test_checkout_malformed_product_id_returns_422(client):
    resp = await client.post(
        "/checkout", json={"items": [{"product_id": "nope", "quantity": 1}]}
    )
    assert resp.status_code == 422


async def test_checkout_inactive_product_returns_409(client):
    p = await make_product(client)
    await client.patch(f"/products/{p['id']}", json={"active": False})
    resp = await client.post(
        "/checkout", json={"items": [{"product_id": p["id"], "quantity": 1}]}
    )
    assert resp.status_code == 409

# ---------- READY en échec (bonus) ----------
async def test_ready_returns_503_when_db_down(client):
    class BrokenDb:
        async def command(self, *_args, **_kwargs):
            raise RuntimeError("mongo down")

    async def broken_get_db():
        return BrokenDb()

    app.dependency_overrides[get_db] = broken_get_db
    resp = await client.get("/ready")
    assert resp.status_code == 503


# ---------- Non-régression des bugs corrigés en phase 3 ----------
async def test_search_combined_with_in_stock_false(client):
    """Avant correction, le `elif` ignorait in_stock=false dès qu'il y avait un `search`."""
    await make_product(client, name="Clavier A", stock=0)
    await make_product(client, name="Clavier B", stock=5)
    resp = await client.get("/products", params={"search": "clavier", "in_stock": False})
    assert [p["name"] for p in resp.json()] == ["Clavier A"]


async def test_search_is_escaped_not_a_regex(client):
    """`.*` doit être cherché comme texte littéral (anti-ReDoS), pas comme regex."""
    await make_product(client, name="Clavier")
    resp = await client.get("/products", params={"search": ".*"})
    assert resp.json() == []
