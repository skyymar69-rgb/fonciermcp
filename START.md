# FoncierMCP — Démarrage en 3 commandes

## Prérequis
- Docker Desktop installé
- Un terminal

## Démarrage

```bash
cp .env.example .env
docker compose up --build
```

Ouvre http://localhost:8000

## Créer une clé API client

```bash
curl -X POST http://localhost:8000/api/key/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Secret: changeme" \
  -d '{"name": "Cabinet Dupont", "email": "dupont@notaire.fr", "plan": "pro"}'
```

© Kayzen Lyon — Tous droits réservés