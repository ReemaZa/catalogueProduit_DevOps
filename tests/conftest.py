"""Fixtures partagées : fausse base Mongo en mémoire + client HTTP de test."""
import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.database import get_db
from app.main import app


@pytest.fixture
async def db():
    """Une base Mongo FACTICE (en mémoire), neuve pour chaque test."""
    database = AsyncMongoMockClient()["test_db"]
    await database.products.create_index("name", unique=True)
    return database


@pytest.fixture
async def client(db):
    """Client HTTP branché directement sur l'app (pas de vrai serveur, pas de réseau).

    On REMPLACE la dépendance get_db par notre fausse base : c'est le principe
    de l'injection de dépendances (cf. docs/01-python-fastapi.md).
    """

    async def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# --- Helper : crée un produit via l'API et renvoie le JSON ---
async def make_product(client, **overrides):
    payload = {"name": "Clavier", "price_cents": 8990, "category": "electronics", "stock": 25}
    payload.update(overrides)
    resp = await client.post("/products", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()
