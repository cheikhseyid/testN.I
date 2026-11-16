-- 15 points d'eau, 3 par quartier (inséré seulement si la table est vide)
INSERT INTO points (nom, type, quartier, lat, lon, etat)
SELECT * FROM (VALUES
    ('Borne Carrefour Madrid',     'borne',   'Tevragh Zeina', 18.1035, -15.9745, 'ok'),
    ('Puits Ilot K',               'puits',   'Tevragh Zeina', 18.1120, -15.9810, 'faible'),
    ('Citerne Marché Capitale',    'citerne', 'Tevragh Zeina', 18.0960, -15.9690, 'ok'),
    ('Borne Carrefour Arafat',     'borne',   'Arafat',        18.0480, -15.9420, 'panne'),
    ('Puits Secteur 4',            'puits',   'Arafat',        18.0410, -15.9510, 'ok'),
    ('Citerne Marché Arafat',      'citerne', 'Arafat',        18.0530, -15.9380, 'faible'),
    ('Borne Dar Naïm Centre',      'borne',   'Dar Naïm',      18.1180, -15.9280, 'ok'),
    ('Puits Hay Saken',            'puits',   'Dar Naïm',      18.1250, -15.9200, 'panne'),
    ('Citerne Route de l''Espoir', 'citerne', 'Dar Naïm',      18.1090, -15.9150, 'faible'),
    ('Borne Toujounine Marché',    'borne',   'Toujounine',    18.0720, -15.8930, 'faible'),
    ('Puits Carrefour Toujounine', 'puits',   'Toujounine',    18.0650, -15.8850, 'ok'),
    ('Citerne Route de Boutilimit','citerne', 'Toujounine',    18.0790, -15.8780, 'panne'),
    ('Borne Marché Sebkha',        'borne',   'Sebkha',        18.0790, -16.0020, 'ok'),
    ('Puits Cinquième',            'puits',   'Sebkha',        18.0720, -16.0110, 'faible'),
    ('Citerne Port de Pêche',      'citerne', 'Sebkha',        18.0650, -16.0200, 'ok')
) AS v(nom, type, quartier, lat, lon, etat)
WHERE NOT EXISTS (SELECT 1 FROM points);
