# Jeux de données simulés (backend/data/)

**points.csv** (40 lignes) : `nom, type (puits|borne|citerne), quartier, lat, lon, etat (ok|faible|panne), potable`. 9 quartiers de Nouakchott, coordonnées tirées à ±0,007° du centre de chaque quartier ; états 24 ok / 10 faible / 6 panne.

**historique.csv** (400 lignes) : `point_nom, type (panne|faible_debit|eau_trouble|autre), texte, urgence (haute|moyenne|basse), score_urgence, statut (ouvert|repare), cree_le, repare_le` (UTC, ISO 8601). Le point est désigné par son nom, car les id dépendent de l'ordre d'insertion.

Règles de simulation (générateur à graine fixe, donc reproductible) :
- 8 semaines, du lundi 6 avril au 31 mai 2026, de 6 h à 22 h ; volume croissant chaque semaine (×2,4 entre la 1re et la 8e) pour simuler l'arrivée de la saison chaude, avec plus de pannes et de faibles débits sur les 4 dernières semaines.
- Poids par quartier : Arafat 2,4 et Dar Naim 2,2, contre 0,5 à 1,2 ailleurs. Ces deux quartiers totalisent ~43 % des signalements.
- Urgence et score dépendent du type (une panne est surtout « haute »).
- Exactement 70 % réparés (280), les plus anciens en priorité ; durée log-normale avec une médiane de 12 h (eau trouble) à 30 h (panne). Moyenne ≈ 26,5 h.

Limites : données inventées, à ne pas présenter comme réelles. Les ~120 signalements « ouverts » ne sont pas synchronisés avec `etat` dans points.csv. Pas de photos ni de doublons, pas de jours fériés ni de coupures de réseau générales. `seed.py` ne charge l'historique que si la table `signalements` est vide.
