# Endpoints des points d'eau
from fastapi import APIRouter, HTTPException

from db import connect

router = APIRouter(prefix="/points", tags=["points"])

COLS = "id, nom, type, quartier, lat, lon, etat, maj_le"


@router.get("")
def liste_points(quartier: str | None = None):
    # Filtre optionnel par quartier
    sql = f"SELECT {COLS} FROM points"
    params = []
    if quartier:
        sql += " WHERE quartier = %s"
        params.append(quartier)
    sql += " ORDER BY id"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


@router.get("/{point_id}")
def un_point(point_id: int):
    with connect() as conn:
        row = conn.execute(
            f"SELECT {COLS} FROM points WHERE id = %s", (point_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Point introuvable")
    return row
