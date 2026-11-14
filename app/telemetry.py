"""Instrumentation OpenTelemetry : traces (OTLP -> Tempo), métriques (OTLP -> Prometheus)
et logs JSON corrélés (trace_id).

Les métriques RED/SLO restent exposées par prometheus_client (/metrics, scrapées via annotations) ;
les métriques OTel portent les métriques métier (cf. docs/10-opentelemetry-observabilite.md).
"""
import json
import logging
import os
from datetime import datetime, timezone

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "catalog-api")


class JsonFormatter(logging.Formatter):
    """Un log = une ligne JSON, avec trace_id/span_id de la requête en cours."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = trace.get_current_span().get_span_context()
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
        }
        if ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    # uvicorn.access est remplacé par notre log applicatif (une ligne par requête, avec trace_id)
    logging.getLogger("uvicorn.access").disabled = True


def setup_tracing(app) -> None:
    """Active traces + métriques OTel si les endpoints OTLP sont définis (sinon no-op : tests)."""
    resource = Resource.create({"service.name": SERVICE_NAME})
    if os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"):
        # Métriques OTel poussées en OTLP directement dans Prometheus (receiver OTLP activé)
        reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=15000)
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # lit l'endpoint dans l'env
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/health,/ready")
    PymongoInstrumentor().instrument()
