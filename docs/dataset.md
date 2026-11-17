# Jeux de données simulés (backend/data/)

**points.csv** (40 lignes) : `nom, type (puits|borne|citerne), quartier, lat, lon, etat, potable`. 9 quartiers de Nouakchott, coordonnées tirées à ±0,007° du centre de chaque quartier. L'`etat` du CSV n'est qu'une valeur de départ : il est recalculé à partir des signalements ouverts (voir plus bas).

**historique.csv** (400 lignes) : `point_nom, type (panne|faible_debit|eau_trouble|autre), texte, urgence (haute|moyenne|basse), score_urgence, statut (ouvert|repare), cree_le, repare_le` (UTC, ISO 8601). Le point est désigné par son nom, car les id dépendent de l'ordre d'insertion.

Règles de simulation (générateur à graine fixe, donc reproductible) :
- 8 semaines, de 6 h à 22 h ; volume croissant chaque semaine (×2,4 entre la 1re et la 8e) pour simuler l'arrivée de la saison chaude, avec plus de pannes et de faibles débits en fin de période. Arafat (poids 2,4) et Dar Naim (2,2) cumulent ~43 % des signalements.
- Urgence et score dépendent du type ; 70 % de signalements réparés dans le CSV, avec une durée log-normale (médiane de 12 h pour l'eau trouble à 30 h pour une panne).

Au chargement, `seed.py` **recale les dates** sur aujourd'hui : le signalement le plus récent est placé à « maintenant − 1 jour », et les écarts entre dates sont conservés. Les signalements encore ouverts depuis **plus de 14 jours** sont marqués `repare` (avec la durée médiane de leur type). L'`etat` de chaque point est ensuite déduit de ses signalements ouverts : `panne` s'il y a une panne ouverte, sinon `faible` s'il y a un faible débit ouvert, sinon `ok`.

Base en ligne : `python seed.py --recalcul` refait ce calcul (relancer de temps en temps pour garder « cette semaine » à jour). Seuls les 400 signalements simulés sont décalés ou clos : leurs id sont listés dans la table `seed_historique`, que le script remplit lui-même dans une base plus ancienne, en comparant exactement avec le CSV. Les vrais signalements ne sont ni modifiés ni effacés ; ils comptent seulement dans le calcul de l'`etat` des points.

Limites : données inventées, à ne pas présenter comme réelles. Après recalcul, ~26 points sur 40 sont en panne (beaucoup de pannes récentes encore ouvertes). « Pannes cette semaine » dépend du jour : le lundi, la veille appartient à la semaine précédente. Pas de photos, de doublons, de jours fériés ni de coupures générales.
