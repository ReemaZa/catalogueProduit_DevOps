# syntax=docker/dockerfile:1
# ---------- Étape 1 : "builder" (installe les dépendances) ----------
FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt .
# --prefix=/install : on isole les paquets pour les copier proprement dans l'image finale
RUN pip install --prefix=/install -r requirements.txt

# ---------- Étape 2 : image finale (petite, sans outils de build) ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

# Utilisateur NON-root (UID numérique : Kubernetes peut vérifier runAsNonRoot)
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /install /usr/local
COPY app ./app

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
