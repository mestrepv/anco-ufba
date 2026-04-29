"""Modelos do vocabulario controlado.

Resolve o "Empirismo" vs "empirismo" vs "Empírica" da base legada,
mantendo termos canonicos com sinonimos para deduplicacao.
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.text import slugify


class Vocabulario(models.Model):
    """Conjunto canonico de termos para um campo (epistemologia, base, ...)."""

    codigo = models.SlugField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "vocabulário"
        verbose_name_plural = "vocabulários"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class TermoVocabulario(models.Model):
    """
    Termo dentro de um Vocabulario.

    `sinonimos` armazena variantes que devem ser fundidas a este termo durante
    a importacao (ex: ['empirismo', 'Empírica', 'empirista'] -> 'Empirismo').
    Termos com `ativo=False` foram criados pela importacao do legado e
    aguardam revisao/curadoria — nao aparecem nos formularios novos.
    """

    vocabulario = models.ForeignKey(
        Vocabulario,
        on_delete=models.CASCADE,
        related_name="termos",
    )
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    sinonimos = ArrayField(
        models.CharField(max_length=200),
        default=list,
        blank=True,
    )
    ativo = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Termos inativos nao aparecem em formularios; usar para itens do legado pendentes de curadoria.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "termo do vocabulário"
        verbose_name_plural = "termos do vocabulário"
        ordering = ["vocabulario__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["vocabulario", "nome"],
                name="uniq_termo_por_vocabulario",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.vocabulario.codigo}:{self.nome}"

    @classmethod
    def buscar_canonico(cls, vocabulario_codigo: str, valor: str) -> TermoVocabulario | None:
        """Procura termo canonico cujo `nome` ou `sinonimos` case com `valor` (case-insensitive)."""
        valor_norm = (valor or "").strip()
        if not valor_norm:
            return None
        valor_lower = valor_norm.lower()
        # match por nome canonico (case-insensitive)
        termo = cls.objects.filter(
            vocabulario__codigo=vocabulario_codigo,
            nome__iexact=valor_norm,
        ).first()
        if termo:
            return termo
        # match por sinonimos (qualquer item do array, case-insensitive)
        for t in cls.objects.filter(vocabulario__codigo=vocabulario_codigo).only(
            "id", "nome", "sinonimos"
        ):
            for sin in t.sinonimos or []:
                if sin.strip().lower() == valor_lower:
                    return t
        return None

    @classmethod
    def slug_para_vocabulario(cls, nome: str) -> str:
        return slugify(nome)[:50]
