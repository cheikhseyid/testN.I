from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, LargeBinary, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PointEau(Base):
    __tablename__ = "points_eau"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("puits", "borne", "citerne", name="type_point"), nullable=False
    )
    quartier: Mapped[str] = mapped_column(String(200), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    etat: Mapped[str] = mapped_column(
        Enum("ok", "faible", "panne", name="etat_point"), nullable=False, default="ok"
    )
    potable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    maj_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    signalements: Mapped[list["Signalement"]] = relationship(
        back_populates="point", cascade="all, delete-orphan"
    )


class Signalement(Base):
    __tablename__ = "signalements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    point_id: Mapped[int] = mapped_column(
        ForeignKey("points_eau.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        Enum("panne", "eau_trouble", "faible_debit", "autre", name="type_signalement"),
        nullable=False,
    )
    texte: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    urgence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score_urgence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    statut: Mapped[str] = mapped_column(
        Enum("ouvert", "repare", name="statut_signalement"), nullable=False, default="ouvert"
    )
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    repare_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    point: Mapped[PointEau] = relationship(back_populates="signalements")


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
