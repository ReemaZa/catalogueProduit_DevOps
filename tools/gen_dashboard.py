"""Génère le dashboard Grafana SRE (RED + Error Budget) sous forme de ConfigMap Kubernetes.

Usage : python3 tools/gen_dashboard.py > k8s/observability/dashboard-sre.yaml
Le sidecar de Grafana charge automatiquement toute ConfigMap portant le label grafana_dashboard=1.
"""
import json

PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}
SEL = 'namespace="catalog",path!~"/health|/ready"'
_id = 0


def _next():
    global _id
    _id += 1
    return _id


def target(expr, legend="", ds=PROM):
    return {"datasource": ds, "expr": expr, "legendFormat": legend, "refId": chr(64 + 1)}


def panel(kind, title, x, y, w, h, exprs, unit=None, extra=None, ds=PROM):
    targets = []
    for i, (e, legend) in enumerate(exprs):
        targets.append({"datasource": ds, "expr": e, "legendFormat": legend, "refId": chr(65 + i)})
    p = {
        "id": _next(), "type": kind, "title": title, "datasource": ds,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
        "fieldConfig": {"defaults": {"unit": unit} if unit else {}, "overrides": []},
        "options": {},
    }
    if extra:
        for k, v in extra.items():
            if k in ("fieldConfig_defaults",):
                p["fieldConfig"]["defaults"].update(v)
            else:
                p[k] = v
    return p


def thresholds(steps):
    return {"thresholds": {"mode": "absolute", "steps": [
        {"color": c, "value": v} for c, v in steps]}}


ERR = f'sum(rate(http_requests_total{{{SEL},status=~"5.."}}[5m]))'
TOT = f'sum(rate(http_requests_total{{{SEL}}}[5m]))'


def LAT(q):  # noqa: N802
    return (f'histogram_quantile({q}, sum by (le) '
            f'(rate(http_request_duration_seconds_bucket{{{SEL}}}[5m])))')


panels = [
    # --- Ligne 1 : RATE ---
    panel("stat", "Rate : requêtes/s (RPS)", 0, 0, 6, 4, [(TOT, "RPS")], "reqps"),
    panel("timeseries", "Rate : RPS par endpoint", 6, 0, 18, 8,
          [(f'sum by (path) (rate(http_requests_total{{{SEL}}}[1m]))', "{{path}}")], "reqps"),
    # --- Errors ---
    panel("stat", "Errors : % d'erreurs global (5m)", 0, 4, 6, 4,
          [(f'100 * ({ERR} or vector(0)) / {TOT}', "% erreurs")], "percent",
          {"fieldConfig_defaults": thresholds([("green", None), ("orange", 0.5), ("red", 5)])}),
    panel("timeseries", "Errors : erreurs 5xx par seconde", 0, 8, 12, 8,
          [(f'sum by (path) (rate(http_requests_total{{{SEL},status=~"5.."}}[1m]))', "{{path}}")], "reqps"),
    panel("timeseries", "Errors : % d'erreurs (1 min)", 12, 8, 12, 8,
          [(f'100 * (sum(rate(http_requests_total{{{SEL},status=~"5.."}}[1m])) or vector(0)) '
            f'/ sum(rate(http_requests_total{{{SEL}}}[1m]))', "% erreurs")], "percent"),
    # --- Duration ---
    panel("timeseries", "Duration : latence p50 / p90 / p95 / p99", 0, 16, 16, 9,
          [(LAT(0.5), "p50"), (LAT(0.9), "p90"), (LAT(0.95), "p95"), (LAT(0.99), "p99")], "s",
          {"fieldConfig_defaults": {"custom": {"thresholdsStyle": {"mode": "line"}},
                                    **thresholds([("green", None), ("red", 0.2)])}}),
    panel("stat", "SLI latence : % requêtes < 200 ms (SLO : 95 %)", 16, 16, 8, 4,
          [("100 * catalog:sli_latency_under200ms:ratio5m", "< 200 ms")], "percent",
          {"fieldConfig_defaults": {"min": 0, "max": 100, **thresholds([("red", None), ("orange", 90), ("green", 95)])}}),
    panel("stat", "p95 actuel (SLO : <= 200 ms)", 16, 20, 8, 5, [(LAT(0.95), "p95")], "s",
          {"fieldConfig_defaults": thresholds([("green", None), ("red", 0.2)])}),
    # --- ERROR BUDGET ---
    panel("gauge", "Error Budget restant (SLO 99,5 %, fenêtre 30 j)", 0, 25, 8, 8,
          [("100 * catalog:error_budget_remaining:ratio", "budget restant")], "percent",
          {"fieldConfig_defaults": {"min": 0, "max": 100,
                                    **thresholds([("red", None), ("orange", 25), ("green", 50)])}}),
    panel("stat", "Burn rate (1 h)", 8, 25, 4, 8, [("catalog:burn_rate:1h", "burn rate 1h")], "none",
          {"fieldConfig_defaults": thresholds([("green", None), ("orange", 6), ("red", 14.4)])}),
    panel("timeseries", "Burn rate : 5 m / 1 h / 6 h (seuils 6 et 14,4)", 12, 25, 12, 8,
          [("catalog:sli_error_ratio:rate5m / 0.005", "5m"),
           ("catalog:sli_error_ratio:rate1h / 0.005", "1h"),
           ("catalog:sli_error_ratio:rate6h / 0.005", "6h"),
           ("vector(14.4)", "seuil critical 14.4"), ("vector(6)", "seuil warning 6")], "none"),
    # --- LOGS corrélés ---
    panel("logs", "Logs de l'application (clic sur trace_id -> Tempo)", 0, 33, 24, 10,
          [('{namespace="catalog", container="api"}', "")], None,
          {"options": {"showTime": True, "wrapLogMessage": True, "enableLogDetails": True}}, ds=LOKI),
]

dashboard = {
    "uid": "catalog-sre", "title": "Catalog API — SRE (RED + Error Budget)",
    "tags": ["sre", "catalog"], "timezone": "browser", "schemaVersion": 39, "version": 1,
    "refresh": "10s", "time": {"from": "now-30m", "to": "now"}, "panels": panels,
}

body = json.dumps(dashboard, indent=2, ensure_ascii=False)
indented = "\n".join("    " + line for line in body.splitlines())
print(f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: catalog-sre-dashboard
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  catalog-sre.json: |
{indented}""")
