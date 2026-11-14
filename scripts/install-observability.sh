#!/usr/bin/env bash
# Installe la stack d'observabilité dans le namespace "monitoring" (Kind doit tourner).
# Usage : bash scripts/install-observability.sh
set -euo pipefail
cd "$(dirname "$0")/.."
D=k8s/observability

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null
helm repo update >/dev/null

echo "==> 1/4 Loki (logs)"
helm upgrade --install loki oci://ghcr.io/grafana-community/helm-charts/loki \
  -n monitoring -f $D/loki-values.yaml --wait --timeout 5m

echo "==> 2/4 Tempo (traces)"
helm upgrade --install tempo oci://ghcr.io/grafana-community/helm-charts/tempo \
  --version 2.3.0 -n monitoring -f $D/tempo-values.yaml --wait --timeout 5m

echo "==> 3/4 kube-prometheus-stack (Prometheus + Alertmanager + Grafana)"
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring -f $D/kps-values.yaml --wait --timeout 10m

echo "==> 4/4 Alloy (collecte des logs -> Loki)"
helm upgrade --install alloy grafana/alloy -n monitoring -f $D/alloy-values.yaml --wait --timeout 5m

echo
echo "OK. Grafana : http://localhost:9090  (admin / admin)"
kubectl get pods -n monitoring
