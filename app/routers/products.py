"""CRUD du catalogue produits + statistiques (exercice 1) + stock bas (exercice 2)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.database import get_db
from app.metrics import PRODUCTS_CREATED
from app.models import Category, ProductCreate, ProductOut, ProductUpdate
from app.utils import parse_object_id
import re

router = APIRouter(prefix="/products", tags=["products"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_out(doc: dict) -> ProductOut:
    """Mongo stocke `_id` (ObjectId) ; l'API expose `id` (str)."""
    data = {**doc, "id": str(doc["_id"])} #{**doc} : C'est la syntaxe de "décomposition" (dictionary unpacking en Python). Ça crée un nouveau dictionnaire en copiant tous les champs du document MongoDB d'origine.
    data.pop("_id")
    return ProductOut(**data)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    now = _now()
    doc = {**payload.model_dump(mode="json"), "active": True, "created_at": now, "updated_at": now}
    try:
        result = await db.products.insert_one(doc)
    except DuplicateKeyError:  # index unique sur `name` (cf. main.py)
        raise HTTPException(status_code=409, detail="Un produit avec ce nom existe déjà") from None
    doc["_id"] = result.inserted_id
    PRODUCTS_CREATED.labels(category=payload.category.value).inc()
    return _to_out(doc)


@router.get("", response_model=list[ProductOut])
#La signature = contrat de validation automatique des paramètres d'URL (query parameters).
async def list_products(
    category: Category | None = None,
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    in_stock: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    search: str | None = None, 
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {"active": True}
    if category:
        query["category"] = category.value
    price: dict = {}
    if min_price_cents is not None:
        price["$gte"] = min_price_cents
    if max_price_cents is not None:
        price["$lte"] = max_price_cents
    if price:
        query["price_cents"] = price
    if in_stock is True:
        query["stock"] = {"$gt": 0}
    elif in_stock is False:
        query["stock"] = 0
    if search is not None:
         # re.escape : l'utilisateur cherche du TEXTE, pas une expression régulière (anti-ReDoS)
         query["name"] = {"$regex": re.escape(search), "$options": "i"}
    cursor = db.products.find(query).sort("created_at", -1).skip(skip).limit(limit)
    return [_to_out(doc) async for doc in cursor]


@router.get("/stats")
async def product_stats(db: AsyncIOMotorDatabase = Depends(get_db)):
    pipeline: list[dict] = [
        { "$match": {"active": True} },
        { "$facet": {
            "by_category": [
                {
                    "$group": {
                        "_id": "$category", 
                        "count": {"$sum": 1}, 
                        "avg_price_cents": {"$avg": "$price_cents"}, 
                        "total_stock": {"$sum": "$stock"}
                    }
                }
            ],
            "top_expensive": [
                { "$sort": {"price_cents": -1} },  
                { "$limit": 3 },
                { "$project": {"name": 1, "price_cents": 1, "_id": 0} }
            ]
        }}
    ]

    result = await db.products.aggregate(pipeline).to_list(length=1)
    return result[0] if result else {"by_category": [], "top_expensive": []}


@router.get("/low-stock", response_model=list[ProductOut])
async def get_products_low_stock(threshold : int = Query(default = 5, ge = 0 ) , db :AsyncIOMotorDatabase = Depends(get_db) ):
    cursor = db.products.find(
        {"active" : True, "stock":{"$lte" : threshold}}
        ).sort("stock",1)
        
    return [_to_out(doc)  async for doc in cursor]


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await db.products.find_one({"_id": parse_object_id(product_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return _to_out(doc)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, payload: ProductUpdate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    changes = payload.model_dump(mode="json", exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Aucun champ à modifier")
    changes["updated_at"] = _now()
    try:
        doc = await db.products.find_one_and_update(
            {"_id": parse_object_id(product_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Un produit avec ce nom existe déjà") from None
    if doc is None:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return _to_out(doc)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    result = await db.products.delete_one({"_id": parse_object_id(product_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Produit introuvable")
