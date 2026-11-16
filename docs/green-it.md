# Green IT — page d'accueil (index.html)

Objectifs : sans la carte, **< 150 Ko et < 10 requêtes** ; avec la carte, **< 500 Ko**.

## Mesures avant / après

| Indicateur | Avant | Après | Comment c'est obtenu |
|---|---|---|---|
| Poids sans carte, compressé (comme en production) | 20,4 Ko | **16,6 Ko** | mesuré : fichiers statiques en gzip -9 + réponses réelles de l'API |
| Poids sans carte, non compressé (serveur local) | 48,4 Ko | 48,8 Ko | mesuré : taille des fichiers + réponses de l'API |
| Requêtes sans carte (Chrome) | 10 (dont `/favicon.ico` en 404) | **9** | mesuré : Resource Timing + favicon |
| Poids avec carte, mobile 375 px (6 tuiles) | 120,4 Ko | **116,7 Ko** | calculé : Leaflet mesuré + 6 × la taille moyenne mesurée d'une tuile |
| Poids avec carte, écran 1366 px (15 tuiles OSM / satellite) | 203,0 / 201,2 Ko | **199,2 / 197,5 Ko** | mesuré : les 15 tuiles téléchargées |
| Requêtes avec carte (mobile / 1366 px) | 18 / 27 | **17 / 26** | mesuré |
| Liste visible en Slow 3G | ≈ 4,4 s | **≈ 4,3 s** | **estimé**, voir ci-dessous |
| Page complète en Slow 3G (textes traduits, alertes) | ≈ 6,4 s | **≈ 6,3 s** | **estimé** |
| Affichage de la carte après le clic, Slow 3G (mobile / 1366 px) | ≈ 6,1 / 7,7 s | ≈ 6,1 / 7,7 s | **estimé** |
| Éléments du DOM (entrée de l'EcoIndex) | 250 | 250 | mesuré |
| `/points` / `/stats` (réponses de l'API) | 4,8 Ko / 1,2 Ko | **0,9 Ko / 0,4 Ko** | mesuré avec `Accept-Encoding: gzip` |

**Les 3 objectifs sont atteints** : 16,6 Ko et 9 requêtes sans la carte, et au plus 199 Ko avec la carte, même sur grand écran.

Méthode de l'estimation Slow 3G : profil DevTools (50 000 octets/s en réception, 2 s de latence par requête). Le temps est la somme des étapes en cascade : HTML, puis CSS, JS et `/points` en parallèle, puis `fr.json` et `/alertes`. **Ce ne sont pas des mesures** : à remplacer par les valeurs DevTools ou EcoIndex (non fournies). L'EcoIndex demande une URL publique (ecoindex.fr), à mesurer après le déploiement sur Vercel.

## Ce qui a changé
- **API** : `GZipMiddleware` (au-delà de 500 octets). C'est le seul gain notable : −81 % sur `/points`.
- **Favicon** : un emoji 💧 en SVG directement dans `index.html`, ce qui supprime une requête (la 10e) qui finissait en 404.
- **Scripts** déplacés dans `<head>` avec `defer` : ils ne bloquent plus l'affichage. Ils étaient déjà en fin de page, donc aucun gain mesurable sur le réseau.
- **CSS** de la page sorti de `index.html` vers `style.css`, un fichier mis en cache et partagé entre les pages.

## Déjà en place avant (l'essentiel du résultat)
Aucun framework ni police externe ; des emojis à la place des icônes et des images. La carte Leaflet (45 Ko) n'est chargée qu'au clic. `/points` est préchargé et gardé en cache dans `localStorage` pour les visites suivantes. Le cache HTTP de Vercel est de 7 jours pour css/js/i18n.

## Limites
- Les tuiles de carte font ~70 % du poids avec la carte. Pour aller plus loin : un zoom initial plus serré, ou une vignette statique de la carte.
- La compression des fichiers statiques est estimée avec gzip -9 ; Vercel sert du brotli, un peu plus petit. En local, `python -m http.server` ne compresse pas (≈ 49 Ko).
