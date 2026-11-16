# Données Mawjoud

> Les données sont **simulées** (jeu de démonstration) : noms, positions et états des points ne reflètent pas la réalité.

- **points** : `id`, `nom`, `type` (puits | borne | citerne), `quartier`, `lat`/`lon` (WGS84), `etat` (ok | faible | panne), `maj_le`.
- **signalements** : `id`, `point_id`, `type` (panne | eau_trouble | faible_debit | autre), `texte` (≤ 500 car.), `photo_b64` (JPEG ≤ 80 Ko), `quartier`.
- `urgence` (0-100) : score explicable calculé par `ai.py` (type, mots-clés FR/AR/Darija, signalements ouverts sur le point, borne publique, ancienneté).
- `statut` (ouvert | repare) et `cree_le` (date UTC) : suivi du traitement.
- **/stats** : pannes ouvertes par quartier, pannes signalées par jour (7 jours, tous statuts), total des signalements ouverts.
- Graphiques admin : barres par quartier, courbe sur 7 jours, carte de chaleur quartier × jour des pannes ouvertes.
- Aucune donnée personnelle n'est stockée (ni nom, ni téléphone, ni position de l'utilisateur).
