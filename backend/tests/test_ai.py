# Tests du score d'urgence
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai import score_urgence  # noqa: E402


def test_malades_plus_urgent_que_pompe_lente():
    grave, raison = score_urgence("eau_trouble", "eau trouble, enfants malades")
    leger, _ = score_urgence("faible_debit", "pompe lente")
    assert grave > leger
    assert "santé" in raison


def test_mots_cles_arabe():
    avec, raison = score_urgence("autre", "الماء عكر و بدون ماء أحيانا")
    sans, _ = score_urgence("autre", "")
    assert avec > sans
    assert "eau impropre" in raison and "sans eau" in raison


def test_darija():
    s, raison = score_urgence("panne", "ma kayn lma, drari mridin")
    assert "santé" in raison and "sans eau" in raison
    assert s >= 80


def test_signalements_ouverts_et_borne():
    seul, _ = score_urgence("panne", "", nb_ouverts=0, type_point="puits")
    groupe, raison = score_urgence("panne", "", nb_ouverts=3, type_point="borne")
    assert groupe == seul + 15 + 10
    assert "borne publique" in raison


def test_anciennete():
    neuf, _ = score_urgence("panne", anciennete_h=1)
    vieux, raison = score_urgence("panne", anciennete_h=100)
    assert vieux == neuf + 10
    assert "> 3 j" in raison


def test_bornes_0_100_et_texte_vide():
    s, _ = score_urgence("eau_trouble", "eau trouble sale, enfants malades, plus d'eau, fuite",
                         nb_ouverts=10, type_point="borne", anciennete_h=500)
    assert s == 100
    s, raison = score_urgence("autre", None)
    assert 0 <= s <= 100 and raison
