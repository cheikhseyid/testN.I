# Accessibilité — Mawjoud

- **Texte** : taille de base 18 px (`html { font-size: 18px }`), interligne 1,5.
- **Contraste AA** : texte #12324a sur #f4f8fb, liens #0a5a86, boutons blancs sur #0b6fa4 (≥ 4,5:1).
- **Focus visible** : contour orange de 3 px sur tout élément atteint au clavier (blanc dans l'en-tête).
- **Cibles tactiles** : boutons, liens de navigation et champs ≥ 44 × 44 px.
- **Formulaires** : chaque champ est entouré d'un `<label>`.
- **Clavier** : lien « Aller au contenu », ordre de tabulation naturel ; flèches ←/→ pour changer de conseil (inversées en arabe).
- **Lecture vocale** : bouton « Écouter » (speechSynthesis, voix fr-FR ou ar-SA), désactivable ; message si l'appareil n'a pas de voix.
- **Lecteurs d'écran** : `lang` et `dir="rtl"` mis à jour, zones `aria-live` pour le bandeau et le conseil affiché.
- **Mouvement réduit** : animations coupées si `prefers-reduced-motion`.
