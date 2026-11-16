# Accès PostgreSQL (psycopg 3)
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ICI = Path(__file__).resolve().parent


def connect():
    # Connexion avec lignes en dict
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    # Crée les tables puis insère le seed si vide
    with connect() as conn:
        conn.execute((ICI / "schema.sql").read_text(encoding="utf-8"))
        conn.execute((ICI / "seed.sql").read_text(encoding="utf-8"))
