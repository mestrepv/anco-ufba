"""Modelos do app `acervo`: Artigo, SnapshotLink, Analise, Revisao."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from django.utils import timezone

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from pgvector.django import VectorField
from simple_history.models import HistoricalRecords

from apps.vocabulario.models import TermoVocabulario


def _ano_max() -> int:
    return datetime.now(tz=UTC).year + 1


def _gerar_identificador_interno(titulo: str, ano: int | None, periodico: str) -> str:
    """
    Gera identificador determinístico no formato `legacy:<hash16>` a partir
    de título + ano + periódico. Mesma chave para os mesmos campos.
    """
    base = f"{(titulo or '').strip().lower()}|{ano or ''}|{(periodico or '').strip().lower()}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"legacy:{digest}"


class Artigo(models.Model):
    """
    Referencia bibliografica. NAO armazena a obra em si — apenas metadados
    e links de acesso a fontes externas.

    Identificacao: ao menos um entre `doi`, `isbn` ou `identificador_interno`
    sempre esta preenchido. O `identificador_interno` (formato
    `legacy:<hash16>`) eh gerado automaticamente no save() quando os outros
    dois estao vazios, garantindo unicidade ja para o legado e para artigos
    novos sem identificador externo.
    """

    class LinkStatus(models.TextChoices):
        NAO_VERIFICADO = "nao_verificado", "Não verificado"
        OK = "ok", "OK"
        QUEBRADO = "quebrado", "Quebrado"
        REDIRECIONA = "redireciona", "Redireciona"

    class TipoPublicacao(models.TextChoices):
        ARTIGO = "artigo", "Artigo de periódico"
        CAPITULO = "capitulo", "Capítulo de livro"
        LIVRO = "livro", "Livro"
        DISSERTACAO = "dissertacao", "Dissertação"
        TESE = "tese", "Tese"
        OUTRO = "outro", "Outro"

    doi = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="DOI canônico (10.xxxx/yyy). Vazio quando a obra é livro ou não tem DOI.",
    )
    isbn = models.CharField(
        max_length=17,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="ISBN-10 ou ISBN-13 (sem hífens). Usado para livros e capítulos.",
    )
    identificador_interno = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Fallback determinístico no formato `legacy:<hash16>` "
            "quando não há DOI nem ISBN. Gerado automaticamente."
        ),
    )
    tipo_publicacao = models.CharField(
        max_length=20,
        choices=TipoPublicacao.choices,
        default=TipoPublicacao.ARTIGO,
        db_index=True,
    )
    titulo = models.TextField()
    titulo_traduzido = models.TextField(
        blank=True,
        help_text="Tradução do título (PT-BR) gerada na curadoria.",
    )
    titulo_periodico = models.TextField(blank=True)
    ano = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1900), MaxValueValidator(_ano_max() + 0)],
    )
    volume = models.CharField(max_length=50, blank=True)
    numero = models.CharField(max_length=50, blank=True)
    pagina_inicial = models.CharField(max_length=20, blank=True)
    pagina_final = models.CharField(max_length=20, blank=True)
    area = models.CharField(max_length=200, blank=True)
    autores = models.TextField(blank=True)
    vinculacao_institucional = models.TextField(blank=True)
    palavras_chaves = models.TextField(blank=True)
    resumo = models.TextField(blank=True)

    base_consulta = models.ForeignKey(
        TermoVocabulario,
        on_delete=models.PROTECT,
        related_name="artigos_por_base",
        null=True,
        blank=True,
        limit_choices_to={"vocabulario__codigo": "base"},
    )
    outra_base_consulta = models.TextField(
        blank=True,
        help_text="Base adicional não modelada no vocabulário (campo da curadoria).",
    )

    link_acesso = models.URLField(
        max_length=600,
        blank=True,
        help_text="Link primario para a obra. Pode ficar vazio em registros legado.",
    )
    link_acesso_alternativo = models.URLField(
        max_length=600,
        blank=True,
        help_text="Repositorio institucional, preprint, mirror.",
    )
    artigo_pago = models.BooleanField(default=False)
    acesso_aberto = models.BooleanField(
        default=False,
        help_text="Selo: obra com licenca de acesso aberto.",
    )

    link_status = models.CharField(
        max_length=20,
        choices=LinkStatus.choices,
        default=LinkStatus.NAO_VERIFICADO,
        db_index=True,
    )
    link_ultima_verificacao = models.DateTimeField(null=True, blank=True)

    eh_legado = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marca artigos importados do JSON legado.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # Embedding semântico (Fase 8) — pgvector
    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text="Embedding de titulo+resumo+palavras_chaves (Fase 8).",
    )
    embedding_atualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "artigo"
        verbose_name_plural = "artigos"
        ordering = ["-ano", "titulo"]

    def __str__(self) -> str:
        ano = self.ano or "s.d."
        return f"{self.titulo[:80]} ({ano})"

    @property
    def tem_link(self) -> bool:
        return bool(self.link_acesso or self.link_acesso_alternativo)

    @property
    def identificador_canonico(self) -> str:
        """Retorna o melhor identificador disponível: DOI > ISBN > interno."""
        return self.doi or self.isbn or self.identificador_interno or ""

    def save(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """
        Normaliza identificadores e gera `identificador_interno` quando
        DOI e ISBN estão vazios. Strings vazias viram NULL para que a
        constraint UNIQUE não falhe entre múltiplos artigos sem DOI/ISBN.
        Operação idempotente.
        """
        if not self.doi:
            self.doi = None
        if not self.isbn:
            self.isbn = None
        if not self.doi and not self.isbn and not self.identificador_interno:
            self.identificador_interno = _gerar_identificador_interno(
                self.titulo, self.ano, self.titulo_periodico
            )
        super().save(*args, **kwargs)


class SnapshotLink(models.Model):
    """Snapshot do link no Internet Archive (Wayback Machine)."""

    artigo = models.ForeignKey(
        Artigo,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    url_original = models.URLField(max_length=600)
    url_wayback = models.URLField(max_length=600)
    capturado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "snapshot de link"
        verbose_name_plural = "snapshots de link"
        ordering = ["-capturado_em"]

    def __str__(self) -> str:
        return f"Snapshot {self.id} de {self.artigo_id}"


class Analise(models.Model):
    """
    Avaliacao estruturada de um Artigo. Multiplos analistas podem analisar
    o mesmo artigo, mas cada analista tem no maximo uma analise por artigo.

    Status `legado` marca registros importados pre-validados.
    Status `publicada` indica que passou por revisao por pares e esta no acervo.
    Quando `tem_resenha=True`, a analise contem uma resenha critica autoral
    que sera submetida a revisao cega adicional.
    """

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        SUBMETIDA = "submetida", "Submetida para revisão"
        EM_REVISAO = "em_revisao", "Em revisão"
        APROVADA = "aprovada", "Aprovada"
        PUBLICADA = "publicada", "Publicada no acervo"
        LEGADO = "legado", "Legado pré-validado"
        DESPUBLICADA = "despublicada", "Despublicada"

    artigo = models.ForeignKey(
        Artigo,
        on_delete=models.PROTECT,
        related_name="analises",
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="analises",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )

    presenca_titulo = models.BooleanField(null=True, blank=True)
    presenca_resumo = models.BooleanField(null=True, blank=True)
    presenca_palavras_chave = models.BooleanField(null=True, blank=True)
    presenca_referencias = models.BooleanField(null=True, blank=True)
    presenca_corpo = models.BooleanField(null=True, blank=True)

    pertinencia = models.BooleanField(null=True, blank=True)
    aspectos_relevantes = models.TextField(blank=True)
    define_conceito = models.BooleanField(null=True, blank=True)
    definicao_extraida = models.TextField(blank=True)

    objeto = models.TextField(blank=True)
    objetivo = models.TextField(blank=True)
    foco = models.TextField(blank=True)
    metodologia = models.TextField(blank=True)
    epistemologia = models.ManyToManyField(
        TermoVocabulario,
        blank=True,
        related_name="analises_por_epistemologia",
        limit_choices_to={"vocabulario__codigo": "epistemologia"},
    )
    teoria = models.ManyToManyField(
        TermoVocabulario,
        blank=True,
        related_name="analises_por_teoria",
        limit_choices_to={"vocabulario__codigo": "teoria"},
    )
    referenciais = models.TextField(blank=True)
    resultados = models.TextField(blank=True)

    contexto_producao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    resenha_critica = models.TextField(
        blank=True,
        help_text=(
            "Texto critico autoral. Quando preenchido, dispara revisao cega "
            "adicional e ganha selo de destaque."
        ),
    )
    tem_resenha = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Cache para filtros — atualizado automaticamente no save().",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    submetida_em = models.DateTimeField(null=True, blank=True)
    publicada_em = models.DateTimeField(null=True, blank=True)

    # Stamp da ultima edicao feita fora do fluxo normal de rascunho
    # (curador/admin a qualquer tempo, ou autor adicionando resenha pos-publicacao).
    # Para o historico completo, ver django-simple-history (HistoricalAnalise).
    editado_em = models.DateTimeField(null=True, blank=True, db_index=True)
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analises_editadas",
    )

    # Embeddings semânticos (Fase 8) — pgvector
    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text="Embedding dos campos estruturais da análise (Fase 8).",
    )
    embedding_resenha = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text="Embedding da resenha crítica, quando presente (Fase 8).",
    )
    embedding_atualizado_em = models.DateTimeField(null=True, blank=True)

    # Embeddings excluídos do histórico: são dados derivados, não autoria.
    history = HistoricalRecords(excluded_fields=["embedding", "embedding_resenha", "embedding_atualizado_em"])

    class Meta:
        verbose_name = "análise"
        verbose_name_plural = "análises"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["artigo", "analista"],
                name="uniq_analise_por_analista_por_artigo",
            ),
        ]

    def __str__(self) -> str:
        return f"Análise de {self.artigo_id} por {self.analista_id} ({self.status})"

    def save(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.tem_resenha = bool((self.resenha_critica or "").strip())
        super().save(*args, **kwargs)

    JANELA_EDICAO_POS_ENVIO = timedelta(hours=1)

    @property
    def pode_ser_modificada(self) -> bool:
        """
        Autoria pode editar/excluir enquanto:
        - status = `rascunho` (qualquer momento), OU
        - status = `submetida` e dentro da janela de 1h após o envio.

        Após esse período (ou status `em_revisao`/`aprovada`/`publicada`/
        `legado`/`despublicada`), a análise fica congelada para a autoria.
        """
        if self.status == self.Status.RASCUNHO:
            return True
        if self.status == self.Status.SUBMETIDA and self.submetida_em:
            return timezone.now() < self.submetida_em + self.JANELA_EDICAO_POS_ENVIO
        return False

    @property
    def pode_editar_resenha_pos_publicacao(self) -> bool:
        """
        Mesmo apos publicada, a autoria pode adicionar/editar APENAS a resenha
        critica. Salvar a resenha dispara nova revisao cega (status volta para
        `submetida`).
        """
        return self.status in {
            self.Status.APROVADA,
            self.Status.PUBLICADA,
            self.Status.LEGADO,
        }


class Revisao(models.Model):
    """
    Parecer de um par sobre uma Analise.

    Tipo `estrutural`: revisor ve autoria normalmente. Aplicado sempre que
    uma analise eh submetida.

    Tipo `cega`: autoria mascarada na interface do revisor. Aplicado apenas
    quando a analise tem resenha critica autoral.
    """

    class Parecer(models.TextChoices):
        APROVAR = "aprovar", "Aprovar"
        AJUSTES = "ajustes", "Solicitar ajustes"
        REJEITAR = "rejeitar", "Rejeitar"

    class Tipo(models.TextChoices):
        ESTRUTURAL = "estrutural", "Revisão estrutural (análise)"
        CEGA = "cega", "Revisão cega (resenha crítica)"

    analise = models.ForeignKey(
        Analise,
        on_delete=models.CASCADE,
        related_name="revisoes",
    )
    revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="revisoes_feitas",
    )
    tipo = models.CharField(
        max_length=15,
        choices=Tipo.choices,
        default=Tipo.ESTRUTURAL,
        db_index=True,
    )
    parecer = models.CharField(
        max_length=10,
        choices=Parecer.choices,
        null=True,
        blank=True,
    )
    comentario_geral = models.TextField(blank=True)
    sorteado_em = models.DateTimeField(auto_now_add=True)
    prazo_em = models.DateTimeField()
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "revisão"
        verbose_name_plural = "revisões"
        ordering = ["-sorteado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["analise", "revisor", "tipo"],
                name="uniq_revisao_por_revisor_tipo",
            ),
        ]

    def __str__(self) -> str:
        return f"Revisão {self.tipo} de {self.analise_id} por {self.revisor_id}"


class ComentarioRevisao(models.Model):
    """Comentario ancorado a um campo especifico da analise revisada."""

    revisao = models.ForeignKey(
        Revisao,
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    campo = models.CharField(
        max_length=50,
        help_text="Nome do campo da Analise comentado (ex: 'metodologia', 'resenha_critica').",
    )
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comentário de revisão"
        verbose_name_plural = "comentários de revisão"
        ordering = ["criado_em"]

    def __str__(self) -> str:
        return f"Comentário em {self.revisao_id}:{self.campo}"
