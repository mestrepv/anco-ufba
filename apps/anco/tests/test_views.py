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
    ItemCorpus.objects.create(
        projeto=p, titulo="Artigo X", identificador="doi:10.1/x", artigo=art,
        resumo="resumo do Artigo X",
    )
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

    # Filtro agora é por NOME da base (agrupa importações), não por id de fonte.
    assert client.get(url + "?fonte=Base A").content.count(b'class="tg-card"') == 2
    assert client.get(url + "?fonte=Base B").content.count(b'class="tg-card"') == 1
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
    assert "de 1 disponíve" in html


def test_sorteio_filtros_na_tela_e_no_post(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import AtribuicaoANCO, ItemCorpus, MembroANCO

    ana = User.objects.create_user(username="anaf", email="anaf@u.edu", password="x")
    MembroANCO.objects.create(projeto=projeto, usuario=ana, papel=MembroANCO.Papel.ANALISTA)
    # fixture já tem "Artigo X" (tipo vazio = "outro"). Adiciona um artigo e um livro.
    for titulo, tipo in [("Um artigo", "Artigo"), ("Um livro", "Livro")]:
        a = Artigo.objects.create(titulo=titulo, ano=2021)
        ItemCorpus.objects.create(
            projeto=projeto, titulo=titulo, identificador=f"i:{titulo}", artigo=a,
            resumo="r", tipo=tipo,
        )
    client.force_login(curador)
    url = reverse("anco_sorteio", args=[projeto.slug])

    # GET: a tela oferece o filtro por tipo e o toggle de resumo (não há mais termo).
    html = client.get(url).content.decode()
    assert "Tipos de documento" in html
    assert 'name="tipos" value="artigo"' in html
    assert "Somente com resumo" in html
    assert "Onde o termo aparece" not in html

    # POST restringindo a artigos: só o item tipo Artigo é atribuído.
    resp = client.post(
        url,
        {"cota": 5, "modo_revisao": "unica", "filtros": "1", "com_resumo": "1", "tipos": ["artigo"]},
    )
    assert resp.status_code == 302
    atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).values_list("artigo__titulo", flat=True)
    )
    assert atribuidos == {"Um artigo"}


def test_sorteio_parcial_elegiveis_reflete_filtro(client, projeto, curador):
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    for titulo, tipo, resumo in [
        ("Art A", "Artigo", "r"),
        ("Art B", "Tese", "r"),
        ("Art C", "Livro", ""),  # sem resumo
    ]:
        a = Artigo.objects.create(titulo=titulo, ano=2021)
        ItemCorpus.objects.create(
            projeto=projeto, titulo=titulo, identificador=f"e:{titulo}", artigo=a,
            resumo=resumo, tipo=tipo,
        )
    client.force_login(curador)
    url = reverse("anco_sorteio_elegiveis", args=[projeto.slug])

    # primeira carga (defaults: resumo ligado, todos os tipos): Artigo X + A + B = 3
    # (Art C fica fora por não ter resumo).
    assert b">3</strong> eleg" in client.get(url).content
    # só artigos: 1 (Art A); "Artigo X" é categoria "outro" e fica fora.
    r = client.get(url + "?filtros=1&com_resumo=1&tipos=artigo").content
    assert b">1</strong> eleg" in r
    # artigos + teses: 2 (Art A + Art B)
    assert b">2</strong> eleg" in client.get(url + "?filtros=1&com_resumo=1&tipos=artigo&tipos=tese").content
    # livros, sem exigir resumo: 1 (Art C entra porque o toggle de resumo foi desligado)
    assert b">1</strong> eleg" in client.get(url + "?filtros=1&tipos=livro").content


def test_navega_por_importacao(client, projeto, curador):
    """Clicar num import abre a ficha do 1º item e navega só entre os itens
    daquela importação (não o corpus inteiro), com volta ao painel."""
    import re

    from apps.anco.importacao import importar_para_fonte
    from apps.anco.models import FonteImport

    fonte = FonteImport.objects.create(projeto=projeto, outra_base="Scopus", criado_por=curador)
    importar_para_fonte(fonte, [
        {"titulo": "Imp 1", "doi": "10.7/1", "resumo": "r"},
        {"titulo": "Imp 2", "doi": "10.7/2", "resumo": "r"},
        {"titulo": "Imp 3", "doi": "10.7/3", "resumo": "r"},
    ])
    client.force_login(curador)

    # clicar no import redireciona à ficha do 1º item, com ctx=import
    r = client.get(reverse("anco_corpus_import_nav", args=[projeto.slug, fonte.pk]))
    assert r.status_code == 302
    assert "ctx=import" in r.headers["Location"] and f"import={fonte.pk}" in r.headers["Location"]

    # a navegação percorre só os 3 dessa importação (não o "Artigo X" da fixture)
    html = client.get(r.headers["Location"]).content.decode()
    assert "Item da importação <strong" in html
    assert 'de <strong style="color:var(--color-ink);">3</strong>' in html
    nxt = re.search(r'href="([^"]*editar/[^"]*)"[^>]*>Avançar', html)
    assert nxt and "ctx=import" in nxt.group(1) and f"import={fonte.pk}" in nxt.group(1)
    assert "Painel</a>" in html  # volta para o painel


