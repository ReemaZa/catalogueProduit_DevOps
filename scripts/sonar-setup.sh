#!/usr/bin/env bash
# Crée la Quality Gate du TP via l'API SonarQube et l'attache au projet.
# Usage : SONAR_URL=http://localhost:9000 SONAR_ADMIN_PASSWORD=<ton mdp> ./scripts/sonar-setup.sh
set -euo pipefail
URL="${SONAR_URL:-http://localhost:9000}"
AUTH="admin:${SONAR_ADMIN_PASSWORD:?définis SONAR_ADMIN_PASSWORD}"
GATE="TP2-Gate"
PROJECT="catalogue-produit"
api() { curl -sf -u "$AUTH" -X POST "$URL/api/$1" "${@:2}"; }

echo ">> Création du projet (ignoré s'il existe)"
api projects/create -d "project=$PROJECT" -d "name=Catalogue Produit" >/dev/null || true

echo ">> Création de la gate $GATE"
api qualitygates/create -d "name=$GATE" >/dev/null || echo "(existe déjà)"

echo ">> Conditions exigées par le sujet (sur le NOUVEAU code)"
# Couverture du nouveau code < 85 %  => échec
api qualitygates/create_condition -d "gateName=$GATE" -d "metric=new_coverage" -d "op=LT" -d "error=85" >/dev/null || true
# Security Hotspots revus < 100 %  => échec (donc 1 hotspot non revu bloque)
api qualitygates/create_condition -d "gateName=$GATE" -d "metric=new_security_hotspots_reviewed" -d "op=LT" -d "error=100" >/dev/null || true
# Duplication du nouveau code > 3 %  => échec
api qualitygates/create_condition -d "gateName=$GATE" -d "metric=new_duplicated_lines_density" -d "op=GT" -d "error=3" >/dev/null || true

echo ">> Attache la gate au projet"
api qualitygates/select -d "gateName=$GATE" -d "projectKey=$PROJECT" >/dev/null

echo ">> Génère un token d'analyse (à copier dans le secret GitHub SONAR_TOKEN) :"
api user_tokens/generate -d "name=ci-$(date +%s)" -d "type=PROJECT_ANALYSIS_TOKEN" -d "projectKey=$PROJECT" || \
  echo "(génère-le à la main : My Account > Security)"
echo
echo "OK"
