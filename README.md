# Mawjoud — trouver, signaler et suivre les points d'eau à Nouakchott

Application web légère (FR / عربي) : FastAPI + PostgreSQL pour l'API, HTML/CSS/JS sans framework pour le site.

**Code** : https://github.com/cheikhseyid/testN.I. **API** : https://mawjoud-api-danc.onrender.com (Render, `render.yaml`). **Site** : *URL Vercel à compléter* (dossier `frontend`).

**Lancer en local** (Python 3.12 et Docker) :
1. Base : `docker run -d --name eau-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=eau -p 5432:5432 postgres:16`
2. API : `cd backend && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`, puis copier `.env.example` en `.env` et y ajouter `JWT_SECRET`, `ADMIN_EMAIL` et `ADMIN_PASSWORD`
3. Données et admin : `.venv\Scripts\python seed.py` (ajouter `--reset` pour tout recharger)
4. Démarrer l'API : `.venv\Scripts\python -m uvicorn app.main:app --port 8000`
5. Site : `python -m http.server 5501 --directory frontend`, puis ouvrir http://localhost:5501
6. Tests : `cd backend && .venv\Scripts\python -m pytest -q`

**Compte de démo** (`dashboard.html`) : `admin@mawjoud.test`. Le mot de passe n'est **pas** dans le dépôt : c'est la valeur de `ADMIN_PASSWORD` (`.env` en local, variable Render en ligne), à demander à l'équipe.

Docs : [fonctionnalités](docs/fonctionnalites.md) · [traductions](docs/traductions.md) · [IA](docs/ia.md) · [données](docs/dataset.md) · [Green IT](docs/green-it.md)
