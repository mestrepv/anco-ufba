"""Testes do comando migrate_legacy: idempotencia e comportamento end-to-end."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

User = get_user_model()


@pytest.fixture
def vocab_completo(db):
    """Recria os vocabulários canônicos sem usar a fixture (testes isolados)."""
    base = Vocabulario.objects.create(codigo="base", nome="Base")
    epist = Vocabulario.objects.create(codigo="epistemologia", nome="Epistemologia")
    teoria = Vocabulario.objects.create(codigo="teoria", nome="Teoria")
    TermoVocabulario.objects.create(vocabulario=base, nome="Web of Science", sinonimos=["WOS"])
    TermoVocabulario.objects.create(
        vocabulario=epist, nome="Empirismo", sinonimos=["empirismo", "Empírica"]
    )
    TermoVocabulario.objects.create(vocabulario=teoria, nome="Cognição", sinonimos=["cognição"])


@pytest.fixture
def json_legado(tmp_path):
    """JSON sintetico cobrindo casos comuns da base real."""
    registros = [
        # Caso 1: registro completo, todos campos preenchidos
        {
            "_linha": 2,
            "Numero_DOI": "10.1234/completo.001",
            "Base_de_Consulta": "Web of Science",
            "Titulo_do_artigo": "Artigo Completo",
            "Ano": 2020,
            "Volume": 1,
            "Numero": 2,
            "Pagina_Inicial": 10,
            "Pagina_Final": 20,
            "Titulo_do_Periodico": "Revista X",
            "Area": "Cognição",
            "Nomes": "Autor Sobrenome",
            "Vinculacao_Institucional": "UFBA",
            "Palavras_Chaves": "cognição, análise",
            "Resumo": "Resumo do artigo.",
            "Presenca_AC_no_Titulo": "Sim",
            "Presenca_AC_no_Resumo": "Não",
            "Presenca_AC_nas_PalavrasChaves": "1",
            "Presenca_AC_nas_Referencias": "0",
            "Presenca_AC_no_Corpo": "x",
            "Pertinencia_para_Area": "sim",
            "Aspectos_Relevantes": "Aspectos importantes.",
            "Define_Conceito": "Não",
            "Objeto": "Cognição",
            "Objetivo": "Investigar",
            "Foco": "Foco X",
            "Metodologia": "Estudo de caso",
            "Epistemologia": "empirismo",
            "Teoria": "Cognição",
            "Referenciais": "Refs",
            "Resultados": "Resultados",
            "Contexto_de_Producao": "Doutorado",
            "Outras_Observacoes": "Obs",
            "Analista": "MARIA SILVA",
            "Link_de_Acesso": "https://example.org/artigo1",
            "Universidade": "UFBA",
            "Artigo_Pago": "não",
            "Outra_Base_de_Consulta": "",
            "Termos_mais_frequentes": "",
        },
        # Caso 2: sem DOI, sem analista, sem link, ano invalido
        {
            "_linha": 3,
            "Numero_DOI": "",
            "Base_de_Consulta": "Scopus",
            "Titulo_do_artigo": "Artigo Sem DOI",
            "Ano": 21,  # invalido
            "Volume": "",
            "Numero": "",
            "Pagina_Inicial": "",
            "Pagina_Final": "",
            "Titulo_do_Periodico": "Revista Y",
            "Area": "",
            "Nomes": "",
            "Vinculacao_Institucional": "-",
            "Palavras_Chaves": "",
            "Resumo": "",
            "Presenca_AC_no_Titulo": "",
            "Presenca_AC_no_Resumo": "",
            "Presenca_AC_nas_PalavrasChaves": "",
            "Presenca_AC_nas_Referencias": "",
            "Presenca_AC_no_Corpo": "",
            "Pertinencia_para_Area": "",
            "Aspectos_Relevantes": "",
            "Define_Conceito": "",
            "Objeto": "",
            "Objetivo": "",
            "Foco": "",
            "Metodologia": "",
            "Epistemologia": "",
            "Teoria": "",
            "Referenciais": "",
            "Resultados": "",
            "Contexto_de_Producao": "",
            "Outras_Observacoes": "",
            "Analista": "",
            "Link_de_Acesso": "",
            "Universidade": "",
            "Artigo_Pago": "",
            "Outra_Base_de_Consulta": "",
            "Termos_mais_frequentes": "",
        },
        # Caso 3: DOI com prefixo "DOI:", variantes de capitalizacao no analista
        {
            "_linha": 4,
            "Numero_DOI": "DOI: 10.1234/prefixo.002",
            "Base_de_Consulta": "Web of Science",
            "Titulo_do_artigo": "Artigo Prefixo",
            "Ano": 2018,
            "Volume": "",
            "Numero": "",
            "Pagina_Inicial": "",
            "Pagina_Final": "",
            "Titulo_do_Periodico": "Revista X",
            "Area": "",
            "Nomes": "",
            "Vinculacao_Institucional": "",
            "Palavras_Chaves": "",
            "Resumo": "",
            "Presenca_AC_no_Titulo": "",
            "Presenca_AC_no_Resumo": "",
            "Presenca_AC_nas_PalavrasChaves": "",
            "Presenca_AC_nas_Referencias": "",
            "Presenca_AC_no_Corpo": "",
            "Pertinencia_para_Area": "",
            "Aspectos_Relevantes": "",
            "Define_Conceito": "",
            "Objeto": "",
            "Objetivo": "",
            "Foco": "",
            "Metodologia": "",
            "Epistemologia": "Empírica",  # variante -> deve resolver para Empirismo
            "Teoria": "",
            "Referenciais": "",
            "Resultados": "",
            "Contexto_de_Producao": "",
            "Outras_Observacoes": "",
            "Analista": "maria silva",  # mesmo analista do caso 1, capitalizacao diferente
            "Link_de_Acesso": "",
            "Universidade": "",
            "Artigo_Pago": "",
            "Outra_Base_de_Consulta": "",
            "Termos_mais_frequentes": "",
        },
    ]
    path = tmp_path / "legado.json"
    path.write_text(json.dumps(registros, ensure_ascii=False))
    return path


class TestMigrateLegacy:
    def test_importa_3_registros(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        assert Artigo.objects.filter(eh_legado=True).count() == 3
        assert Analise.objects.filter(status=Analise.Status.LEGADO).count() == 3

    def test_idempotencia_segunda_rodada_nao_duplica(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        artigos_apos_1 = Artigo.objects.count()
        analises_apos_1 = Analise.objects.count()
        users_apos_1 = User.objects.count()

        call_command("migrate_legacy", path=str(json_legado))

        assert Artigo.objects.count() == artigos_apos_1
        assert Analise.objects.count() == analises_apos_1
        assert User.objects.count() == users_apos_1

    def test_doi_invalido_gera_id_legacy(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        # registro 2 tem DOI vazio -> deve ter `legacy:` prefix
        assert Artigo.objects.filter(doi__startswith="legacy:").count() == 1

    def test_doi_canonico_preservado(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        assert Artigo.objects.filter(doi="10.1234/completo.001").exists()

    def test_doi_com_prefixo_e_normalizado(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        # DOI: 10.1234/prefixo.002 -> 10.1234/prefixo.002
        assert Artigo.objects.filter(doi="10.1234/prefixo.002").exists()

    def test_ano_invalido_vira_null(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        sem_doi = Artigo.objects.get(doi__startswith="legacy:")
        assert sem_doi.ano is None

    def test_analista_anonimo_para_registros_sem_analista(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        anonimo = User.objects.get(username="legado-anonimo")
        # Registro 2 sem analista
        analises_anonimas = Analise.objects.filter(analista=anonimo).count()
        assert analises_anonimas == 1

    def test_variantes_de_capitalizacao_consolidam_no_mesmo_user(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        # "MARIA SILVA" e "maria silva" -> mesmo User "Maria Silva"
        assert User.objects.filter(eh_legado=True, username="legado-maria-silva").count() == 1

    def test_user_legado_tem_atributos_corretos(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        u = User.objects.get(username="legado-maria-silva")
        assert u.eh_legado is True
        assert u.papel == User.Papel.LEITOR
        assert u.is_active is False
        assert u.email.endswith("@anco.local")

    def test_resolucao_de_sinonimo_de_vocabulario(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        # Registro 1: "empirismo" (sinonimo) e Registro 3: "Empírica" (sinonimo)
        # Ambos devem vincular ao termo canonico "Empirismo"
        empirismo = TermoVocabulario.objects.get(nome="Empirismo")
        analises_com_empirismo = Analise.objects.filter(epistemologia=empirismo).count()
        assert analises_com_empirismo == 2

    def test_dry_run_nao_grava(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado), dry_run=True)
        assert Artigo.objects.filter(eh_legado=True).count() == 0
        assert Analise.objects.filter(status=Analise.Status.LEGADO).count() == 0

    def test_presenca_ac_normalizada_para_bool(self, vocab_completo, json_legado):
        call_command("migrate_legacy", path=str(json_legado))
        a = Analise.objects.get(artigo__doi="10.1234/completo.001")
        assert a.presenca_titulo is True  # "Sim"
        assert a.presenca_resumo is False  # "Não"
        assert a.presenca_palavras_chave is True  # "1"
        assert a.presenca_referencias is False  # "0"
        assert a.presenca_corpo is True  # "x"
