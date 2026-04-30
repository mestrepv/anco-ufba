"""Testes da Fase 8 — Busca Semântica."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import Client
from django.urls import reverse


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def analise_publicada(db):
    """Análise publicada mínima para testar as views."""
    from django.contrib.auth import get_user_model

    from apps.acervo.models import Analise, Artigo
    from apps.vocabulario.models import TermoVocabulario, Vocabulario

    User = get_user_model()

    vocab, _ = Vocabulario.objects.get_or_create(codigo="base", defaults={"nome": "Base"})
    termo, _ = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab, nome="Teste", defaults={"ativo": True}
    )

    user = User.objects.create_user(username="analista_s8", email="s8@test.edu")
    artigo = Artigo.objects.create(
        doi="10.9999/semantica-test",
        titulo="Análise Cognitiva em Redes Científicas",
        resumo="Este artigo investiga cognição e redes.",
        base_consulta=termo,
    )
    return Analise.objects.create(
        artigo=artigo,
        analista=user,
        status=Analise.Status.PUBLICADA,
        objeto="Redes científicas de pesquisa",
        objetivo="Investigar padrões cognitivos",
    )


# ---------------------------------------------------------------------------
# 8.1 – Wrapper de embeddings
# ---------------------------------------------------------------------------


class TestEmbeddingsWrapper:
    def test_embed_query_retorna_none_quando_servico_falha(self):
        from apps.busca_semantica.embeddings import embed_query

        with patch("apps.busca_semantica.embeddings._post_with_retry", side_effect=Exception("off")):
            result = embed_query("cognição em redes")
        assert result is None

    def test_embed_query_retorna_lista_de_floats(self):
        from apps.busca_semantica.embeddings import embed_query

        vec = [0.1] * 384
        with patch("apps.busca_semantica.embeddings._post_with_retry", return_value=[vec]):
            # Limpa o cache LRU antes de testar
            from apps.busca_semantica.embeddings import _embed_cached
            _embed_cached.cache_clear()
            result = embed_query("cognição")
        assert isinstance(result, list)
        assert len(result) == 384

    def test_embed_texts_retorna_none_por_item_em_falha(self):
        from apps.busca_semantica.embeddings import embed_texts

        with patch("apps.busca_semantica.embeddings._post_with_retry", side_effect=Exception("off")):
            result = embed_texts(["texto 1", "texto 2"])
        assert result == [None, None]

    def test_service_available_false_quando_servico_offline(self):
        from apps.busca_semantica.embeddings import service_available

        with patch("apps.busca_semantica.embeddings.requests.get", side_effect=Exception("off")):
            assert service_available() is False

    def test_service_available_false_quando_not_ready(self):
        from apps.busca_semantica.embeddings import service_available

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"status": "ok", "ready": False}
        with patch("apps.busca_semantica.embeddings.requests.get", return_value=mock_resp):
            assert service_available() is False


# ---------------------------------------------------------------------------
# 8.2 – Campos de embedding nos modelos
# ---------------------------------------------------------------------------


class TestEmbeddingFields:
    def test_artigo_tem_campo_embedding(self, db):
        from apps.acervo.models import Artigo

        a = Artigo.objects.create(doi="10.1234/emb-test", titulo="Teste embedding")
        assert hasattr(a, "embedding")
        assert a.embedding is None

    def test_analise_tem_campos_embedding(self, analise_publicada):
        a = analise_publicada
        assert hasattr(a, "embedding")
        assert hasattr(a, "embedding_resenha")
        assert hasattr(a, "embedding_atualizado_em")


# ---------------------------------------------------------------------------
# 8.3 – Tasks de embedding (comportamento fail-safe)
# ---------------------------------------------------------------------------


class TestEmbeddingTasks:
    def test_task_artigo_nao_quebra_quando_servico_offline(self, db):
        from apps.acervo.models import Artigo
        from apps.busca_semantica.tasks import task_embedding_artigo

        a = Artigo.objects.create(doi="10.1234/task-test", titulo="Task test", resumo="texto")
        with patch("apps.busca_semantica.embeddings._post_with_retry", side_effect=Exception("off")):
            task_embedding_artigo(a.pk)  # não deve lançar exceção

        a.refresh_from_db()
        assert a.embedding is None  # embedding permanece None

    def test_task_analise_nao_quebra_quando_servico_offline(self, analise_publicada):
        from apps.busca_semantica.tasks import task_embedding_analise

        with patch("apps.busca_semantica.embeddings._post_with_retry", side_effect=Exception("off")):
            task_embedding_analise(analise_publicada.pk)

        analise_publicada.refresh_from_db()
        assert analise_publicada.embedding is None

    def test_task_artigo_salva_embedding_quando_servico_ok(self, db):
        from apps.acervo.models import Artigo
        from apps.busca_semantica.tasks import task_embedding_artigo

        vec = [0.1] * 384
        a = Artigo.objects.create(doi="10.1234/task-ok", titulo="Artigo com embedding", resumo="bom")
        with patch("apps.busca_semantica.embeddings._post_with_retry", return_value=[vec]):
            task_embedding_artigo(a.pk)

        a.refresh_from_db()
        assert a.embedding is not None
        assert len(a.embedding) == 384


# ---------------------------------------------------------------------------
# 8.4 – Interface de busca
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListagemModoSemantico:
    def test_toggle_textual_presente_na_listagem(self, client: Client):
        resp = client.get(reverse("acervo_publico"))
        assert resp.status_code == 200
        assert b'name="modo"' in resp.content
        assert b'value="textual"' in resp.content
        assert b'value="semantico"' in resp.content

    def test_modo_textual_por_padrao(self, client: Client):
        resp = client.get(reverse("acervo_publico"))
        assert resp.context["modo"] == "textual"

    def test_modo_semantico_preservado_na_url(self, client: Client):
        vec = [0.1] * 384
        with patch("apps.busca_semantica.embeddings.service_available", return_value=True), \
             patch("apps.busca_semantica.embeddings.embed_query", return_value=vec):
            resp = client.get(reverse("acervo_publico") + "?q=cognição&modo=semantico")
        assert resp.status_code == 200
        assert resp.context["modo"] == "semantico"

    def test_modo_invalido_cai_para_textual(self, client: Client):
        resp = client.get(reverse("acervo_publico") + "?modo=xpto")
        assert resp.context["modo"] == "textual"

    def test_semantico_sem_servico_degrada_para_textual(self, client: Client, analise_publicada):
        with patch("apps.busca_semantica.embeddings.service_available", return_value=False):
            resp = client.get(reverse("acervo_publico") + "?q=cognição&modo=semantico")
        assert resp.status_code == 200
        assert resp.context["modo"] == "textual"
        assert resp.context["servico_indisponivel"] is True

    def test_semantico_com_servico_retorna_resultados(self, client: Client, analise_publicada):
        vec = [0.1] * 384
        # Analise precisa ter embedding para aparecer nos resultados semânticos
        analise_publicada.embedding = vec
        analise_publicada.save(update_fields=["embedding"])

        with patch("apps.busca_semantica.embeddings.service_available", return_value=True), \
             patch("apps.busca_semantica.embeddings.embed_query", return_value=vec):
            resp = client.get(reverse("acervo_publico") + "?q=cognição&modo=semantico")

        assert resp.status_code == 200
        assert resp.context["modo"] == "semantico"
        assert len(resp.context["resultados_semanticos"]) >= 1
        # Verifica que o score está no range esperado
        score = resp.context["resultados_semanticos"][0]["score"]
        assert 0 <= score <= 100
