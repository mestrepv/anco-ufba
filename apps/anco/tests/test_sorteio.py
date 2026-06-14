"""Sorteio ANCO: distribuição por cota, idempotência e semente."""

import pytest
from django.contrib.auth import get_user_model

from apps.acervo.models import Artigo
from apps.anco.models import AtribuicaoANCO, ItemCorpus, MembroANCO, ProjetoANCO
from apps.anco.sorteio import executar_sorteio

User = get_user_model()
pytestmark = pytest.mark.django_db


def _projeto(n_itens: int, n_analistas: int) -> ProjetoANCO:
    proj = ProjetoANCO.objects.create(nome="P")
    for i in range(n_analistas):
        u = User.objects.create_user(username=f"a{i}", email=f"a{i}@u.edu", password="x")
        MembroANCO.objects.create(projeto=proj, usuario=u, papel=MembroANCO.Papel.ANALISTA)
    for i in range(n_itens):
        art = Artigo.objects.create(titulo=f"Art {i}", ano=2020)
        ItemCorpus.objects.create(
            projeto=proj, titulo=f"Art {i}", identificador=f"doi:10.1/{i}", artigo=art
        )
    return proj


def test_distribui_por_cota():
    proj = _projeto(10, 2)
    res = executar_sorteio(proj, cota=3, semente=42)
    assert res.sorteio is not None
    assert res.atribuidas == 6  # 2 analistas × cota 3
    assert res.sorteio.semente == 42


def test_idempotente_nao_realoca():
    proj = _projeto(10, 1)
    r1 = executar_sorteio(proj, cota=3, semente=1)
    r2 = executar_sorteio(proj, cota=3, semente=1)
    a1 = set(AtribuicaoANCO.objects.filter(sorteio=r1.sorteio).values_list("artigo_id", flat=True))
    a2 = set(AtribuicaoANCO.objects.filter(sorteio=r2.sorteio).values_list("artigo_id", flat=True))
    assert a1 and a2 and a1.isdisjoint(a2)  # não reatribui os já distribuídos


def test_sem_analistas():
    proj = _projeto(5, 0)
    res = executar_sorteio(proj, cota=3)
    assert res.sorteio is None and "analista" in res.motivo.lower()


def test_dupla_dois_assentos_por_artigo():
    proj = _projeto(3, 2)
    res = executar_sorteio(proj, cota=5, modo_revisao="dupla", semente=9)
    # 3 artigos × 2 assentos = 6 vagas, 2 analistas × cota 5 = capacidade 10
    assert res.atribuidas == 6
