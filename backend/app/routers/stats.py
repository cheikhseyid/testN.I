"""Aggregates for the dashboard (GET /stats) and public alerts (GET /alertes).

Every figure is computed in SQL (GROUP BY / aggregate functions); Python only shapes the JSON.
date_trunc / extract(epoch) are PostgreSQL functions.
"""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Date, Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PointEau, Signalement

router = APIRouter(tags=["stats"])

SEUIL_ALERTE = 3  # points en panne dans un même quartier


class ParQuartier(BaseModel):
    quartier: str
    signalements: int
    pannes: int


class ParSemaine(BaseModel):
    semaine: date  # lundi de la semaine (ISO)
    signalements: int
    pannes: int


class ParType(BaseModel):
    type: str
    signalements: int


class Stats(BaseModel):
    par_quartier: list[ParQuartier]
    par_semaine: list[ParSemaine]
    par_type: list[ParType]
    temps_moyen_reparation_h: float | None
    signalements_ouverts: int


class Alerte(BaseModel):
    quartier: str
    nb: int


_nb = func.count(Signalement.id)
_nb_pannes = func.count(case((Signalement.type == "panne", 1)))


@router.get("/stats", response_model=Stats)
def stats(db: Session = Depends(get_db)):
    par_quartier = db.execute(
        select(PointEau.quartier, _nb.label("signalements"), _nb_pannes.label("pannes"))
        .join(Signalement, Signalement.point_id == PointEau.id)
        .group_by(PointEau.quartier)
        .order_by(_nb_pannes.desc(), _nb.desc(), PointEau.quartier)
    ).mappings().all()

    semaine = cast(func.date_trunc("week", Signalement.cree_le), Date)
    par_semaine = db.execute(
        select(semaine.label("semaine"), _nb.label("signalements"), _nb_pannes.label("pannes"))
        .group_by(semaine)
        .order_by(semaine)
    ).mappings().all()

    par_type = db.execute(
        select(Signalement.type, _nb.label("signalements"))
        .group_by(Signalement.type)
        .order_by(_nb.desc())
    ).mappings().all()

    moyenne_h = db.scalar(
        select(func.round(
            cast(func.avg(func.extract("epoch", Signalement.repare_le - Signalement.cree_le)) / 3600, Numeric), 1
        )).where(Signalement.repare_le.is_not(None))
    )

    ouverts = db.scalar(select(func.count()).select_from(Signalement).where(Signalement.statut == "ouvert"))

    return Stats(
        par_quartier=par_quartier,
        par_semaine=par_semaine,
        par_type=par_type,
        temps_moyen_reparation_h=float(moyenne_h) if moyenne_h is not None else None,
        signalements_ouverts=ouverts,
    )


@router.get("/alertes", response_model=list[Alerte])
def alertes(db: Session = Depends(get_db)):
    """Public: neighbourhoods with at least SEUIL_ALERTE water points currently out of order."""
    nb = func.count(PointEau.id)
    return db.execute(
        select(PointEau.quartier, nb.label("nb"))
        .where(PointEau.etat == "panne")
        .group_by(PointEau.quartier)
        .having(nb >= SEUIL_ALERTE)
        .order_by(nb.desc(), PointEau.quartier)
    ).mappings().all()
