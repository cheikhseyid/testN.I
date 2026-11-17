from datetime import datetime, timezone

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, defer

from ..auth import get_admin
from ..db import get_db
from ..ia.classifier import predict as predict_urgence
from ..models import Admin, PointEau, Signalement
from ..schemas import SignalementOut, StatutSignalement, TypeSignalement

router = APIRouter(prefix="/signalements", tags=["signalements"])

# Shared limiter: main.py registers it on app.state and adds the 429 handler.
limiter = Limiter(key_func=get_remote_address)

MAX_PHOTO_BYTES = 300 * 1024
ETAT_PAR_TYPE = {"panne": "panne", "faible_debit": "faible"}


def _image_type(data: bytes) -> str | None:
    """Detect JPEG/PNG from magic bytes (the client's Content-Type is not trusted)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


async def _read_photo(photo: UploadFile | None) -> bytes | None:
    if photo is None or not photo.filename:
        return None  # champ absent ou vide
    data = await photo.read(MAX_PHOTO_BYTES + 1)
    if not data:
        return None
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Photo trop lourde (300 Ko maximum)")
    if _image_type(data) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Format de photo non accepté (JPEG ou PNG uniquement)")
    return data


@router.post("", response_model=SignalementOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_signalement(
    request: Request,  # required by slowapi
    point_id: int = Form(...),
    type: TypeSignalement = Form(...),
    texte: str = Form("", max_length=500),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    point = db.get(PointEau, point_id)
    if point is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Point d'eau introuvable")

    photo_bytes = await _read_photo(photo)
    texte = texte.strip()
    urgence, score = predict_urgence(texte, type)  # never raises: falls back to ("moyenne", 0.5)

    sig = Signalement(
        point_id=point.id,
        type=type,
        texte=texte,
        photo=photo_bytes,
        urgence=urgence,
        score_urgence=score,
        statut="ouvert",
    )
    db.add(sig)

    nouvel_etat = ETAT_PAR_TYPE.get(type)
    if nouvel_etat:
        point.etat = nouvel_etat
    point.maj_le = datetime.now(timezone.utc)

    db.commit()
    db.refresh(sig)
    return sig


@router.get("/{signalement_id}/photo")
def get_photo(signalement_id: int, db: Session = Depends(get_db)):
    sig = db.get(Signalement, signalement_id)
    if sig is None or not sig.photo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo introuvable")
    return Response(
        content=sig.photo,
        media_type=_image_type(sig.photo) or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------- Admin (JWT) ----------

class SignalementAdminOut(SignalementOut):
    point_nom: str
    quartier: str
    a_photo: bool


class SignalementPatch(BaseModel):
    statut: Literal["repare"]


# Higher rank first; unknown/NULL urgence last.
_URGENCE_RANG = case(
    (Signalement.urgence == "haute", 3),
    (Signalement.urgence == "moyenne", 2),
    (Signalement.urgence == "basse", 1),
    else_=0,
)


def _admin_out(sig: Signalement, point: PointEau, a_photo: bool) -> SignalementAdminOut:
    return SignalementAdminOut(
        **SignalementOut.model_validate(sig).model_dump(),
        point_nom=point.nom,
        quartier=point.quartier,
        a_photo=a_photo,
    )


@router.get("", response_model=list[SignalementAdminOut])
def list_signalements(
    statut: StatutSignalement | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_admin),
):
    """Urgence haute → basse, puis du plus ancien au plus récent (le plus long en attente d'abord)."""
    stmt = (
        select(Signalement, PointEau, Signalement.photo.is_not(None).label("a_photo"))
        .join(PointEau, PointEau.id == Signalement.point_id)
        .order_by(_URGENCE_RANG.desc(), Signalement.score_urgence.desc(), Signalement.cree_le.asc(), Signalement.id.asc())
    )
    if statut:
        stmt = stmt.where(Signalement.statut == statut)
    # Don't load the photo bytes for the list.
    stmt = stmt.options(defer(Signalement.photo))
    return [_admin_out(sig, point, a_photo) for sig, point, a_photo in db.execute(stmt).all()]


@router.patch("/{signalement_id}", response_model=SignalementAdminOut)
def update_signalement(
    signalement_id: int,
    body: SignalementPatch,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_admin),
):
    sig = db.get(Signalement, signalement_id)
    if sig is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signalement introuvable")
    point = db.get(PointEau, sig.point_id)
    now = datetime.now(timezone.utc)

    if sig.statut != "repare":  # idempotent: keep the first repair date
        sig.statut = "repare"
        sig.repare_le = now
        db.flush()
        encore_ouverts = db.scalar(
            select(func.count()).select_from(Signalement)
            .where(Signalement.point_id == point.id, Signalement.statut == "ouvert")
        )
        if encore_ouverts == 0:
            point.etat = "ok"
            point.maj_le = now
        db.commit()

    a_photo = db.scalar(select(Signalement.photo.is_not(None)).where(Signalement.id == sig.id))
    db.refresh(sig)
    db.refresh(point)
    return _admin_out(sig, point, bool(a_photo))
