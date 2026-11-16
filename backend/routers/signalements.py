# Endpoints des signalements
import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai import score_urgence
from db import connect

router = APIRouter(prefix="/signalements", tags=["signalements"])

MAX_PHOTO = 110 * 1024  # 110 Ko
LIMITE = 5              # signalements par minute et par IP
FENETRE = 60
_hits: dict[str, deque] = defaultdict(deque)  # IP -> horodatages (en mémoire)



class SignalementIn(BaseModel):
    point_id: int
    type: Literal["panne", "eau_trouble", "faible_debit", "autre"]
    texte: str | None = Field(default=None, max_length=500)
    photo_b64: str | None = None


def limite_ip(ip: str):
    # Fenêtre glissante d'une minute
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > FENETRE:
        q.popleft()
    if len(q) >= LIMITE:
        raise HTTPException(status_code=429, detail="Trop de signalements, réessayez plus tard")
    q.append(now)


@router.post("", status_code=201)
def creer(data: SignalementIn, request: Request):
    limite_ip(request.client.host if request.client else "inconnu")
    if data.photo_b64 and len(data.photo_b64) > MAX_PHOTO:
        raise HTTPException(status_code=413, detail="Photo trop lourde")
    with connect() as conn:
        point = conn.execute(
            "SELECT quartier, type FROM points WHERE id = %s", (data.point_id,)
        ).fetchone()
        if point is None:
            raise HTTPException(status_code=404, detail="Point introuvable")
        # Contexte pour le score IA : signalements ouverts et ancienneté (heures)
        ctx = conn.execute(
            """SELECT count(*) AS n,
                      COALESCE(EXTRACT(EPOCH FROM now() - min(cree_le)) / 3600, 0) AS age_h
               FROM signalements WHERE point_id = %s AND statut = 'ouvert'""",
            (data.point_id,),
        ).fetchone()
        urgence, raison = score_urgence(data.type, data.texte, ctx["n"],
                                        point["type"], float(ctx["age_h"]))
        row = conn.execute(
            """INSERT INTO signalements (point_id, type, texte, photo_b64, quartier, urgence)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id, point_id, type, texte, quartier, urgence, statut, cree_le""",
            (data.point_id, data.type, data.texte, data.photo_b64,
             point["quartier"], urgence),
        ).fetchone()
        row["raison"] = raison  # explication renvoyée (non stockée)
        if data.type == "panne":
            conn.execute(
                "UPDATE points SET etat = 'panne', maj_le = now() WHERE id = %s",
                (data.point_id,),
            )
    return row


@router.get("")
def liste(statut: Literal["ouvert", "repare"] | None = None, quartier: str | None = None):
    # Filtres optionnels, tri urgence décroissante puis date
    sql = ("SELECT id, point_id, type, texte, quartier, urgence, statut, cree_le "
           "FROM signalements")
    where, params = [], []
    if statut:
        where.append("statut = %s")
        params.append(statut)
    if quartier:
        where.append("quartier = %s")
        params.append(quartier)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY urgence DESC, cree_le DESC"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()
