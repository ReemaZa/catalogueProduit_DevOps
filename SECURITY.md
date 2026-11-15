# Politique de sécurité

Ce dépôt est un projet pédagogique (TP DevOps) et n'est pas destiné à la production.

## Signaler une vulnérabilité
Merci d'utiliser **Security → Report a vulnerability** (signalement privé GitHub) plutôt qu'une issue publique.

## Bonnes pratiques appliquées
- Aucun secret dans le dépôt (GitHub Secrets / variables d'environnement uniquement).
- CI sur runners GitHub-hosted uniquement, permissions `contents: read` par défaut.
- Actions épinglées par SHA, mises à jour par Dependabot.
- Image Docker non-root, scan Trivy (CRITICAL = échec), politiques Gatekeeper.
- Services locaux liés à `127.0.0.1` ; mots de passe fournis à l'exécution, jamais en dur.
