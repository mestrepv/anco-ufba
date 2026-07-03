"""Loop de "Artigo individual" no ANCO: lista de sessão (progresso), estados de
sucesso/falha e o fim do dead-end quando o artigo já existe.

Cobre o ajuste que faz cada adição empilhar um resultado visível na sessão e
voltar ao formulário (PRG), em vez de despejar o analista na lista do corpus.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.acervo.views import _SESSAO_ADD
from apps.anco.models import ItemCorpus, MembroANCO, ProjetoANCO
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def analista(db):
    return User.objects.create_user(
        username="ana",
        email="ana@u.edu",
        password="x",
        papel=User.Papel.ANALISTA,
        pode_anco=True,
    )


@pytest.fixture
def projeto(db, analista):
    p = ProjetoANCO.objects.create(nome="Piloto", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=analista, papel=MembroANCO.Papel.ANALISTA)
    return p


@pytest.fixture
def base(db):
    vocab, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    termo, _ = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab, nome="Web of Science", defaults={"ativo": True}
    )
    return termo


def _url(projeto):
    return f"{reverse('cadastrar_artigo')}?projeto={projeto.slug}"


def _sessao(client, slug):
    return (client.session.get(_SESSAO_ADD) or {}).get(slug, [])


def _payload_valido(base, **overrides):
    dados = {
        "titulo": "Cognição e aprendizagem",
        "ano": "2024",
        "link_acesso": "https://example.org/artigo",
        "base_consulta": str(base.pk),
        "tipo_publicacao": "artigo",
        "area": "Psicologia",
        "resumo": "Resumo de teste.",
        "autores": "Fulano; Beltrano",
        "palavras_chaves": "cognição; teste",
    }
    dados.update(overrides)
    return dados


# --------------------------------------------------------------------------- #
# Sucesso + progresso (lista de sessão)
# --------------------------------------------------------------------------- #


def test_adicionar_existente_registra_novo_na_sessao(client, analista, projeto):
    """Artigo que já existe no sistema + contexto de projeto entra no corpus
    (fim do dead-end) e vira uma linha 'novo' na lista da sessão."""
    art = Artigo.objects.create(titulo="Existente", ano=2023, doi="10.1/exist", eh_legado=False)
    client.force_login(analista)

    resp = client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})

    assert resp.status_code == 302
    assert reverse("cadastrar_artigo") in resp["Location"]
    assert f"projeto={projeto.slug}" in resp["Location"]
    assert projeto.itens.filter(removido=False).count() == 1
    sessao = _sessao(client, projeto.slug)
    assert len(sessao) == 1
    assert sessao[0]["status"] == "novo"
    assert sessao[0]["doi"] == art.doi
    # item_id preenchido → a linha da sessão é clicável/editável
    assert sessao[0]["item_id"] == projeto.itens.get().pk


def test_adicionar_repetido_marca_status_repetido(client, analista, projeto):
    art = Artigo.objects.create(titulo="Repetido", ano=2023, doi="10.1/rep", eh_legado=False)
    client.force_login(analista)

    client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})
    client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})

    assert projeto.itens.filter(removido=False).count() == 1  # idempotente
    sessao = _sessao(client, projeto.slug)
    assert len(sessao) == 2
    assert sessao[0]["status"] == "repetido"  # 2º (topo) já estava no corpus
    assert sessao[1]["status"] == "novo"


def test_adicionar_legado_fica_isento(client, analista, projeto):
    art = Artigo.objects.create(titulo="Curado", ano=2010, doi="10.1/leg", eh_legado=True)
    client.force_login(analista)

    client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})

    assert projeto.itens.count() == 0  # legado isento, não entra no corpus
    sessao = _sessao(client, projeto.slug)
    assert len(sessao) == 1
    assert sessao[0]["status"] == "legado"


def test_novo_via_formulario_completo(client, analista, projeto, base):
    """Caminho do formulário (artigo inédito): cria Artigo + ItemCorpus e registra
    'novo' na sessão."""
    client.force_login(analista)

    resp = client.post(
        _url(projeto), _payload_valido(base, projeto=projeto.slug, doi="10.1/inedito")
    )

    assert resp.status_code == 302
    assert Artigo.objects.filter(doi="10.1/inedito").exists()
    assert projeto.itens.filter(removido=False).count() == 1
    sessao = _sessao(client, projeto.slug)
    assert len(sessao) == 1 and sessao[0]["status"] == "novo"


# --------------------------------------------------------------------------- #
# Falha
# --------------------------------------------------------------------------- #


def test_link_falho_nao_impede_salvar(client, analista, projeto, base, monkeypatch):
    """Se a verificação do link explode, o artigo ainda é salvo e a linha da
    sessão sinaliza link_falhou."""

    def _boom(_url):
        raise RuntimeError("timeout")

    monkeypatch.setattr("apps.acervo.views.validar_link", _boom)
    client.force_login(analista)

    resp = client.post(
        _url(projeto), _payload_valido(base, projeto=projeto.slug, doi="10.1/linkruim")
    )

    assert resp.status_code == 302
    assert Artigo.objects.filter(doi="10.1/linkruim").exists()  # salvou mesmo assim
    assert projeto.itens.filter(removido=False).count() == 1
    sessao = _sessao(client, projeto.slug)
    assert sessao[0]["link_falhou"] is True


def test_form_invalido_nao_cria_item(client, analista, projeto):
    """POST sem link/base/área: re-render 200 com aviso de falha, nada é criado."""
    client.force_login(analista)

    resp = client.post(_url(projeto), {"projeto": projeto.slug, "titulo": "Só título"})

    assert resp.status_code == 200
    assert projeto.itens.count() == 0
    assert _sessao(client, projeto.slug) == []
    assert "Não salvei" in resp.content.decode()


# --------------------------------------------------------------------------- #
# Concluir / progresso visível
# --------------------------------------------------------------------------- #


def test_get_mostra_painel_de_sessao(client, analista, projeto):
    art = Artigo.objects.create(titulo="Visível", ano=2023, doi="10.1/vis", eh_legado=False)
    client.force_login(analista)
    client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})

    resp = client.get(_url(projeto))

    assert resp.status_code == 200
    corpo = resp.content.decode()
    assert "Adicionados nesta sessão" in corpo
    # o título vira link para a edição do item no corpus
    item = projeto.itens.get()
    assert reverse("anco_corpus_editar", args=[projeto.slug, item.pk]) in corpo


def test_entrada_antiga_sem_item_id_fica_clicavel(client, analista, projeto):
    """Registro de sessão gravado antes do item_id: resolvido pelo DOI no render."""
    from apps.anco.models import ItemCorpus

    art = Artigo.objects.create(titulo="Antigo", ano=2020, doi="10.9/old")
    item = ItemCorpus.objects.create(
        projeto=projeto, identificador="k-old", doi="10.9/old", titulo="Antigo", artigo=art
    )
    client.force_login(analista)
    sess = client.session
    sess[_SESSAO_ADD] = {
        projeto.slug: [
            {"titulo": "Antigo", "doi": "10.9/old", "ano": 2020, "status": "novo"}
        ]
    }
    sess.save()

    resp = client.get(_url(projeto))

    assert reverse("anco_corpus_editar", args=[projeto.slug, item.pk]) in resp.content.decode()


def test_item_removido_do_corpus_aparece_marcado(client, analista, projeto):
    """Item que saiu do corpus (ex.: fonte excluída) não vira link morto: aparece
    riscado com 'removido do corpus'."""
    from apps.anco.models import ItemCorpus

    art = Artigo.objects.create(titulo="Sumido", ano=2021, doi="10.9/gone")
    ItemCorpus.objects.create(
        projeto=projeto,
        identificador="k-gone",
        doi="10.9/gone",
        titulo="Sumido",
        artigo=art,
        removido=True,
    )
    client.force_login(analista)
    sess = client.session
    sess[_SESSAO_ADD] = {
        projeto.slug: [{"titulo": "Sumido", "doi": "10.9/gone", "ano": 2021, "status": "novo"}]
    }
    sess.save()

    corpo = client.get(_url(projeto)).content.decode()

    assert "removido do corpus" in corpo
    assert "line-through" in corpo  # título riscado, sem link de edição


def test_remover_da_sessao_volta_para_tela_e_marca(client, analista, projeto):
    """Botão 'remover' no painel de sessão exclui do corpus e volta à mesma tela;
    o item passa a aparecer como 'removido do corpus'."""
    art = Artigo.objects.create(titulo="ParaRemover", ano=2022, doi="10.9/rm")
    client.force_login(analista)
    client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})
    item = projeto.itens.get()

    resp = client.post(
        reverse("anco_corpus_excluir", args=[projeto.slug]),
        {"item_id": item.pk, "next": _url(projeto)},
    )

    assert resp.status_code == 302
    assert resp["Location"] == _url(projeto)  # voltou à tela de adição, não ao corpus
    item.refresh_from_db()
    assert item.removido is True
    corpo = client.get(_url(projeto)).content.decode()
    assert "removido do corpus" in corpo


def test_concluir_limpa_sessao_e_vai_ao_corpus(client, analista, projeto):
    art = Artigo.objects.create(titulo="Fim", ano=2023, doi="10.1/fim", eh_legado=False)
    client.force_login(analista)
    client.post(_url(projeto), {"projeto": projeto.slug, "doi": art.doi})
    assert len(_sessao(client, projeto.slug)) == 1

    resp = client.get(f"{reverse('cadastrar_artigo')}?projeto={projeto.slug}&concluir=1")

    assert resp.status_code == 302
    assert reverse("anco_corpus", args=[projeto.slug]) in resp["Location"]
    assert _sessao(client, projeto.slug) == []
