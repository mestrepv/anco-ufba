"""Modelos do módulo **Revisão ANCO** (análise cognitiva).

Independente do PRISMA-ScR (`apps/triagem`). A epistemologia é outra: permissiva,
multirreferencial, **sem triagem** — tudo que se importa entra no corpus, e a
análise (Matriz AnCo) é distribuída por sorteio. O acervo (`apps/acervo`) é o
destino comum e nunca é alterado por aqui.

`related_name` sempre com sufixo `_anco` para coexistir com `apps/triagem`
durante a transição (mesmos `User`/`Artigo`/`Analise`).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ProjetoANCO(models.Model):
    """Projeto de Revisão ANCO — uma revisão de análise cognitiva."""

    nome = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    pergunta_pesquisa = models.TextField(blank=True, help_text="Objetivo da revisão.")
    estrategia_busca = models.TextField(blank=True)
    arquivado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "projeto ANCO"
        verbose_name_plural = "projetos ANCO"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if not self.slug:
            base = slugify(self.nome or "projeto") or "projeto"
            slug, i = base, 2
            while ProjetoANCO.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @classmethod
    def ativo(cls) -> ProjetoANCO | None:
        return (
            cls.objects.filter(arquivado=False).order_by("id").first()
            or cls.objects.order_by("id").first()
        )

    def papel_de(self, user) -> str | None:
        if user is None or not user.is_authenticated:
            return None
        m = self.membros.filter(usuario=user).first()
        return m.papel if m else None

    def eh_membro(self, user) -> bool:
        return self.papel_de(user) is not None

    def eh_curador_no(self, user) -> bool:
        if user is not None and getattr(user, "is_staff", False):
            return True
        return self.papel_de(user) == MembroANCO.Papel.CURADOR


class MembroANCO(models.Model):
    """Vínculo de um usuário a um projeto ANCO, com papel no projeto."""

    class Papel(models.TextChoices):
        ANALISTA = "analista", "Analista"
        CURADOR = "curador", "Curador"

    projeto = models.ForeignKey(ProjetoANCO, on_delete=models.CASCADE, related_name="membros")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projetos_anco"
    )
    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.ANALISTA)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membro do projeto ANCO"
        verbose_name_plural = "membros do projeto ANCO"
        ordering = ["projeto", "usuario"]
        constraints = [
            models.UniqueConstraint(fields=["projeto", "usuario"], name="uniq_membro_anco"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario_id} em {self.projeto_id} ({self.papel})"


class FonteImport(models.Model):
    """Uma importação de lista bibliográfica para um projeto ANCO."""

    class Formato(models.TextChoices):
        RIS = "ris", "RIS"
        BIBTEX = "bibtex", "BibTeX"
        CSV = "csv", "CSV"

    projeto = models.ForeignKey(ProjetoANCO, on_delete=models.CASCADE, related_name="fontes")
    base_consulta = models.ForeignKey(
        "vocabulario.TermoVocabulario",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fontes_anco",
        limit_choices_to={"vocabulario__codigo": "base"},
        help_text="Base bibliográfica (reusa o vocabulário `base`).",
    )
    outra_base = models.CharField(max_length=200, blank=True)
    string_busca = models.TextField(blank=True)
    data_busca = models.DateField(null=True, blank=True)
    formato = models.CharField(max_length=10, choices=Formato.choices, blank=True)
    arquivo = models.FileField(upload_to="anco/fontes/", null=True, blank=True)
    n_lidos = models.PositiveIntegerField(default=0)
    n_novos = models.PositiveIntegerField(default=0)
    n_duplicados = models.PositiveIntegerField(default=0)
    n_ignorados = models.PositiveIntegerField(default=0)
    importado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fontes_anco",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "fonte (import) ANCO"
        verbose_name_plural = "fontes (imports) ANCO"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Fonte {self.base_nome or '?'} ({self.criado_em:%Y-%m-%d})"

    @property
    def base_nome(self) -> str:
        return self.base_consulta.nome if self.base_consulta else self.outra_base


class ItemCorpus(models.Model):
    """Item do corpus ANCO. Todo registro importado entra aqui — **sem triagem**.

    Promovido/vinculado a um `acervo.Artigo` na importação; analisado pela Matriz
    AnCo (via `apps/acervo`). Pode ser removido do corpus pelo curador/importador.
    """

    projeto = models.ForeignKey(ProjetoANCO, on_delete=models.CASCADE, related_name="itens")
    titulo = models.TextField()
    autores = models.TextField(blank=True)
    ano = models.PositiveSmallIntegerField(null=True, blank=True)
    doi = models.CharField(max_length=255, blank=True)
    isbn = models.CharField(max_length=40, blank=True)
    resumo = models.TextField(blank=True)
    palavras_chaves = models.TextField(blank=True)
    titulo_periodico = models.CharField(max_length=300, blank=True)
    idioma = models.CharField(max_length=20, blank=True)
    link = models.CharField(max_length=600, blank=True)
    tipo = models.CharField(max_length=40, blank=True)
    identificador = models.CharField(
        max_length=64, db_index=True, help_text="Chave de deduplicação interna."
    )
    origem_fontes = models.ManyToManyField(FonteImport, related_name="itens", blank=True)
    artigo = models.ForeignKey(
        "acervo.Artigo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_anco",
        help_text="Artigo no acervo (promovido/vinculado).",
    )
    removido = models.BooleanField(default=False)
    removido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_anco_removidos",
    )
    removido_em = models.DateTimeField(null=True, blank=True)
    motivo_remocao = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "item do corpus"
        verbose_name_plural = "itens do corpus"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["projeto", "identificador"], name="uniq_item_anco_por_projeto"
            ),
        ]

    def __str__(self) -> str:
        return self.titulo[:80]


class SorteioANCO(models.Model):
    """Distribuição da análise (Matriz AnCo) entre os analistas — por cota."""

    class ModoRevisao(models.TextChoices):
        UNICA = "unica", "Revisão única (1 analista)"
        DUPLA = "dupla", "Revisão dupla (2 analistas + consenso)"

    projeto = models.ForeignKey(ProjetoANCO, on_delete=models.CASCADE, related_name="sorteios")
    modo_revisao = models.CharField(
        max_length=10, choices=ModoRevisao.choices, default=ModoRevisao.UNICA
    )
    cota = models.PositiveSmallIntegerField(default=5)
    semente = models.BigIntegerField(
        null=True, blank=True, help_text="Seed do embaralhamento (reprodutível/auditável)."
    )
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sorteios_anco",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sorteio de análise (ANCO)"
        verbose_name_plural = "sorteios de análise (ANCO)"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Sorteio {self.pk} — projeto {self.projeto_id}"

    @property
    def assentos_por_artigo(self) -> int:
        return 2 if self.modo_revisao == self.ModoRevisao.DUPLA else 1


class AtribuicaoANCO(models.Model):
    """Um artigo atribuído a um analista por um sorteio ANCO."""

    sorteio = models.ForeignKey(SorteioANCO, on_delete=models.CASCADE, related_name="atribuicoes")
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="atribuicoes_anco"
    )
    artigo = models.ForeignKey(
        "acervo.Artigo", on_delete=models.CASCADE, related_name="atribuicoes_anco"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "atribuição de análise (ANCO)"
        verbose_name_plural = "atribuições de análise (ANCO)"
        ordering = ["sorteio", "analista", "artigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["sorteio", "analista", "artigo"], name="uniq_atribuicao_anco"
            ),
        ]
        indexes = [models.Index(fields=["analista", "artigo"])]

    def __str__(self) -> str:
        return f"Artigo {self.artigo_id} → analista {self.analista_id}"


class ConsensoANCO(models.Model):
    """Conciliação da revisão dupla: duas análises independentes → uma final."""

    projeto = models.ForeignKey(ProjetoANCO, on_delete=models.CASCADE, related_name="consensos")
    artigo = models.ForeignKey(
        "acervo.Artigo", on_delete=models.CASCADE, related_name="consensos_anco"
    )
    sorteio = models.ForeignKey(
        SorteioANCO, on_delete=models.SET_NULL, null=True, blank=True, related_name="consensos"
    )
    analises = models.ManyToManyField(
        "acervo.Analise", blank=True, related_name="consensos_anco_origem"
    )
    analise_final = models.ForeignKey(
        "acervo.Analise",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consenso_anco_final",
    )
    conciliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consensos_anco",
    )
    conciliado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consenso de análise (ANCO)"
        verbose_name_plural = "consensos de análise (ANCO)"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Consenso artigo {self.artigo_id} — projeto {self.projeto_id}"
