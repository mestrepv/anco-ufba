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
            projeto=proj, titulo=f"Art {i}", identificador=f"doi:10.1/{i}",
            artigo=art, resumo=f"resumo do artigo {i}",
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
        ItemCorpus.objects.create(
            projeto=proj, titulo=art.titulo, identificador=f"l:{i}", artigo=art, resumo="r"
        )
        legados.append(art.pk)
    for i in range(4):
        art = Artigo.objects.create(titulo=f"Novo {i}", ano=2021, eh_legado=False)
        ItemCorpus.objects.create(
            projeto=proj, titulo=art.titulo, identificador=f"n:{i}", artigo=art, resumo="r"
        )
        novos.append(art.pk)

    res = executar_sorteio(proj, cota=10, semente=7)
    atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio=res.sorteio).values_list("artigo_id", flat=True)
    )
    assert atribuidos == set(novos)  # só os novos
    assert not (atribuidos & set(legados))  # nenhum do acervo


def test_categoria_tipo():
    from apps.anco.sorteio import categoria_tipo

    assert categoria_tipo("Artigo") == "artigo"
    assert categoria_tipo("Journal Article") == "artigo"
    assert categoria_tipo("journalArticle") == "artigo"
    assert categoria_tipo("Periodico") == "artigo"
    assert categoria_tipo("Tese") == "tese"
    assert categoria_tipo("Doctoralthesis") == "tese"
    assert categoria_tipo("Livro") == "livro"
    assert categoria_tipo("Capítulo") == "capitulo"
    assert categoria_tipo("bookSection") == "capitulo"
    assert categoria_tipo("") == "outro"
    assert categoria_tipo("qualquer coisa") == "outro"


def test_pool_filtra_por_tipo():
    from apps.anco.sorteio import _pool

    proj = ProjetoANCO.objects.create(nome="Filtros")
    def _item(titulo, tipo):
        art = Artigo.objects.create(titulo=titulo, ano=2021)
        ItemCorpus.objects.create(
            projeto=proj, titulo=titulo, identificador=f"id:{titulo}",
            artigo=art, resumo="r", tipo=tipo,
        )
    _item("Um artigo", "Artigo")
    _item("Uma tese", "Tese")
    _item("Um livro", "Livro")

    assert len(_pool(proj, set(), 1)) == 3  # tipos=None = todos
    assert len(_pool(proj, set(), 1, tipos=["artigo"])) == 1
    assert len(_pool(proj, set(), 1, tipos=["artigo", "tese"])) == 2
    assert len(_pool(proj, set(), 1, tipos=[])) == 0  # lista vazia = nenhum


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


def test_exclui_itens_sem_resumo():
    """A análise AnCo exige resumo: itens sem resumo ficam fora do sorteio."""
    from apps.anco.sorteio import itens_elegiveis

    proj = ProjetoANCO.objects.create(nome="Sem resumo")
    com = Artigo.objects.create(titulo="Com resumo", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo=com.titulo, identificador="c:1", artigo=com, resumo="tem")
    sem = Artigo.objects.create(titulo="Sem resumo", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo=sem.titulo, identificador="s:1", artigo=sem, resumo="")
    branco = Artigo.objects.create(titulo="Só espaços", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo=branco.titulo, identificador="b:1", artigo=branco, resumo="   ")

    ids = {it.artigo_id for it in itens_elegiveis(proj)}
    assert ids == {com.pk}  # só o que tem resumo
    # desligando a exigência, entram os 3
    assert len(itens_elegiveis(proj, exigir_resumo=False)) == 3


def test_itens_elegiveis_filtra_por_tipo():
    """Filtro por tipo: seleção explícita restringe; None = todos; [] = nenhum."""
    from apps.anco.sorteio import itens_elegiveis

    proj = ProjetoANCO.objects.create(nome="Tipos")
    art = Artigo.objects.create(titulo="Artigo", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo="Artigo", identificador="t:1", artigo=art, resumo="r", tipo="Artigo")
    tese = Artigo.objects.create(titulo="Tese", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo="Tese", identificador="t:2", artigo=tese, resumo="r", tipo="Tese")
    livro = Artigo.objects.create(titulo="Livro", ano=2021)
    ItemCorpus.objects.create(projeto=proj, titulo="Livro", identificador="t:3", artigo=livro, resumo="r", tipo="Livro")

    todos = {it.artigo_id for it in itens_elegiveis(proj)}
    assert todos == {art.pk, tese.pk, livro.pk}  # None = todos
    art_tese = {it.artigo_id for it in itens_elegiveis(proj, tipos=["artigo", "tese"])}
    assert art_tese == {art.pk, tese.pk}  # artigos e teses (livro fora)
    assert len(itens_elegiveis(proj, tipos=[])) == 0  # nenhum tipo marcado
