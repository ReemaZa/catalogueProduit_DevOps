"""Petites fonctions utilitaires partagées."""
from bson import ObjectId
from fastapi import HTTPException


def parse_object_id(value: str) -> ObjectId:
    """Convertit une chaîne en ObjectId, ou lève une 422 si elle est mal formée."""
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=422, detail="Identifiant invalide")
    return ObjectId(value)
