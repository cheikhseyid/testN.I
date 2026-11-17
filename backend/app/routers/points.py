from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PointEau
from ..schemas import EtatPoint, PointEauOut, TypePoint

router = APIRouter(prefix="/points", tags=["points"])


class PointEauLight(BaseModel):
    """Payload léger pour la liste / la carte."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    type: TypePoint
    quartier: str
    lat: float
    lon: float
    etat: EtatPoint


@router.get("", response_model=list[PointEauLight])
def list_points(
    quartier: str | None = Query(None, description="Filtre exact, insensible à la casse"),
    db: Session = Depends(get_db),
):
    stmt = select(
        PointEau.id, PointEau.nom, PointEau.type, PointEau.quartier,
        PointEau.lat, PointEau.lon, PointEau.etat,
    ).order_by(PointEau.id)
    if quartier and quartier.strip():
        stmt = stmt.where(func.lower(PointEau.quartier) == quartier.strip().lower())
    return db.execute(stmt).mappings().all()


@router.get("/{point_id}", response_model=PointEauOut)
def get_point(point_id: int, db: Session = Depends(get_db)):
    point = db.get(PointEau, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="Point d'eau introuvable")
    return point