def test_navega_import_filtro_so_novos(client, projeto, curador):
    """Na navegação por importação, o filtro 'só novos' exclui os já no acervo."""
    from apps.acervo.models import Artigo
    from apps.anco.models import FonteImport, ItemCorpus

    fonte = FonteImport.objects.create(projeto=projeto, outra_base="Base", criado_por=curador)
    for i in range(2):
        a = Artigo.objects.create(titulo=f"Novo {i}", ano=2022, doi=f"10.6/n{i}", eh_legado=False)
        ItemCorpus.objects.create(
            projeto=projeto, titulo=f"Novo {i}", doi=f"10.6/n{i}", identificador=f"n:{i}", artigo=a
        ).origem_fontes.add(fonte)
    leg = Artigo.objects.create(titulo="Legado", ano=2010, doi="10.6/leg", eh_legado=True)
    ItemCorpus.objects.create(
        projeto=projeto, titulo="Legado", doi="10.6/leg", identificador="l:1", artigo=leg
    ).origem_fontes.add(fonte)

    client.force_login(curador)
    nav = reverse("anco_corpus_import_nav", args=[projeto.slug, fonte.pk])

    # sem filtro: 3 itens; a ficha oferece o toggle "só os novos (2)"
    r = client.get(nav)
    html = client.get(r.headers["Location"]).content.decode()
    assert 'de <strong style="color:var(--color-ink);">3</strong>' in html
    assert "só os novos (2)" in html

    # com filtro: 2 itens (exclui o legado)
    r2 = client.get(nav + "?novos=1")
    assert "novos=1" in r2.headers["Location"]
    html2 = client.get(r2.headers["Location"]).content.decode()
    assert 'de <strong style="color:var(--color-ink);">2</strong>' in html2
    assert "Mostrando só os novos (2)" in html2


def test_import_nav_sem_itens_redireciona(client, projeto, curador):
    from apps.anco.models import FonteImport

    fonte = FonteImport.objects.create(projeto=projeto, outra_base="Vazia", criado_por=curador)
    client.force_login(curador)
    r = client.get(reverse("anco_corpus_import_nav", args=[projeto.slug, fonte.pk]))
    assert r.status_code == 302 and reverse("anco_corpus", args=[projeto.slug]) in r.headers["Location"]


def test_editar_navega_so_entre_elegiveis(client, projeto, curador):
    """Com ctx=elegiveis, a navegação anterior/próximo anda só no subconjunto
    elegível (com os filtros ativos), não no corpus inteiro."""
    from apps.acervo.models import Artigo
    from apps.anco.models import ItemCorpus

    itens = {}
    for titulo, tipo in [("Art A", "Artigo"), ("Art B", "Artigo"), ("Um livro", "Livro")]:
        a = Artigo.objects.create(titulo=titulo, ano=2021)
        itens[titulo] = ItemCorpus.objects.create(
            projeto=projeto, titulo=titulo, identificador=f"n:{titulo}", artigo=a,
            resumo="r", tipo=tipo,
        )
    client.force_login(curador)
    ed = reverse("anco_corpus_editar", args=[projeto.slug, itens["Art A"].pk])

    # sem contexto: navega o corpus inteiro (Artigo X + A + B + livro = 4)
    html = client.get(ed).content.decode()
    assert "Item <strong" in html and "de <strong style=\"color:var(--color-ink);\">4</strong>" in html

    # com ctx=elegiveis + só artigos: total = 2 (Art A + Art B), rótulo "Elegível"
    html = client.get(ed + "?ctx=elegiveis&filtros=1&com_resumo=1&tipos=artigo").content.decode()
    assert "Elegível <strong" in html
    assert "de <strong style=\"color:var(--color-ink);\">2</strong>" in html
    # o link "Avançar" preserva o contexto de elegíveis
    import re
    nxt = re.search(r'href="([^"]*editar/[^"]*)"[^>]*>Avançar', html)
    assert nxt and "ctx=elegiveis" in nxt.group(1) and "tipos=artigo" in nxt.group(1)


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
    # tem Voltar e Avançar ativos (links) e posição
    assert "← Voltar" in html and "Avançar →" in html
    # o link "Ver artigo" foi removido (tela do artigo é desnecessária)
    assert "Ver artigo" not in html
    # os links de navegação apontam para itens vizinhos do corpus
    assert reverse("anco_corpus_editar", args=[projeto.slug, its[0].pk]) in html
    assert reverse("anco_corpus_editar", args=[projeto.slug, its[2].pk]) in html


