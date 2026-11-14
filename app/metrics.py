"""Métriques Prometheus (RED : Rate, Errors, Duration) + métriques métier."""
from opentelemetry import metrics
from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "http_requests_total",
    "Nombre total de requêtes HTTP",
    ["method", "path", "status"], # <--- Tes 3 étiquettes (labels)
)

# IMPORTANT : le bucket 0.2 correspond au SLO de latence (95 % des requêtes < 200 ms).
# Sans un bucket exactement à 0.2, on ne pourrait pas calculer ce SLI précisément (Phase 7).
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP en secondes",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.5, 5.0),
)

PRODUCTS_CREATED = Counter(
    "products_created_total",
    "Nombre de produits créés",
    ["category"],
)

CHECKOUT_REVENUE = Counter(
    "checkout_revenue_cents_total",
    "Chiffre d'affaires cumulé des commandes validées (en centimes)",
)

# Métrique OpenTelemetry (SDK OTel -> OTLP -> Prometheus) : articles vendus
CHECKOUT_ITEMS = metrics.get_meter("catalog-api").create_counter(
    "catalog.checkout.items", unit="{item}", description="Articles vendus via /checkout"
)
