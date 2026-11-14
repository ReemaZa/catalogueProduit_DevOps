"""Tests de l'instrumentation : format JSON des logs et activation conditionnelle des traces."""
import json
import logging
import sys

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.telemetry import JsonFormatter, setup_tracing


def _record(msg="bonjour", exc_info=None):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, exc_info)


def test_json_formatter_sans_trace():
    data = json.loads(JsonFormatter().format(_record()))
    assert data["message"] == "bonjour"
    assert data["level"] == "INFO"
    assert "trace_id" not in data


def test_json_formatter_avec_trace_id():
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("s"):
        data = json.loads(JsonFormatter().format(_record()))
        expected = format(trace.get_current_span().get_span_context().trace_id, "032x")
    assert data["trace_id"] == expected
    assert len(data["span_id"]) == 16


def test_json_formatter_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = _record(exc_info=sys.exc_info())
    assert "ValueError" in json.loads(JsonFormatter().format(rec))["exception"]


def test_setup_tracing_noop_sans_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    setup_tracing(FastAPI())  # ne doit rien lever


def test_setup_tracing_active_avec_endpoint(monkeypatch):
    """Avec un endpoint OTLP, le TracerProvider est configuré et l'app instrumentée."""
    from opentelemetry.sdk.trace.export import SpanExporter

    import app.telemetry as telemetry

    class FakeExporter(SpanExporter):
        def export(self, spans):
            return 0

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", FakeExporter)
    telemetry.setup_tracing(FastAPI())


def test_setup_metrics_otlp(monkeypatch):
    """Avec un endpoint de métriques, un MeterProvider OTel est installé."""
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: F401

    import app.telemetry as telemetry

    class FakeMetricExporter:
        _preferred_temporality = {}
        _preferred_aggregation = {}

        def export(self, *a, **k):
            return None

        def force_flush(self, *a, **k):
            return True

        def shutdown(self, *a, **k):
            return None

    captured = {}

    class FakeReader:
        def __init__(self, exporter, **kwargs):
            captured["exporter"] = exporter

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://localhost:9090/x")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(telemetry, "OTLPMetricExporter", FakeMetricExporter)
    monkeypatch.setattr(telemetry, "PeriodicExportingMetricReader", FakeReader)
    monkeypatch.setattr(telemetry.metrics, "set_meter_provider", lambda p: captured.update(p=p))
    monkeypatch.setattr(telemetry, "MeterProvider", lambda **kw: kw)
    telemetry.setup_tracing(FastAPI())
    assert isinstance(captured["exporter"], FakeMetricExporter)
