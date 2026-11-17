# Fonctionnalités réalisées — Mawjoud, l'eau, un bien partagé

Aider les habitants à trouver, signaler et partager l'eau.
En local : site sur http://localhost:5501, API sur http://localhost:8000 (voir README). Tests back-end : `cd backend && pytest -q` (113 tests).

## Fonctionnalités obligatoires

| # | Énoncé | Statut | Ce qui est fait / où tester |
|---|---|---|---|
| 1 | Carte des points d'eau avec état (🟢 fonctionne, 🟠 faible débit, 🔴 panne) | ✅ Fait | `index.html` : liste 🟢🟠🔴 triée par distance, puis « Voir la carte » (Leaflet, marqueurs colorés selon l'état, popup avec un bouton « Signaler ») · `GET /points` |
| 2 | Signalement citoyen (texte + photo si possible) | ✅ Fait | `signaler.html` : point pré-rempli, 4 types, texte facultatif, photo compressée dans le navigateur (< 300 Ko) · `POST /signalements` · `tests/test_signalements.py` |
| 3 | Tableau de bord responsables : voir, trier par urgence, marquer « réparé » | ✅ Fait | `dashboard.html` (connexion admin) : signalements ouverts triés par urgence (IA), miniature de la photo, bouton « Réparé » ; le point redevient vert quand tous ses signalements sont clôturés · `tests/test_auth.py` |
| 4 | Conseils d'économie d'eau adaptés au contexte local | ✅ Fait | `conseils.html` : 12 conseils pour Nouakchott (bidons fermés, ablutions à la bouilloire, eau des légumes, Javel, charrettes et citernes…), en FR et en AR |
| 5 | Fonctionne avec un mauvais réseau (page principale < 5 s en 3G sur Android bas de gamme) | 🟡 Partiel | Page d'accueil : 16,6 Ko et 9 requêtes ; liste en cache pour un affichage immédiat et une consultation hors ligne ; carte chargée seulement au clic. Liste visible en **≈ 4,3 s estimées** en Slow 3G, **non mesurées sur un vrai Android bas de gamme** · `docs/green-it.md` |

## Bonus

| Énoncé | Statut | Où tester |
|---|---|---|
| Alerte de pénurie quand plusieurs points d'un quartier sont en panne | ✅ Fait | Au moins 3 points en panne dans un quartier : `GET /alertes` (public), bandeau rouge en haut de `index.html` (« ⚠️ Pénurie à Arafat : 3 points en panne »), alerte aussi sur `dashboard.html` · `tests/test_stats.py` |

## Livrables

| Livrable | Statut |
|---|---|
| URL publique | 🟡 Partiel : API en ligne sur https://mawjoud-api-danc.onrender.com (Render) ; site sur Vercel à déployer |
| Code GitHub | 🟡 https://github.com/cheikhseyid/testN.I, branche `main`. Le dépôt est **privé** : à passer en public (Settings → Danger Zone → Change visibility) pour que le jury y ait accès |
| Document des fonctionnalités réalisées | ✅ Ce fichier |

## Défis choisis

| # | Défi | Statut | Contenu / où tester |
|---|---|---|---|
| 1 | IA utile (démo + modèle + limites) | ✅ Fait | Démo : `POST /signalements` avec « l'eau sent mauvais, mon enfant est malade » → `haute`. Modèle : TF-IDF sur les caractères + régression logistique, FR / AR / hassaniya, avec une règle de sécurité (`python -m app.ia.train`). Limites : `docs/ia.md` (données simulées, exactitude de 0,70) · `tests/test_ia.py` |
| 2 | Data & visualisation (page + jeu de données documenté) | ✅ Fait | Page `dashboard.html` : chiffres clés, 3 graphiques Chart.js et une carte de chaleur, à partir de `GET /stats`. Jeu de données : `docs/dataset.md` (40 points, 400 signalements simulés) |
| 4 | Pitch 3 min | ❌ Non fait | En dehors du code : à préparer par l'équipe |
| 6 | Green IT (rapport poids / requêtes) | ✅ Fait | `docs/green-it.md` : tableau avant / après, 16,6 Ko et 9 requêtes sans carte, au plus 199 Ko avec la carte. Temps en 3G estimés, pas mesurés |
| 7 | Bilingue FR / AR avec RTL (app + liste des textes traduits) | ✅ Fait | Bouton « عربي » sur toutes les pages : textes, carte, popups, graphiques et quartiers en arabe, de droite à gauche · `docs/traductions.md` (161 clés) |
