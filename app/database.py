"""Connexion MongoDB (driver async motor) + dépendance FastAPI `get_db`."""
import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "catalog_db")

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def get_db() -> AsyncIOMotorDatabase:
    """Dépendance FastAPI. En test, on la remplace par une fausse base (injection de dépendances)."""
    return get_client()[MONGO_DB]
