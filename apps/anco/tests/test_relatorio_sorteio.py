"""Relatório do sorteio: por analista, artigos com título/autor/base/DOI/URL."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.anco import estatisticas as stats
from apps.anco.models import (
    AtribuicaoANCO,
    FonteImport,
    ItemCorpus,
    MembroANCO,
    ProjetoANCO,
    SorteioANCO,
)
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="c", email="c@u.edu", password="x", pode_anco=True, is_staff=True
    )


@pytest.fixture
def analista(db):
    return User.objects.create_user(username="a", email="ana@u.edu", password="x", pode_anco=True)


@pytest.fixture
def projeto(db, curador, analista):
    p = ProjetoANCO.objects.create(nome="Piloto", slug="piloto-x", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=curador, papel=MembroANCO.Papel.CURADOR)
    MembroANCO.objects.create(projeto=p, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    return p


@pytest.fixture
def base_scopus(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


def _item(projeto, titulo, ident, fonte, **kw):
    art = Artigo.objects.create(titulo=titulo, ano=2023, doi=kw.get("doi") or None)
    it = ItemCorpus.objects.create(
        projeto=projeto,
        titulo=titulo,
        identificador=ident,
        artigo=art,
        autores=kw.get("autores", ""),
        doi=kw.get("doi", ""),
        link=kw.get("link", ""),
    )
    it.origem_fontes.add(fonte)
    return it


def test_relatorio_agrupa_por_analista_com_campos(projeto, analista, base_scopus):
    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    it = _item(
        projeto,
        "Cognição em equipes",
        "k1",
        fonte,
        autores="Silva, A.; Souza, B.",
        doi="10.1016/j.x.2023",
        link="https://example.org/artigo",
    )
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)

    rel = stats.relatorio_sorteio(projeto, s)
    assert len(rel) == 1
    bloco = rel[0]
    assert bloco["nome"] == analista.email  # sem nome_exibicao → email
    assert bloco["n"] == 1
    art = bloco["artigos"][0]
    assert art["titulo"] == "Cognição em equipes"
    assert art["autores"] == "Silva, A.; Souza, B."
    assert art["base"] == "Scopus"
    assert art["doi"] == "10.1016/j.x.2023"
    assert art["doi_url"] == "https://doi.org/10.1016/j.x.2023"
    assert art["url"] == "https://example.org/artigo"
    # Acesso prioriza a URL própria, não o DOI.
    assert art["acesso_url"] == "https://example.org/artigo"
    assert art["acesso_host"] == "example.org"
    assert art["acesso_via_doi"] is False


def test_acesso_cai_para_doi_quando_sem_url(projeto, analista, base_scopus):
    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    it = _item(projeto, "Só DOI", "k9", fonte, doi="10.1/só")  # sem link
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)
    art = stats.relatorio_sorteio(projeto, s)[0]["artigos"][0]
    assert art["acesso_url"] == "https://doi.org/10.1/só"
    assert art["acesso_via_doi"] is True


def test_progresso_e_situacao_por_artigo(projeto, analista, base_scopus):
    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    feito = _item(projeto, "Publicado", "k1", fonte)
    andamento = _item(projeto, "Rascunho", "k2", fonte)
    _item(projeto, "Nem começou", "k3", fonte)  # 3º sorteado, sem análise
    s = SorteioANCO.objects.create(projeto=projeto)
    for it in (feito, andamento):
        AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)
    AtribuicaoANCO.objects.create(
        sorteio=s, analista=analista, artigo=ItemCorpus.objects.get(identificador="k3").artigo
    )
    from apps.acervo.models import Analise

    Analise.objects.create(artigo=feito.artigo, analista=analista, status=Analise.Status.PUBLICADA)
    Analise.objects.create(
        artigo=andamento.artigo, analista=analista, status=Analise.Status.RASCUNHO
    )

    g = stats.relatorio_sorteio(projeto, s)[0]
    assert g["progresso"] == {
        "total": 3,
        "concluidas": 1,
        "andamento": 1,
        "a_fazer": 1,
        "pct": 33,
        "estado": "andamento",
    }
    # "A fazer" vem primeiro; situação de cada artigo classificada.
    estados = [a["estado"] for a in g["artigos"]]
    assert estados[0] == "nada"  # ordenado: o que falta primeiro
    por_titulo = {a["titulo"]: a["estado"] for a in g["artigos"]}
    assert por_titulo["Publicado"] == "publicada"
    assert por_titulo["Rascunho"] == "andamento"
    assert por_titulo["Nem começou"] == "nada"


def test_doi_url_nao_duplica_prefixo(projeto, analista, base_scopus):
    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    it = _item(projeto, "Já é URL", "k2", fonte, doi="https://doi.org/10.5/y")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)
    rel = stats.relatorio_sorteio(projeto, s)
    assert rel[0]["artigos"][0]["doi_url"] == "https://doi.org/10.5/y"


def test_view_mostra_relatorio_e_excluir(client, projeto, curador, analista, base_scopus):
    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    it = _item(projeto, "Artigo XYZ", "k1", fonte, autores="Fulano", doi="10.1/z")
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)

    client.force_login(curador)
    resp = client.get(reverse("anco_sorteio", args=[projeto.slug]))
    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert "Progresso por analista" in corpo
    assert "Artigo XYZ" in corpo
    assert "Scopus" in corpo
    # Botão de desfazer (linha de histórico do sorteio unificado).
    assert 'name="acao" value="desfazer"' in corpo


def test_painel_botao_vira_sorteio_e_acompanhamento(client, projeto, curador, analista):
    art = Artigo.objects.create(titulo="T", ano=2023)
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=art)
    client.force_login(curador)
    resp = client.get(reverse("anco_painel", args=[projeto.slug]))
    assert b"Sorteio e acompanhamento" in resp.content
    assert b"Sortear an\xc3\xa1lise" not in resp.content


def test_enviada_mostra_revisar_e_decidir(client, projeto, curador, analista, base_scopus):
    from apps.acervo.models import Analise

    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    it = _item(projeto, "Enviada para aprovar", "k1", fonte)
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)
    analise = Analise.objects.create(
        artigo=it.artigo, analista=analista, status=Analise.Status.SUBMETIDA
    )

    client.force_login(curador)
    # A decisão saiu da lista: linha "Enviada" leva à visualização (Revisar e decidir).
    resp = client.get(reverse("anco_sorteio", args=[projeto.slug]))
    corpo = resp.content.decode()
    assert "Revisar e decidir" in corpo
    assert reverse("ver_analise_analista", args=[it.artigo_id, analista.pk]) in corpo
    # Não há mais formulário de aprovar/devolver embutido na lista.
    assert reverse("aprovar_analise", args=[analise.pk]) not in corpo


def test_devolver_analise_inline_volta_ao_sorteio(client, projeto, curador, analista, base_scopus):
    from apps.acervo.models import Analise

    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    it = _item(projeto, "Para devolver", "k1", fonte)
    s = SorteioANCO.objects.create(projeto=projeto)
    AtribuicaoANCO.objects.create(sorteio=s, analista=analista, artigo=it.artigo)
    analise = Analise.objects.create(
        artigo=it.artigo, analista=analista, status=Analise.Status.SUBMETIDA
    )

    client.force_login(curador)
    destino = reverse("anco_sorteio", args=[projeto.slug])
    resp = client.post(
        reverse("devolver_analise", args=[analise.pk]),
        {"next": destino, "acao": "ajustes", "motivo": "Falta a metodologia."},
    )
    assert resp.status_code == 302
    assert resp["Location"] == destino
    analise.refresh_from_db()
    assert analise.status == Analise.Status.RASCUNHO
    assert analise.motivo_curadoria == "Falta a metodologia."


def test_relatorio_unificado_soma_todos_os_sorteios(projeto, analista, base_scopus):
    """Sem `sorteio`, o relatório agrega as atribuições de TODOS os sorteios:
    um bloco por analista, contagem única (tela de sorteio unificada)."""
    fonte = FonteImport.objects.create(projeto=projeto, base_consulta=base_scopus)
    outra = User.objects.create_user(username="n", email="nova@u.edu", password="x")
    MembroANCO.objects.create(projeto=projeto, usuario=outra, papel=MembroANCO.Papel.ANALISTA)

    s1 = SorteioANCO.objects.create(projeto=projeto)
    s2 = SorteioANCO.objects.create(projeto=projeto)  # complementar
    it1 = _item(projeto, "Artigo A", "u1", fonte)
    it2 = _item(projeto, "Artigo B", "u2", fonte)
    it3 = _item(projeto, "Artigo C", "u3", fonte)
    AtribuicaoANCO.objects.create(sorteio=s1, analista=analista, artigo=it1.artigo)
    AtribuicaoANCO.objects.create(sorteio=s1, analista=analista, artigo=it2.artigo)
    AtribuicaoANCO.objects.create(sorteio=s2, analista=outra, artigo=it3.artigo)

    rel = stats.relatorio_sorteio(projeto)  # unificado
    assert len(rel) == 2  # um bloco por analista, não por sorteio
    por_nome = {g["nome"]: g for g in rel}
    assert por_nome["ana@u.edu"]["n"] == 2
    assert por_nome["nova@u.edu"]["n"] == 1
    # Restrito a um sorteio continua funcionando (histórico).
    assert len(stats.relatorio_sorteio(projeto, s2)) == 1
