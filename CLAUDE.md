# Mawjoud — Nuit de l'Info
Objectif : app web légère (3G) pour trouver, signaler et suivre les points d'eau à Nouakchott. FR/AR (RTL).

## Stack
- Front : HTML/CSS/JS pur, seule lib = Leaflet. Déployé sur Vercel. Page < 500 Ko.
- Back : Python FastAPI + psycopg (SQL paramétré). Déployé sur Render.
- Base : PostgreSQL via DATABASE_URL (jamais SQLite).

## Dossiers
- backend/ : main.py, db.py, schema.sql, seed.sql, routers/, ai.py, tests/
- frontend/ : index.html, report.html, admin.html, conseils.html, js/, css/, i18n/
- docs/ : FONCTIONNALITES.md, SECURITE.md, GREENIT.md

## Données
- points(id, nom, type[puits|borne|citerne], quartier, lat, lon, etat[ok|faible|panne], maj_le)
- signalements(id, point_id, type[panne|eau_trouble|faible_debit|autre], texte, photo_b64, quartier, urgence 0-100, statut[ouvert|repare], cree_le)

## Règles
- Ne modifier que les fichiers cités dans la tâche. Pas de refonte, pas de nouvelle dépendance sans demande.
- Code simple, commentaires courts en français. Ne pas générer de documentation.
- SQL toujours paramétré. Secrets dans .env uniquement (DATABASE_URL, ADMIN_PASSWORD).
- Tout texte visible passe par i18n (clés fr/ar), jamais en dur dans le HTML/JS.
- Photos compressées côté client, 80 Ko maximum.
- Réponses courtes : résumer en 3 lignes ce qui a changé.

## Commandes
- Back : cd backend && uvicorn main:app --reload (port 8000)
- Test : curl localhost:8000/health ; pytest -q backend
- Front : cd frontend && python -m http.server 5500 (API_URL dans js/config.js)

## Git
- Une branche par groupe, petits commits, jamais de push direct sur main.
