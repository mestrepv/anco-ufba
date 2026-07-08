"""Comando sortear_analistas: sorteio complementar restrito a um subconjunto."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from apps.acervo.models import Artigo
from apps.anco.models import AtribuicaoANCO, ItemCorpus, MembroANCO, ProjetoANCO
from apps.anco.sorteio import executar_sorteio

User = get_user_model()
pytestmark = pytest.mark.django_db


def _projeto(n_itens: int, n_analistas: int) -> ProjetoANCO:
    proj = ProjetoANCO.objects.create(nome="P", slug="p")
    for i in range(n_analistas):
        u = User.objects.create_user(username=f"a{i}", email=f"a{i}@u.edu", password="x")
        MembroANCO.objects.create(projeto=proj, usuario=u, papel=MembroANCO.Papel.ANALISTA)
    for i in range(n_itens):
        art = Artigo.objects.create(titulo=f"Art {i}", ano=2020)
        ItemCorpus.objects.create(
            projeto=proj, titulo=f"Art {i}", identificador=f"doi:10.1/{i}",
            artigo=art, resumo=f"resumo do artigo {i}",
        )
    return proj


def _chamar(*args) -> str:
    out = StringIO()
    call_command("sortear_analistas", *args, stdout=out)
    return out.getvalue()


def test_sorteia_so_para_quem_nao_tem_atribuicao():
    proj = _projeto(30, 3)
    veterana = User.objects.get(email="a0@u.edu")
    executar_sorteio(proj, analistas=[veterana], cota=5, semente=1)
    antes_veterana = set(
        AtribuicaoANCO.objects.filter(analista=veterana).values_list("artigo_id", flat=True)
    )

    saida = _chamar("--projeto", "p", "--sem-atribuicao", "--cota", "5")

    assert "10 atribuição(ões) para 2 analista(s)" in saida
    # Veterana não ganhou artigos novos; novatas ganharam 5 cada.
    assert AtribuicaoANCO.objects.filter(analista=veterana).count() == len(antes_veterana)
    for email in ("a1@u.edu", "a2@u.edu"):
        assert AtribuicaoANCO.objects.filter(analista__email=email).count() == 5
    # Artigos únicos: nenhum artigo em mais de uma atribuição (modo única).
    ids = list(AtribuicaoANCO.objects.values_list("artigo_id", flat=True))
    assert len(ids) == len(set(ids))


def test_dry_run_nao_grava():
    proj = _projeto(10, 2)
    assert proj  # fixture
    saida = _chamar("--projeto", "p", "--sem-atribuicao", "--dry-run")
    assert "DRY-RUN" in saida
    assert AtribuicaoANCO.objects.count() == 0


def test_emails_fora_do_projeto_falham():
    _projeto(10, 1)
    with pytest.raises(CommandError, match="Não são analistas deste projeto"):
        _chamar("--projeto", "p", "--emails", "intrusa@x.br")


# --------------------------------------------------------------------------- #
# Sorteio complementar pela tela de sorteio (POST acao=sorteio_complementar)
# --------------------------------------------------------------------------- #

from django.urls import reverse  # noqa: E402


def _curador(proj):
    u = User.objects.create_user(
        username="cur", email="cur@u.edu", password="x", is_staff=True, pode_anco=True
    )
    MembroANCO.objects.create(projeto=proj, usuario=u, papel=MembroANCO.Papel.CURADOR)
    return u


def test_view_sorteio_complementar_so_para_novos(client):
    proj = _projeto(30, 3)
    curador = _curador(proj)
    veterana = User.objects.get(email="a0@u.edu")
    executar_sorteio(proj, analistas=[veterana], cota=5, semente=1)

    client.force_login(curador)
    resp = client.post(
        reverse("anco_sorteio", args=[proj.slug]),
        {"acao": "sorteio_complementar", "cota": "5"},
    )
    assert resp.status_code == 302
    assert AtribuicaoANCO.objects.filter(analista=veterana).count() == 5  # intocada
    for email in ("a1@u.edu", "a2@u.edu"):
        assert AtribuicaoANCO.objects.filter(analista__email=email).count() == 5
    ids = list(AtribuicaoANCO.objects.values_list("artigo_id", flat=True))
    assert len(ids) == len(set(ids))  # nenhum artigo repetido entre sorteios


def test_view_sorteio_complementar_exige_curador(client):
    proj = _projeto(10, 2)
    analista = User.objects.get(email="a0@u.edu")
    analista.pode_anco = True
    analista.save()
    client.force_login(analista)
    resp = client.post(
        reverse("anco_sorteio", args=[proj.slug]),
        {"acao": "sorteio_complementar"},
    )
    assert resp.status_code in (302, 403)  # bloqueado pelo gate de curador
    assert AtribuicaoANCO.objects.count() == 0


def test_painel_avisa_curador_sobre_novos(client):
    proj = _projeto(30, 2)
    curador = _curador(proj)
    veterana = User.objects.get(email="a0@u.edu")
    executar_sorteio(proj, analistas=[veterana], cota=5, semente=3)

    client.force_login(curador)
    corpo = client.get(reverse("anco_painel", args=[proj.slug])).content.decode()
    assert "sem artigos" in corpo and "sortear agora" in corpo
