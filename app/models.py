"""Modèles Pydantic : ils valident les données entrantes et définissent le format de sortie."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    electronics = "electronics"
    books = "books"
    clothing = "clothing"
    home = "home"


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    # Prix en CENTIMES (entier) : on ne stocke jamais l'argent en float (0.1 + 0.2 != 0.3).
    price_cents: int = Field(gt=0, le=100_000_000)
    category: Category
    stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    """Tous les champs sont optionnels : on met à jour seulement ce qui est envoyé (PATCH)."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price_cents: int | None = Field(default=None, gt=0, le=100_000_000)
    category: Category | None = None
    stock: int | None = Field(default=None, ge=0)
    active: bool | None = None


class ProductOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    price_cents: int
    category: Category
    stock: int
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CheckoutItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=10)


class CheckoutRequest(BaseModel):
    items: list[CheckoutItem] = Field(min_length=1, max_length=20)
