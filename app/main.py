"""Point d'entrée FastAPI : middleware de métriques, routeurs, endpoint /metrics."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.database import close_client, get_db
from app.metrics import LATENCY, REQUESTS
from app.routers import ops, products

logger = logging.getLogger("catalog-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage : création des index (idempotent). Cf. docs/02-mongodb.md
    try:
        db = await get_db()
        await db.products.create_index("name", unique=True)  # pas de doublon de nom
        await db.products.create_index([("category", 1), ("price_cents", 1)])
        await db.products.create_index("stock")
        await db.products.create_index([("created_at", -1)])
    except Exception:
        logger.warning("Impossible de créer les index (MongoDB indisponible ?)")
    yield
    close_client()  # Arrêt propre


app = FastAPI(title="Catalog API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500  # Si une exception non gérée survient, c'est une 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        # On utilise le TEMPLATE de route ("/products/{product_id}") et non l'URL réelle,
        # sinon chaque id créerait une nouvelle série temporelle (explosion de cardinalité).
        path = route.path if route else "unmatched"
        if path != "/metrics":
            duration = time.perf_counter() - start
            REQUESTS.labels(request.method, path, str(status_code)).inc()
            LATENCY.labels(request.method, path).observe(duration)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(products.router)
app.include_router(ops.router)
