from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TypePoint = Literal["puits", "borne", "citerne"]
EtatPoint = Literal["ok", "faible", "panne"]
TypeSignalement = Literal["panne", "eau_trouble", "faible_debit", "autre"]
StatutSignalement = Literal["ouvert", "repare"]


class Health(BaseModel):
    ok: bool


class PointEauBase(BaseModel):
    nom: str
    type: TypePoint
    quartier: str
    lat: float
    lon: float
    etat: EtatPoint = "ok"
    potable: bool = True


class PointEauCreate(PointEauBase):
    pass


class PointEauOut(PointEauBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    maj_le: datetime


class SignalementCreate(BaseModel):
    point_id: int
    type: TypeSignalement
    texte: str = Field(default="", max_length=500)


class SignalementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    point_id: int
    type: TypeSignalement
    texte: str
    urgence: str | None
    score_urgence: float
    statut: StatutSignalement
    cree_le: datetime
    repare_le: datetime | None


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
