-- Tables Mawjoud (idempotent)
CREATE TABLE IF NOT EXISTS points (
    id SERIAL PRIMARY KEY,
    nom TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('puits', 'borne', 'citerne')),
    quartier TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    etat TEXT NOT NULL DEFAULT 'ok' CHECK (etat IN ('ok', 'faible', 'panne')),
    maj_le TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signalements (
    id SERIAL PRIMARY KEY,
    point_id INTEGER REFERENCES points(id) ON DELETE SET NULL,
    type TEXT NOT NULL CHECK (type IN ('panne', 'eau_trouble', 'faible_debit', 'autre')),
    texte TEXT,
    photo_b64 TEXT,
    quartier TEXT,
    urgence INTEGER NOT NULL DEFAULT 0 CHECK (urgence BETWEEN 0 AND 100),
    statut TEXT NOT NULL DEFAULT 'ouvert' CHECK (statut IN ('ouvert', 'repare')),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_points_quartier ON points(quartier);
CREATE INDEX IF NOT EXISTS idx_signalements_point ON signalements(point_id);
