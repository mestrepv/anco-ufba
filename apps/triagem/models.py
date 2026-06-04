"""Modelos da triagem PRISMA-ScR (Fase 9).

App **aditivo**: tabelas novas, sem alterar o schema de `acervo`. O vínculo de
proveniência (triagem → acervo) mora aqui, em `RegistroTriagem.artigo`.

Fluxo: `Busca` (por base) → `RegistroTriagem` (candidato pré-`Artigo`) →
`DecisaoTriagem` (parecer de ≥2 revisores) → inclusão/exclusão → promoção a
`Artigo` (só os incluídos). O `ProtocoloTriagem` (singleton) guarda critérios e
parâmetros (nº de revisores, prazo).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from simple_history.models import HistoricalRecords

from apps.acervo.models import _gerar_identificador_interno
from apps.vocabulario.models import TermoVocabulario


def chave_dedup(
    doi: str | None, isbn: str | None, titulo: str, ano: int | None, periodico: str
) -> str:
    """
    Chave determinística de deduplicação, espelhando `Artigo`:
    DOI normalizado > ISBN > hash(título|ano|periódico).
    Mesmos campos → mesma chave (idempotente). Usada como `identificador`
    único do registro dentro do protocolo.
    """
    doi_norm = (doi or "").strip().lower()
    if doi_norm:
        return f"doi:{doi_norm}"
    isbn_norm = (isbn or "").strip().replace("-", "").replace(" ", "")
    if isbn_norm:
        return f"isbn:{isbn_norm}"
    return _gerar_identificador_interno(titulo, ano, periodico)


class ProtocoloTriagem(models.Model):
    """Protocolo da revisão de escopo (singleton). Critérios e parâmetros."""

    titulo = models.CharField(
        max_length=300, default="Revisão de escopo — Análise Cognitiva"
    )
    pergunta_pesquisa = models.TextField(blank=True)
    criterios_inclusao = models.TextField(
        blank=True, help_text="Critérios de inclusão pré-registrados (PRISMA-ScR)."
    )
    criterios_exclusao = models.TextField(
        blank=True, help_text="Critérios de exclusão pré-registrados (PRISMA-ScR)."
    )
    n_revisores = models.PositiveSmallIntegerField(
        default=2, help_text="Revisores independentes por registro (≥2)."
    )
    prazo_dias = models.PositiveSmallIntegerField(
        default=21, help_text="Prazo (dias) para concluir cada triagem."
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "protocolo de triagem"
        verbose_name_plural = "protocolos de triagem"

    def __str__(self) -> str:
        return self.titulo

    @classmethod
    def ativo(cls) -> ProtocoloTriagem:
        """Retorna o protocolo único (cria com padrões se não existir)."""
        obj = cls.objects.order_by("id").first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class Busca(models.Model):
    """Uma busca em uma base — etapa de *identification* do PRISMA."""

    class Formato(models.TextChoices):
        RIS = "ris", "RIS"
        BIBTEX = "bibtex", "BibTeX"
        CSV = "csv", "CSV"

    class CampoBusca(models.TextChoices):
        TOPICO = "topico", "Tópico"
        TITULO = "titulo", "Título"
        RESUMO = "resumo", "Resumo"
        PALAVRAS_CHAVE = "palavras_chave", "Palavras-chave"
        TODOS = "todos", "Todos os campos"

    class TipoDocumento(models.TextChoices):
        ARTIGO = "artigo", "Artigo"
        REVISAO = "revisao", "Revisão"
        CAPITULO = "capitulo", "Capítulo de livro"
        EVENTO = "evento", "Trabalho de evento"
        TESE = "tese_dissertacao", "Tese/Dissertação"
        OUTRO = "outro", "Outro"

    protocolo = models.ForeignKey(
        ProtocoloTriagem, on_delete=models.CASCADE, related_name="buscas"
    )
    base_consulta = models.ForeignKey(
        TermoVocabulario,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="buscas_triagem",
        limit_choices_to={"vocabulario__codigo": "base"},
        help_text="Base bibliográfica (reusa o vocabulário `base`).",
    )
    outra_base = models.CharField(
        max_length=200, blank=True, help_text="Base fora do vocabulário controlado."
    )
    string_busca = models.TextField(
        blank=True, help_text="String de busca usada (para reprodutibilidade)."
    )
    # Filtros estruturados (reprodutibilidade PRISMA, minimiza erro de registro).
    ano_inicio = models.PositiveSmallIntegerField(null=True, blank=True)
    ano_fim = models.PositiveSmallIntegerField(null=True, blank=True)
    idiomas = ArrayField(
        models.CharField(max_length=10), default=list, blank=True,
        help_text="Idiomas filtrados na base.",
    )
    idioma_outro = models.CharField(
        max_length=100, blank=True,
        help_text="Especificação quando 'Outro' é escolhido em idiomas.",
    )
    tipos_documento = ArrayField(
        models.CharField(max_length=20), default=list, blank=True,
        help_text="Tipos de documento filtrados na base.",
    )
    campos_busca = ArrayField(
        models.CharField(max_length=20), default=list, blank=True,
        help_text="Em que campo(s) a query foi aplicada.",
    )
    filtros = models.TextField(
        blank=True,
        help_text="Outros filtros/limites não cobertos pelos campos acima.",
    )
    data_busca = models.DateField(null=True, blank=True)
    n_identificados = models.PositiveIntegerField(
        default=0, help_text="Total de registros relatado pela base (para o PRISMA)."
    )
    # Resultado da importação deste arquivo (preenchido em importar_para_busca).
    n_lidos = models.PositiveIntegerField(default=0)
    n_novos = models.PositiveIntegerField(default=0)
    n_duplicados = models.PositiveIntegerField(default=0)
    n_ja_no_acervo = models.PositiveIntegerField(default=0)
    n_ignorados = models.PositiveIntegerField(default=0)
    importado_em = models.DateTimeField(null=True, blank=True)
    arquivo = models.FileField(
        upload_to="triagem/buscas/", null=True, blank=True,
        help_text="Export cru (RIS/BibTeX/CSV), guardado para auditoria.",
    )
    formato = models.CharField(max_length=10, choices=Formato.choices, blank=True)
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buscas_triagem",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "busca"
        verbose_name_plural = "buscas"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Busca em {self.base_nome or 'base não informada'} ({self.criado_em:%Y-%m-%d})"

    @property
    def base_nome(self) -> str:
        return self.base_consulta.nome if self.base_consulta else self.outra_base

    @property
    def periodo(self) -> str:
        if self.ano_inicio and self.ano_fim:
            return f"{self.ano_inicio}–{self.ano_fim}"
        return str(self.ano_inicio or self.ano_fim or "")

    @property
    def idiomas_display(self) -> str:
        from apps.acervo.models import Artigo

        mapa = dict(Artigo.Idioma.choices)
        nomes = []
        for i in self.idiomas:
            if i == "outro" and self.idioma_outro:
                nomes.append(f"Outro ({self.idioma_outro})")
            else:
                nomes.append(mapa.get(i, i))
        return ", ".join(nomes)

    @property
    def tipos_documento_display(self) -> str:
        mapa = dict(self.TipoDocumento.choices)
        return ", ".join(mapa.get(t, t) for t in self.tipos_documento)

    @property
    def campos_busca_display(self) -> str:
        mapa = dict(self.CampoBusca.choices)
        return ", ".join(mapa.get(c, c) for c in self.campos_busca)


class RegistroTriagem(models.Model):
    """Candidato bibliográfico (pré-`Artigo`) sob triagem."""

    class Status(models.TextChoices):
        IDENTIFICADO = "identificado", "Identificado"
        EM_TRIAGEM = "em_triagem", "Em triagem"
        INCLUIDO = "incluido", "Incluído"
        EXCLUIDO = "excluido", "Excluído"
        DUPLICADO = "duplicado", "Duplicado"

    class Decisao(models.TextChoices):
        INCLUIR = "incluir", "Incluir"
        EXCLUIR = "excluir", "Excluir"
        DUVIDA = "duvida", "Em dúvida"

    # Status que aguardam ou já passaram pela triagem por pares.
    EM_ABERTO = (Status.IDENTIFICADO, Status.EM_TRIAGEM)
    TRIADOS = (Status.INCLUIDO, Status.EXCLUIDO)

    protocolo = models.ForeignKey(
        ProtocoloTriagem, on_delete=models.CASCADE, related_name="registros"
    )
    origem_buscas = models.ManyToManyField(
        Busca, blank=True, related_name="registros",
        help_text="Buscas em que este registro apareceu (uma ou mais bases).",
    )

    # Campos bibliográficos (espelham os importáveis de `Artigo`).
    titulo = models.TextField()
    autores = models.TextField(blank=True)
    ano = models.IntegerField(null=True, blank=True)
    doi = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=17, blank=True)
    resumo = models.TextField(blank=True)
    palavras_chaves = models.TextField(blank=True)
    titulo_periodico = models.TextField(blank=True)
    idioma = models.CharField(max_length=20, blank=True)
    link = models.URLField(max_length=600, blank=True)

    identificador = models.CharField(
        max_length=80, db_index=True,
        help_text="Chave determinística de dedup (DOI>ISBN>hash).",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.IDENTIFICADO, db_index=True
    )
    motivo_exclusao = models.TextField(
        blank=True, help_text="Motivo da exclusão (PRISMA: excluded with reasons)."
    )
    duplicado_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="duplicatas"
    )
    ja_no_acervo = models.BooleanField(
        default=False, db_index=True,
        help_text="Casa com Artigo já existente (inclusive legado): não re-triar.",
    )
    artigo = models.ForeignKey(
        "acervo.Artigo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_triagem",
        help_text="Artigo correspondente: por promoção (incluído) ou por casar com o acervo.",
    )
    decisao_final = models.CharField(
        max_length=10, choices=Decisao.choices, blank=True,
        help_text="Decisão consolidada (consenso ou desempate).",
    )
    decidida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triagens_decididas",
    )
    decidida_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "registro de triagem"
        verbose_name_plural = "registros de triagem"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["protocolo", "identificador"],
                name="uniq_registro_por_identificador_protocolo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titulo[:80]} ({self.status})"

    def save(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if not self.identificador:
            self.identificador = chave_dedup(
                self.doi, self.isbn, self.titulo, self.ano, self.titulo_periodico
            )
        super().save(*args, **kwargs)


class DecisaoTriagem(models.Model):
    """Parecer de triagem de um revisor (análogo a `acervo.Revisao`)."""

    registro = models.ForeignKey(
        RegistroTriagem, on_delete=models.CASCADE, related_name="decisoes"
    )
    revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="triagens_feitas"
    )
    decisao = models.CharField(
        max_length=10, choices=RegistroTriagem.Decisao.choices, null=True, blank=True
    )
    motivo_exclusao = models.TextField(blank=True)
    comentario = models.TextField(blank=True)
    sorteado_em = models.DateTimeField(auto_now_add=True)
    prazo_em = models.DateTimeField()
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "decisão de triagem"
        verbose_name_plural = "decisões de triagem"
        ordering = ["-sorteado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["registro", "revisor"],
                name="uniq_decisao_por_revisor_registro",
            ),
        ]

    def __str__(self) -> str:
        return f"Triagem do registro {self.registro_id} por {self.revisor_id}"


class ParDuplicataDescartado(models.Model):
    """Par de registros que um humano marcou como **não** sendo duplicatas.

    Evita reexibir o par na revisão de "possíveis duplicatas". Convenção:
    `registro_a_id < registro_b_id`.
    """

    registro_a = models.ForeignKey(
        RegistroTriagem, on_delete=models.CASCADE, related_name="+"
    )
    registro_b = models.ForeignKey(
        RegistroTriagem, on_delete=models.CASCADE, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "par descartado (não duplicata)"
        verbose_name_plural = "pares descartados (não duplicatas)"
        constraints = [
            models.UniqueConstraint(
                fields=["registro_a", "registro_b"], name="uniq_par_descartado"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.registro_a_id} ≠ {self.registro_b_id}"
