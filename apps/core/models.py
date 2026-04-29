"""Modelos do app `core`: usuario customizado e fluxos de cadastro."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Usuario da plataforma.

    Estende AbstractUser para incluir papel (leitor/analista/curador), dados
    institucionais e preferencias de revisao. Email e o identificador real
    (vem do OAuth Google na Fase 2); username permanece por compatibilidade.
    """

    class Papel(models.TextChoices):
        LEITOR = "leitor", "Leitor"
        ANALISTA = "analista", "Analista"
        CURADOR = "curador", "Curador"

    nome_exibicao = models.CharField(max_length=200, blank=True)
    vinculo_institucional = models.CharField(max_length=300, blank=True)
    grupo_pesquisa = models.CharField(max_length=300, blank=True)
    orcid = models.CharField(max_length=19, blank=True)
    papel = models.CharField(
        max_length=10,
        choices=Papel.choices,
        default=Papel.LEITOR,
        db_index=True,
    )
    aceita_revisoes = models.BooleanField(default=True)
    limite_revisoes_simultaneas = models.PositiveSmallIntegerField(default=3)

    eh_legado = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marca contas placeholder criadas pela migracao do legado.",
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["username"]

    def __str__(self) -> str:
        return self.nome_exibicao or self.get_full_name() or self.username

    @property
    def eh_curador(self) -> bool:
        return self.papel == self.Papel.CURADOR

    @property
    def eh_analista(self) -> bool:
        return self.papel in {self.Papel.ANALISTA, self.Papel.CURADOR}


class SolicitacaoCadastro(models.Model):
    """
    Pedido de promocao de leitor para analista.

    Criado apos o cadastro inicial (Fase 2). Curadores aprovam ou rejeitam
    pelo admin; aprovacao muda o papel do usuario para `analista`.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADA = "aprovada", "Aprovada"
        REJEITADA = "rejeitada", "Rejeitada"

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="solicitacao_cadastro",
    )
    justificativa = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    revisado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitacoes_revisadas",
    )
    revisado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    motivo_rejeicao = models.TextField(blank=True)

    class Meta:
        verbose_name = "solicitação de cadastro"
        verbose_name_plural = "solicitações de cadastro"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"Solicitação de {self.usuario} ({self.get_status_display()})"
