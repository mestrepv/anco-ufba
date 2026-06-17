"""Smoke das telas ANCO (rotas montadas via ANCO_ATIVO=True em dev/test)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.acervo.models import Artigo
from apps.anco.models import ItemCorpus, MembroANCO, ProjetoANCO

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def curador(db):
    return User.objects.create_user(
        username="cur", email="cur@u.edu", password="x", pode_anco=True
    )


@pytest.fixture
def projeto(db, curador):
    p = ProjetoANCO.objects.create(nome="Piloto ANCO", pergunta_pesquisa="Q?")
    MembroANCO.objects.create(projeto=p, usuario=curador, papel=MembroANCO.Papel.CURADOR)
    art = Artigo.objects.create(titulo="Artigo X", ano=2021)
    ItemCorpus.objects.create(projeto=p, titulo="Artigo X", identificador="doi:10.1/x", artigo=art)
    return p


@pytest.mark.parametrize(
    "nome",
    ["anco_painel", "anco_importar", "anco_corpus", "anco_sorteio", "anco_estatisticas", "anco_equipe"],
)
def test_telas_curador_200(client, projeto, curador, nome):
    client.force_login(curador)
    resp = client.get(reverse(nome, args=[projeto.slug]))
    assert resp.status_code == 200


def test_projetos_lista(client, projeto, curador):
    client.force_login(curador)
    resp = client.get(reverse("anco_projetos"))
    assert resp.status_code == 200
    assert b"Piloto ANCO" in resp.content


def test_nao_membro_bloqueado(client, projeto):
    outro = User.objects.create_user(username="z", email="z@u.edu", password="x", pode_anco=True)
    client.force_login(outro)
    assert client.get(reverse("anco_painel", args=[projeto.slug])).status_code == 403


def test_sem_pode_anco_bloqueado(client, projeto):
    # Membro do projeto, mas sem acesso ao módulo (pode_anco=False) → 403.
    membro = User.objects.create_user(
        username="m2", email="m2@u.edu", password="x", pode_anco=False
    )
    MembroANCO.objects.create(projeto=projeto, usuario=membro, papel=MembroANCO.Papel.ANALISTA)
    client.force_login(membro)
    assert client.get(reverse("anco_painel", args=[projeto.slug])).status_code == 403


def test_sorteio_post_distribui(client, projeto, curador):
    # adiciona um analista e sorteia
    ana = User.objects.create_user(username="ana", email="ana@u.edu", password="x")
    MembroANCO.objects.create(projeto=projeto, usuario=ana, papel=MembroANCO.Papel.ANALISTA)
    client.force_login(curador)
    resp = client.post(reverse("anco_sorteio", args=[projeto.slug]), {"cota": 5, "modo_revisao": "unica"})
    assert resp.status_code == 302
    from apps.anco.models import AtribuicaoANCO

    assert AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).count() == 1


# --- gate de análise: corpus ANCO exige sorteio (analista comum) -------------


@pytest.fixture
def analista(db, projeto):
    u = User.objects.create_user(
        username="ana", email="ana@u.edu", password="x",
        pode_anco=True, papel=User.Papel.ANALISTA,
    )
    MembroANCO.objects.create(projeto=projeto, usuario=u, papel=MembroANCO.Papel.ANALISTA)
    return u


def _artigo_do_projeto(projeto):
    return projeto.itens.filter(removido=False).first().artigo


def test_analista_sem_sorteio_bloqueado(client, projeto, analista):
    art = _artigo_do_projeto(projeto)
    client.force_login(analista)
    resp = client.get(reverse("iniciar_analise", args=[art.pk]))
    assert resp.status_code == 403


def test_analista_sorteado_pode_analisar(client, projeto, analista):
    from apps.anco.sorteio import executar_sorteio

    executar_sorteio(projeto, cota=5, semente=1)
    art = _artigo_do_projeto(projeto)
    client.force_login(analista)
    resp = client.get(reverse("iniciar_analise", args=[art.pk]))
    assert resp.status_code == 302  # iniciou (redireciona ao editor)


def test_curador_projeto_analisa_em_qualquer_tempo(client, projeto):
    # Curador do projeto SEM ser curador global (papel analista global): mesmo
    # assim analisa qualquer item do corpus, sem sorteio.
    cur = User.objects.create_user(
        username="curproj", email="cp@u.edu", password="x",
        pode_anco=True, papel=User.Papel.ANALISTA,
    )
    MembroANCO.objects.create(projeto=projeto, usuario=cur, papel=MembroANCO.Papel.CURADOR)
    art = _artigo_do_projeto(projeto)
    client.force_login(cur)
    resp = client.get(reverse("iniciar_analise", args=[art.pk]))
    assert resp.status_code == 302


def test_corpus_filtro_acervo_vs_aguardando(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    # projeto já tem 1 item novo ("Artigo X"); adiciona 1 do acervo (legado).
    leg = Artigo.objects.create(titulo="Legado", ano=2018, eh_legado=True)
    ItemCorpus.objects.create(projeto=projeto, titulo="Legado", identificador="l:1", artigo=leg)
    client.force_login(curador)
    url = reverse("anco_corpus", args=[projeto.slug])

    assert client.get(url + "?filtro=acervo").content.count(b'class="tg-card"') == 1
    assert client.get(url + "?filtro=novos").content.count(b'class="tg-card"') == 1
    assert client.get(url).content.count(b'class="tg-card"') == 2


def test_corpus_filtro_por_fonte(client, projeto, curador):
    from apps.anco.importacao import importar_para_fonte
    from apps.anco.models import FonteImport

    f1 = FonteImport.objects.create(projeto=projeto, outra_base="Base A", criado_por=curador)
    f2 = FonteImport.objects.create(projeto=projeto, outra_base="Base B", criado_por=curador)
    importar_para_fonte(f1, [{"titulo": "A1", "doi": "10.7/a1"}, {"titulo": "A2", "doi": "10.7/a2"}])
    importar_para_fonte(f2, [{"titulo": "B1", "doi": "10.7/b1"}])
    client.force_login(curador)
    url = reverse("anco_corpus", args=[projeto.slug])

    assert client.get(url + f"?fonte={f1.pk}").content.count(b'class="tg-card"') == 2
    assert client.get(url + f"?fonte={f2.pk}").content.count(b'class="tg-card"') == 1
    # "Todas" inclui também o item do fixture (sem fonte) → 1 + 2 + 1 = 4
    assert client.get(url).content.count(b'class="tg-card"') == 4


# --- editar/excluir item do corpus: dono (importador) + curador/admin --------


def _item_com_fonte(projeto, por, doi="10.8/e1", titulo="Editável"):
    from apps.anco.importacao import importar_para_fonte
    from apps.anco.models import FonteImport, ItemCorpus

    f = FonteImport.objects.create(projeto=projeto, outra_base="Base", criado_por=por)
    importar_para_fonte(f, [{"titulo": titulo, "doi": doi}])
    return ItemCorpus.objects.get(projeto=projeto, doi=doi)


def test_importador_edita_item_e_sincroniza(client, projeto, analista):
    item = _item_com_fonte(projeto, analista)
    client.force_login(analista)
    url = reverse("anco_corpus_editar", args=[projeto.slug, item.pk])
    assert client.get(url).status_code == 200
    resp = client.post(url, {"titulo": "Novo Título", "doi": item.doi})
    assert resp.status_code == 302
    item.refresh_from_db()
    item.artigo.refresh_from_db()
    assert item.titulo == "Novo Título"
    assert item.artigo.titulo == "Novo Título"  # sincronizou no Artigo


def test_nao_dono_ve_mas_nao_edita_item(client, projeto, curador):
    item = _item_com_fonte(projeto, curador)  # importado pelo curador
    outro = User.objects.create_user(
        username="outro", email="o@u.edu", password="x", pode_anco=True, papel=User.Papel.ANALISTA
    )
    from apps.anco.models import MembroANCO

    MembroANCO.objects.create(projeto=projeto, usuario=outro, papel=MembroANCO.Papel.ANALISTA)
    client.force_login(outro)
    url = reverse("anco_corpus_editar", args=[projeto.slug, item.pk])
    # vê (navega), mas sem formulário de edição
    resp = client.get(url)
    assert resp.status_code == 200
    assert b"Salvar altera" not in resp.content
    # tentar salvar → 403
    assert client.post(url, {"titulo": "hack"}).status_code == 403


def test_item_legado_ve_mas_nao_edita(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    leg = Artigo.objects.create(titulo="Curado", ano=2010, eh_legado=True)
    it = ItemCorpus.objects.create(projeto=projeto, titulo="Curado", identificador="leg:1", artigo=leg)
    client.force_login(curador)
    url = reverse("anco_corpus_editar", args=[projeto.slug, it.pk])
    resp = client.get(url)
    assert resp.status_code == 200  # legado é visível (só-leitura)
    assert b"Salvar altera" not in resp.content
    assert client.post(url, {"titulo": "x"}).status_code == 403


def test_importador_remove_item(client, projeto, analista):
    item = _item_com_fonte(projeto, analista, doi="10.8/rm")
    client.force_login(analista)
    resp = client.post(reverse("anco_corpus_excluir", args=[projeto.slug]), {"item_id": item.pk})
    assert resp.status_code == 302
    item.refresh_from_db()
    assert item.removido is True


def test_painel_conta_fonte_reflete_remocao(client, projeto, curador):
    """Remover item do corpus atualiza a contagem por fonte no painel (ao vivo)."""
    item = _item_com_fonte(projeto, curador, doi="10.8/pa", titulo="P1")
    client.force_login(curador)
    painel = reverse("anco_painel", args=[projeto.slug])
    assert b"1 no corpus" in client.get(painel).content
    item.removido = True
    item.save(update_fields=["removido"])
    assert b"0 no corpus" in client.get(painel).content


def test_tela_sorteio_conta_so_novos(client, projeto, curador):
    """A tela de sorteio mostra só os novos como entrantes; acervo fica de fora."""
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    # fixture já tem 1 novo ("Artigo X"); adiciona 1 do acervo (legado).
    leg = Artigo.objects.create(titulo="Curado", ano=2009, eh_legado=True)
    ItemCorpus.objects.create(projeto=projeto, titulo="Curado", identificador="cur:1", artigo=leg)
    client.force_login(curador)
    html = client.get(reverse("anco_sorteio", args=[projeto.slug])).content.decode()
    assert "1 já no acervo nunca entram" in html  # acervo fora do sorteio
    assert ">1</strong> elegíve" in html  # só o novo ("Artigo X") é elegível
    assert "de 1 novo" in html


def test_sorteio_filtros_na_tela_e_no_post(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import AtribuicaoANCO, ItemCorpus, MembroANCO

    ana = User.objects.create_user(username="anaf", email="anaf@u.edu", password="x")
    MembroANCO.objects.create(projeto=projeto, usuario=ana, papel=MembroANCO.Papel.ANALISTA)
    # fixture já tem "Artigo X" (sem o termo). Adiciona 1 com o termo no resumo.
    a = Artigo.objects.create(titulo="Tem termo", ano=2021)
    ItemCorpus.objects.create(
        projeto=projeto, titulo="Tem termo", identificador="i:t", artigo=a,
        resumo="trata de análise cognitiva",
    )
    client.force_login(curador)
    url = reverse("anco_sorteio", args=[projeto.slug])

    # GET: a tela oferece os campos como checkboxes (não há mais filtro de tipos)
    html = client.get(url).content.decode()
    assert "Onde o termo aparece" in html
    assert 'name="campos" value="resumo"' in html
    assert "Tipos de documento" not in html

    # POST exigindo o termo no resumo: o sorteio só atribui o que casa
    resp = client.post(
        url, {"cota": 5, "modo_revisao": "unica", "termo": "cognitiva", "campos": ["resumo"]}
    )
    assert resp.status_code == 302
    atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).values_list("artigo__titulo", flat=True)
    )
    assert atribuidos == {"Tem termo"}


def test_sorteio_parcial_elegiveis_reflete_filtro(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    for titulo, resumo, palavras in [
        ("Art A", "fala de análise cognitiva", ""),
        ("Art B", "outro assunto", ""),
        ("Art C", "nada", "cognitiva"),
    ]:
        a = Artigo.objects.create(titulo=titulo, ano=2021)
        ItemCorpus.objects.create(
            projeto=projeto, titulo=titulo, identificador=f"e:{titulo}", artigo=a,
            resumo=resumo, palavras_chaves=palavras,
        )
    client.force_login(curador)
    url = reverse("anco_sorteio_elegiveis", args=[projeto.slug])

    # sem filtro: fixture "Artigo X" + 3 = 4 elegíveis
    assert b">4</strong> eleg" in client.get(url).content
    # termo só no resumo: 1 (Art A)
    r = client.get(url + "?termo=cognitiva&campos=resumo").content
    assert b">1</strong> eleg" in r and b"casou em" in r
    # termo no resumo OU palavras-chave: 2 (Art A + Art C)
    assert b">2</strong> eleg" in client.get(url + "?termo=cognitiva&campos=resumo&campos=palavras_chave").content


def test_item_navegacao_e_link_artigo(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    its = []
    for i in range(3):
        a = Artigo.objects.create(titulo=f"N{i}", ano=2021, doi=f"10.9/n{i}")
        its.append(ItemCorpus.objects.create(projeto=projeto, titulo=f"N{i}", identificador=f"n:{i}", artigo=a))
    client.force_login(curador)
    meio = its[1]
    html = client.get(reverse("anco_corpus_editar", args=[projeto.slug, meio.pk])).content.decode()
    # tem Voltar e Avançar ativos (links), posição e link "Ver artigo"
    assert "← Voltar" in html and "Avançar →" in html
    assert "Ver artigo" in html
    # os links de navegação apontam para itens vizinhos do corpus
    assert reverse("anco_corpus_editar", args=[projeto.slug, its[0].pk]) in html
    assert reverse("anco_corpus_editar", args=[projeto.slug, its[2].pk]) in html
