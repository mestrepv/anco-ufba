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


def test_sorteio_exclui_artigos_no_acervo():
    """Artigos já no acervo (eh_legado) não entram no sorteio — só os novos."""
    proj = ProjetoANCO.objects.create(nome="Misto")
    u = User.objects.create_user(username="an", email="an@u.edu", password="x")
    MembroANCO.objects.create(projeto=proj, usuario=u, papel=MembroANCO.Papel.ANALISTA)
    legados, novos = [], []
    for i in range(4):
        art = Artigo.objects.create(titulo=f"Leg {i}", ano=2019, eh_legado=True)
        ItemCorpus.objects.create(projeto=proj, titulo=art.titulo, identificador=f"l:{i}", artigo=art)
        legados.append(art.pk)
    for i in range(4):
        art = Artigo.objects.create(titulo=f"Novo {i}", ano=2021, eh_legado=False)
        ItemCorpus.objects.create(projeto=proj, titulo=art.titulo, identificador=f"n:{i}", artigo=art)
        novos.append(art.pk)

    res = executar_sorteio(proj, cota=10, semente=7)
    atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert atribuidos == set(novos)  # só os novos
    assert not (atribuidos & set(legados))  # nenhum do acervo


def test_pool_filtra_por_termo_e_campos():
    from apps.anco.sorteio import _pool

    proj = ProjetoANCO.objects.create(nome="Filtros")
    def _item(titulo, resumo="", palavras=""):
        art = Artigo.objects.create(titulo=titulo, ano=2021)
        ItemCorpus.objects.create(
            projeto=proj, titulo=titulo, identificador=f"id:{titulo}",
            artigo=art, resumo=resumo, palavras_chaves=palavras,
        )
    _item("Cognição em jogos", resumo="trata de análise cognitiva")
    _item("Outro tema", resumo="sem o termo", palavras="cognitiva")
    _item("Mais um", resumo="nada aqui")

    assert len(_pool(proj, set(), 1)) == 3  # sem termo = todos
    # termo "cognitiva" em todos os campos (campos vazio): resumo OU palavras → 2
    assert len(_pool(proj, set(), 1, termo="cognitiva")) == 2
    # só no resumo: casa 1 ("Cognição em jogos")
    assert len(_pool(proj, set(), 1, termo="cognitiva", campos=["resumo"])) == 1
    # só nas palavras-chave: casa 1 ("Outro tema")
    assert len(_pool(proj, set(), 1, termo="cognitiva", campos=["palavras_chave"])) == 1
    # resumo OU palavras-chave: casa 2
    assert len(_pool(proj, set(), 1, termo="cognitiva", campos=["resumo", "palavras_chave"])) == 2
    # só no título: 0 ("cognitiva" != "cognição")
    assert len(_pool(proj, set(), 1, termo="cognitiva", campos=["titulo"])) == 0


def test_itens_elegiveis_e_pool_coincidem():
    """O preview (itens_elegiveis) e o pool do sorteio são o MESMO conjunto."""
    from apps.anco.sorteio import _pool, itens_elegiveis

    proj = _projeto(6, 1)
    # marca 2 como legado (acervo) — não entram
    from apps.anco.models import ItemCorpus
    for it in ItemCorpus.objects.filter(projeto=proj)[:2]:
        it.artigo.eh_legado = True
        it.artigo.save(update_fields=["eh_legado"])
    eleg = {it.artigo_id for it in itens_elegiveis(proj)}
    pool = {p.artigo_id for p in _pool(proj, set(), 1)}
    assert eleg == pool
    assert len(eleg) == 4  # 6 - 2 legado


def test_itens_elegiveis_exclui_ja_atribuidos():
    from apps.anco.sorteio import executar_sorteio, itens_elegiveis

    proj = _projeto(5, 1)
    antes = len(itens_elegiveis(proj))
    executar_sorteio(proj, cota=2, semente=1)  # atribui 2
    depois = len(itens_elegiveis(proj))
    assert antes == 5
    assert depois == 3  # os 2 atribuídos saem do pool elegível


def test_termo_sinonimo_pt_en_mesmos_resultados():
    """Digitar 'análise cognitiva' ou 'cognitive analysis' casa o MESMO conjunto."""
    from apps.anco.sorteio import itens_elegiveis

    proj = ProjetoANCO.objects.create(nome="Sinônimos")
    a1 = Artigo.objects.create(titulo="Estudo de análise cognitiva", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo=a1.titulo, identificador="s:1", artigo=a1)
    a2 = Artigo.objects.create(titulo="A cognitive analysis of games", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo=a2.titulo, identificador="s:2", artigo=a2)
    a3 = Artigo.objects.create(titulo="Tema sem relação", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo=a3.titulo, identificador="s:3", artigo=a3)

    pt = {it.artigo_id for it in itens_elegiveis(proj, termo="análise cognitiva")}
    en = {it.artigo_id for it in itens_elegiveis(proj, termo="cognitive analysis")}
    assert pt == en == {a1.pk, a2.pk}  # os dois casam; o "sem relação" fica fora
