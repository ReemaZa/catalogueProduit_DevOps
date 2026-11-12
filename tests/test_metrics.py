"""Tests du endpoint /metrics et du middleware d'instrumentation."""
from tests.conftest import make_product


async def test_metrics_endpoint_exposes_prometheus_text(client):
    await client.get("/health")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
    assert "http_request_duration_seconds_bucket" in resp.text


async def test_metrics_uses_route_template_not_real_id(client):
    product = await make_product(client)
    await client.get(f"/products/{product['id']}")
    text = (await client.get("/metrics")).text
    assert 'path="/products/{product_id}"' in text
    assert product["id"] not in text  # pas d'explosion de cardinalité
