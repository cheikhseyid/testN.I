# IA : urgence des signalements

**But** : classer chaque nouveau signalement en `haute` / `moyenne` / `basse`, à partir du texte (FR, arabe, hassaniya translittéré) et du type. Appelé dans `POST /signalements` (`app/ia/classifier.py`).

**Modèle** : texte normalisé (minuscules, accents et signes diacritiques arabes retirés, ة→ه) → TF-IDF sur les caractères (n-grammes 2-4, `char_wb`), qui résiste aux fautes et aux translittérations ; le type est encodé en one-hot. Classifieur `LogisticRegression(class_weight="balanced", C=20)`. `score_urgence` = P(haute) + 0,5 × P(moyenne), entre 0 et 1 (il sert au tri). Le modèle est chargé une seule fois. Si `model.joblib` manque ou ne se charge pas : ("moyenne", 0,5), sans erreur pour l'utilisateur.

**Règle de sécurité** : si le texte contient « malade », « مريض », « odeur » ou « رائحة » (y compris les formes normalisées comme malades, مريضة, رائحه), l'urgence est forcée à `haute` avec un score ≥ 0,9, quoi que dise le modèle.

**Données** : `data/entrainement_ia.csv`, 300 exemples **simulés** (115 haute, 109 moyenne, 76 basse), 45 % FR, 30 % AR, 25 % hassaniya, avec des fautes, des majuscules et des mélanges de langues. L'étiquette suit des règles : le type donne le niveau de base, +1 pour une longue durée ou des personnes fragiles (école, centre de santé, tout le quartier), −1 pour « pas grave », et la santé ou l'odeur donnent toujours `haute`.

**Résultats** (`python -m app.ia.train`, test 20 % = 60 exemples) : exactitude 0,70, F1 macro 0,70 ; rappel `haute` 0,61, avec 2 cas `haute` classés `basse`. En validation croisée (5 plis), le F1 macro va de 0,65 à 0,71 selon les réglages : le facteur limitant est la taille des données, pas les réglages. Le modèle final est réentraîné sur les 300 exemples. Sur le test, la règle ne change rien : les erreurs restantes viennent de la durée ou des personnes fragiles, pas de la santé.

**Limites** :
- Les données sont simulées : les chiffres ci-dessus mesurent la cohérence avec nos propres règles, pas la performance sur le terrain.
- Pas d'analyse de photo ; la négation est mal comprise (« pas d'odeur » déclenche la règle).
- Vocabulaire hassaniya limité et orthographe non standard.
- `model.joblib` dépend de la version de scikit-learn : il faut la figer, ou réentraîner au déploiement.
- **À réentraîner avec de vrais signalements** étiquetés par l'équipe (au moins quelques centaines par classe), puis à surveiller : part de `haute`, signalements requalifiés à la main.