def test_fonte_excluir_confirma_e_executa(client, projeto, curador):
    from apps.anco.importacao import importar_para_fonte
    from apps.anco.models import FonteImport, ItemCorpus

    f = FonteImport.objects.create(projeto=projeto, outra_base="Lista X", criado_por=curador)
    importar_para_fonte(f, [{"titulo": "A", "doi": "10.2/a"}, {"titulo": "B", "doi": "10.2/b"}])
    client.force_login(curador)
    url = reverse("anco_fonte_excluir", args=[projeto.slug, f.pk])
    # GET: tela de confirmação com o resumo
    html = client.get(url).content.decode()
    assert "Excluir lista de fontes" in html and "Lista X" in html
    # POST: executa, redireciona ao painel; itens novos saem
    resp = client.post(url)
    assert resp.status_code == 302
    assert not FonteImport.objects.filter(pk=f.pk).exists()
    assert ItemCorpus.objects.filter(doi__in=["10.2/a", "10.2/b"], removido=True).count() == 2


def test_fonte_excluir_importador_ou_curador(client, projeto, analista):
    from apps.anco.models import FonteImport, MembroANCO

    f = FonteImport.objects.create(projeto=projeto, outra_base="L", criado_por=analista)
    # quem importou (analista, não curador) PODE excluir
    client.force_login(analista)
    assert client.get(reverse("anco_fonte_excluir", args=[projeto.slug, f.pk])).status_code == 200
    # outro membro que não importou nem é curador → 403
    outro = User.objects.create_user(username="outroana", email="oa@u.edu", password="x", pode_anco=True)
    MembroANCO.objects.create(projeto=projeto, usuario=outro, papel=MembroANCO.Papel.ANALISTA)
    client.force_login(outro)
    assert client.get(reverse("anco_fonte_excluir", args=[projeto.slug, f.pk])).status_code == 403


def test_nao_curador_nao_remove_item_no_acervo(client, projeto, analista):
    from apps.acervo.models import Analise

    item = _item_com_fonte(projeto, analista, doi="10.3/pub")
    Analise.objects.create(artigo=item.artigo, analista=analista, status=Analise.Status.PUBLICADA)
    client.force_login(analista)  # importou, mas item está no acervo (publicado)
    resp = client.post(reverse("anco_corpus_excluir", args=[projeto.slug]), {"item_id": item.pk})
    assert resp.status_code == 403  # acervo = só curador


def test_equipe_mudar_papel(client, projeto, curador):
    from apps.anco.models import MembroANCO

    ana = User.objects.create_user(username="anap", email="anap@u.edu", password="x", pode_anco=True)
    m = MembroANCO.objects.create(projeto=projeto, usuario=ana, papel=MembroANCO.Papel.ANALISTA)
    cur_m = MembroANCO.objects.get(projeto=projeto, usuario=curador)
    client.force_login(curador)
    url = reverse("anco_equipe", args=[projeto.slug])

    # promover analista → curador
    client.post(url, {"acao": "mudar_papel", "membro_id": m.pk, "papel": "curador"})
    m.refresh_from_db()
    assert m.papel == "curador"
    # rebaixar curador → analista
    client.post(url, {"acao": "mudar_papel", "membro_id": m.pk, "papel": "analista"})
    m.refresh_from_db()
    assert m.papel == "analista"
    # curador NÃO pode rebaixar a si mesmo
    client.post(url, {"acao": "mudar_papel", "membro_id": cur_m.pk, "papel": "analista"})
    cur_m.refresh_from_db()
    assert cur_m.papel == "curador"


def test_equipe_mudar_papel_so_curador(client, projeto, analista):
    from apps.anco.models import MembroANCO

    m = MembroANCO.objects.get(projeto=projeto, usuario=analista)
    client.force_login(analista)  # membro analista, não curador
    resp = client.post(
        reverse("anco_equipe", args=[projeto.slug]),
        {"acao": "mudar_papel", "membro_id": m.pk, "papel": "curador"},
    )
    assert resp.status_code == 403
    m.refresh_from_db()
    assert m.papel == "analista"
