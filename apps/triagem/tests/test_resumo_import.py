"""Fase 10.1 — resumo de deduplicação por busca."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.acervo.models import Artigo
from apps.triagem.importacao import importar_para_busca, parse_ris
from apps.triagem.models import Busca, ProtocoloTriagem
from apps.vocabulario.models import TermoVocabulario, Vocabulario

from .conftest import membro, turl

User = get_user_model()
pytestmark = pytest.mark.django_db

RIS = """TY  - JOUR
TI  - Estudo sobre cognição
AU  - Silva, J.
PY  - 2020
DO  - 10.1/abc
ER  -
"""


@pytest.fixture
def protocolo(db):
    return ProtocoloTriagem.ativo()


@pytest.fixture
def base_termo(db):
    v, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    return TermoVocabulario.objects.create(vocabulario=v, nome="Scopus")


@pytest.fixture
def analista(db):
    return membro(
        User.objects.create_user(
            username="ana", email="a@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )


def test_menu_base_sem_prefixo(base_termo):
    from apps.triagem.forms import ImportarBuscaForm

    labels = [str(label) for _, label in ImportarBuscaForm().fields["base_consulta"].choices]
    assert "Scopus" in labels
    assert not any("base:" in label for label in labels)


def test_import_persiste_contagens_na_busca(protocolo, base_termo):
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    importar_para_busca(b, parse_ris(RIS))
    b.refresh_from_db()
    assert b.n_lidos == 1
    assert b.n_novos == 1
    assert b.n_ja_no_acervo == 0
    assert b.importado_em is not None


def test_ja_no_acervo_contado(protocolo, base_termo):
    Artigo.objects.create(doi="10.1/abc", titulo="x", ano=2020, base_consulta=base_termo)
    b = Busca.objects.create(protocolo=protocolo, base_consulta=base_termo)
    importar_para_busca(b, parse_ris(RIS))
    b.refresh_from_db()
    assert b.n_ja_no_acervo == 1 and b.n_novos == 0


def _upload(client, base_termo, n_identificados, conteudo=RIS, **extra):
    arq = SimpleUploadedFile("scopus.ris", conteudo.encode("utf-8"))
    data = {
        "base_consulta": base_termo.pk,
        "formato": "",
        "arquivo": arq,
        "n_identificados": n_identificados,
        **extra,
    }
    return client.post(turl("triagem_importar"), data=data)


def test_n_identificados_opcional_usa_contagem(client, analista, base_termo, settings, tmp_path):
    """Sem o nº reportado, a importação usa a contagem do próprio arquivo."""
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    arq = SimpleUploadedFile("s.ris", RIS.encode("utf-8"))
    resp = client.post(
        turl("triagem_importar"),
        data={"base_consulta": base_termo.pk, "arquivo": arq},  # sem n_identificados
    )
    assert resp.status_code == 302  # importa
    busca = Busca.objects.latest("pk")
    assert busca.n_identificados == 1  # auto = contagem do arquivo (RIS tem 1 registro)


def test_preview_arquivo_bom(client, analista, base_termo, settings, tmp_path):
    """Preview HTMX conta os registros de um arquivo válido."""
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    arq = SimpleUploadedFile("s.ris", RIS.encode("utf-8"))
    resp = client.post(turl("triagem_importar_preview"), data={"arquivo": arq})
    assert resp.status_code == 200
    assert b"1 registro" in resp.content
    assert '"ok": true' in resp.headers.get("HX-Trigger", "")


def test_preview_arquivo_ruim_pdf(client, analista, base_termo, settings, tmp_path):
    """Preview rejeita um PDF (binário) com mensagem amigável e trava (ok=false)."""
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    pdf = SimpleUploadedFile("doc.pdf", b"%PDF-1.7\n...", content_type="application/pdf")
    resp = client.post(turl("triagem_importar_preview"), data={"arquivo": pdf})
    assert resp.status_code == 200
    assert b"PDF" in resp.content
    assert '"ok": false' in resp.headers.get("HX-Trigger", "")


def test_upload_guarda_filtros_estruturados(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(
        client,
        base_termo,
        1,
        string_busca="cog",
        campos_busca=["topico", "resumo"],
        ano_inicio=2017,
        ano_fim=2025,
        idiomas=["en", "pt"],
        tipos_documento=["artigo", "revisao"],
        filtros="acesso aberto",
    )
    assert resp.status_code == 302
    busca = Busca.objects.latest("pk")
    assert busca.ano_inicio == 2017 and busca.ano_fim == 2025
    assert set(busca.idiomas) == {"en", "pt"}
    assert set(busca.tipos_documento) == {"artigo", "revisao"}
    assert set(busca.campos_busca) == {"topico", "resumo"}
    assert busca.filtros == "acesso aberto"
    assert busca.periodo == "2017–2025"
    resumo = client.get(resp.headers["Location"])
    assert b"Estrat" in resumo.content
    assert b"2017" in resumo.content


def test_periodo_invalido_bloqueia(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1, ano_inicio=2025, ano_fim=2017)  # início > fim
    assert resp.status_code == 200  # re-renderiza com erro
    assert not Busca.objects.exists()


def test_idioma_outro_exige_especificacao(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1, idiomas=["outro"])  # sem especificar
    assert resp.status_code == 200  # bloqueia
    assert not Busca.objects.exists()


def test_idioma_outro_especificado_grava_e_exibe(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1, idiomas=["en", "outro"], idioma_outro="Catalão")
    assert resp.status_code == 302
    busca = Busca.objects.latest("pk")
    assert busca.idioma_outro == "Catalão"
    assert "Outro (Catalão)" in busca.idiomas_display
    resumo = client.get(resp.headers["Location"])
    assert "Catalão".encode() in resumo.content


def test_resumo_avisa_divergencia(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    # base reportou 466, mas o arquivo só tem 1 registro
    resp = _upload(client, base_termo, 466)
    resumo = client.get(resp.headers["Location"])
    assert b"Diverg" in resumo.content
    assert b"incompleto" in resumo.content
    assert b"466" in resumo.content


def test_resumo_confere_quando_bate(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1)  # arquivo tem 1, informado 1
    resumo = client.get(resp.headers["Location"])
    assert b"Confere" in resumo.content


def test_detalhe_mostra_ja_no_acervo_e_data(client, analista, base_termo, settings, tmp_path):
    from apps.acervo.models import Artigo

    settings.MEDIA_ROOT = str(tmp_path)
    Artigo.objects.create(doi="10.1/abc", titulo="x", ano=2020, base_consulta=base_termo)
    client.force_login(analista)
    resp = _upload(client, base_termo, 1)  # RIS tem doi 10.1/abc → já no acervo
    detalhe = client.get(resp.headers["Location"])
    assert "já no acervo".encode() in detalhe.content  # contador de isentos
    assert b"Importada em" in detalhe.content
    assert b"Excluir importa" in detalhe.content  # botão presente (intocada)


def test_painel_lista_importacoes_clicaveis(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    _upload(client, base_termo, 1)
    busca = Busca.objects.latest("pk")
    r = client.get(turl("triagem_painel"))
    assert turl("triagem_busca_resumo", args=[busca.pk]).encode() in r.content
    assert b"busca-row" in r.content


def test_excluir_busca_intocada(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    _upload(client, base_termo, 1)
    busca = Busca.objects.latest("pk")
    from apps.triagem.models import RegistroTriagem

    assert RegistroTriagem.objects.filter(doi="10.1/abc").exists()
    resp = client.post(turl("triagem_busca_excluir", args=[busca.pk]))
    assert resp.status_code == 302
    assert resp.headers["Location"] == turl("triagem_painel")
    assert not Busca.objects.filter(pk=busca.pk).exists()
    assert not RegistroTriagem.objects.filter(doi="10.1/abc").exists()


def test_excluir_bloqueado_para_nao_curador_apos_triagem(
    client, analista, base_termo, settings, tmp_path
):
    """Após a triagem começar, o importador não-curador é bloqueado (403)."""
    from apps.triagem.models import RegistroTriagem

    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    _upload(client, base_termo, 1)
    busca = Busca.objects.latest("pk")
    reg = RegistroTriagem.objects.get(doi="10.1/abc")
    reg.status = RegistroTriagem.Status.EM_TRIAGEM  # já entrou em triagem
    reg.save()
    resp = client.post(turl("triagem_busca_excluir", args=[busca.pk]))
    assert resp.status_code == 403
    assert Busca.objects.filter(pk=busca.pk).exists()  # NÃO excluiu
    assert RegistroTriagem.objects.filter(pk=reg.pk).exists()


def test_curador_exclui_apos_triagem_em_cascata(client, analista, base_termo, settings, tmp_path):
    """Após a triagem, o curador pode excluir — e a triagem vai junto."""
    from apps.triagem.models import RegistroTriagem

    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)
    _upload(client, base_termo, 1)
    busca = Busca.objects.latest("pk")
    reg = RegistroTriagem.objects.get(doi="10.1/abc")
    reg.status = RegistroTriagem.Status.INCLUIDO
    reg.save()

    curador = membro(
        User.objects.create_user(
            username="cur",
            email="cur@u.edu",
            password="x",
            papel=User.Papel.CURADOR,
            is_staff=True,
        ),
        papel="curador",
    )
    client.force_login(curador)
    resp = client.post(turl("triagem_busca_excluir", args=[busca.pk]))
    assert resp.status_code == 302
    assert not Busca.objects.filter(pk=busca.pk).exists()  # excluída
    assert not RegistroTriagem.objects.filter(pk=reg.pk).exists()  # triagem junto


def test_excluir_so_pelo_importador_ou_curador(client, analista, base_termo, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client.force_login(analista)  # analista importa → é o dono
    _upload(client, base_termo, 1)
    busca = Busca.objects.latest("pk")

    # outro membro (não importou) não vê o botão nem pode excluir
    outro = membro(
        User.objects.create_user(
            username="outro", email="outro@u.edu", password="x", papel=User.Papel.ANALISTA
        )
    )
    client.force_login(outro)
    detalhe = client.get(turl("triagem_busca_resumo", args=[busca.pk]))
    assert b"Excluir importa" not in detalhe.content  # botão escondido
    resp = client.post(turl("triagem_busca_excluir", args=[busca.pk]))
    assert resp.status_code == 403
    assert Busca.objects.filter(pk=busca.pk).exists()  # nada foi excluído
