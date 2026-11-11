"""Endpoints techniques du TP : /checkout (lent), /flaky (erreurs), /health, /ready."""
import asyncio
import os
import random

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_db
from app.metrics import CHECKOUT_REVENUE
from app.models import CheckoutRequest
from app.utils import parse_object_id

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health():
    """Liveness : le process répond. Utilisé par la probe Kubernetes (Phase 4)."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Readiness : l'app ET sa base répondent."""
    try:
        await db.command("ping")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="MongoDB indisponible") from exc
    return {"status": "ready"}


@router.post("/checkout")
async def checkout(payload: CheckoutRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Valide une commande : décrémente le stock et renvoie le total.

    Latence simulée de 100 à 600 ms (paiement externe fictif).
    Le décrément est ATOMIQUE par produit : le filtre `stock >= quantité` et le `$inc`
    s'exécutent en une seule opération Mongo, donc deux clients simultanés ne peuvent
    pas acheter le dernier exemplaire en même temps (pas de stock négatif).
    En cas d'échec sur un article, on restitue le stock des articles déjà décrémentés.
    """
    await asyncio.sleep(random.uniform(0.1, 0.6))

    ids = [parse_object_id(item.product_id) for item in payload.items]  # 422 si invalide
    decremented: list[tuple[ObjectId, int]] = []
    total_cents = 0

    for oid, item in zip(ids, payload.items):
        doc = await db.products.find_one_and_update(
            {"_id": oid, "active": True, "stock": {"$gte": item.quantity}},
            {"$inc": {"stock": -item.quantity}},
        )  # renvoie le document AVANT modification (donc le prix est disponible)
        if doc is None:
            for done_oid, qty in decremented:  # compensation (rollback manuel)
                await db.products.update_one({"_id": done_oid}, {"$inc": {"stock": qty}})
            raise HTTPException(status_code=409, detail="Produit introuvable ou stock insuffisant")
        decremented.append((oid, item.quantity))
        total_cents += doc["price_cents"] * item.quantity

    CHECKOUT_REVENUE.inc(total_cents)
    return {"items": len(payload.items), "total_cents": total_cents}


@router.get("/flaky")
async def flaky():
    """Échoue aléatoirement (HTTP 500) avec la probabilité FLAKY_ERROR_RATE (défaut 30 %)."""
    rate = float(os.getenv("FLAKY_ERROR_RATE", "0.3"))
    if random.random() < rate:
        raise HTTPException(status_code=500, detail="Erreur intermittente simulée")
    return {"status": "ok"}
