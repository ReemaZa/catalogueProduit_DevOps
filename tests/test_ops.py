"""Tests des endpoints techniques : health, ready, flaky, checkout."""
from tests.conftest import make_product


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_ok(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200


async def test_flaky_always_fails_when_rate_is_1(client, monkeypatch):
    monkeypatch.setenv("FLAKY_ERROR_RATE", "1.0")
    resp = await client.get("/flaky")
    assert resp.status_code == 500


async def test_flaky_never_fails_when_rate_is_0(client, monkeypatch):
    monkeypatch.setenv("FLAKY_ERROR_RATE", "0")
    resp = await client.get("/flaky")
    assert resp.status_code == 200


async def test_checkout_ok_decrements_stock(client, monkeypatch):
    # On neutralise la latence simulée pour que le test soit instantané
    async def no_sleep(_): return None
    monkeypatch.setattr("app.routers.ops.asyncio.sleep", no_sleep)

    product = await make_product(client, price_cents=1000, stock=10)
    resp = await client.post(
        "/checkout", json={"items": [{"product_id": product["id"], "quantity": 3}]}
    )
    assert resp.status_code == 200
    assert resp.json()["total_cents"] == 3000

    after = (await client.get(f"/products/{product['id']}")).json()
    assert after["stock"] == 7
