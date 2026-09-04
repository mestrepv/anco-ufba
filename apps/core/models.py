"""Modelos do app `core`: usuario customizado e fluxos de cadastro."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class UserQuerySet(models.QuerySet["User"]):
    def equipe_publica(self) -> models.QuerySet[User]:
        """
        Quem aparece no diretorio publico `/equipe` e nas contagens da home.

        Definicao unica: e' preciso ter papel de analista ou curador, estar
        ativo, ter perfil minimo preenchido (nome e vinculo) e ser uma pessoa
        real da equipe — contas do legado e contas de servico ficam fora.
        """
        return (
            self.filter(
                papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
                is_active=True,
                eh_legado=False,
                eh_conta_servico=False,
            )
            .exclude(nome_exibicao="")
            .exclude(vinculo_institucional="")
        )


class UserManager(DjangoUserManager["User"].from_queryset(UserQuerySet)):  # type: ignore[misc]
    """Manager do User com o queryset da equipe publica."""


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

    class Titulacao(models.TextChoices):
        GRADUANDO = "graduando", "Graduando"
        GRADUADO = "graduado", "Graduado"
        MESTRANDO = "mestrando", "Mestrando"
        MESTRE = "mestre", "Mestre"
        DOUTORANDO = "doutorando", "Doutorando"
        DOUTOR = "doutor", "Doutor"
        POS_DOC = "pos_doc", "Pós-doutorado"
        PROFESSOR = "professor", "Professor"

    # ----- identidade -----
    nome_exibicao = models.CharField(max_length=200, blank=True)
    foto = models.ImageField(
        upload_to="usuarios/fotos/",
        blank=True,
        null=True,
        help_text="Foto de perfil. Se vazia, usa a foto do Google ou iniciais.",
    )

    # ----- vinculo institucional -----
    vinculo_institucional = models.CharField(
        max_length=300, blank=True, help_text="Instituição principal (ex: IFBA)."
    )
    unidade_departamento = models.CharField(
        max_length=300, blank=True, help_text="Unidade/departamento/programa (ex: DMMDC)."
    )
    grupo_pesquisa = models.CharField(max_length=300, blank=True)
    cargo = models.CharField(
        max_length=150, blank=True, help_text="Cargo/posição (ex: Professor titular)."
    )

    # ----- formacao -----
    titulacao = models.CharField(
        max_length=15,
        choices=Titulacao.choices,
        blank=True,
        db_index=True,
    )
    programa_pos = models.CharField(
        max_length=200, blank=True, help_text="Programa de pós-graduação quando aplicável."
    )
    orientador = models.CharField(
        max_length=200, blank=True, help_text="Orientador(a) — para mestrandos/doutorandos."
    )

    # ----- pesquisa -----
    bio_curta = models.CharField(
        max_length=280,
        blank=True,
        help_text="Apresentação curta (até 280 caracteres).",
    )
    areas_interesse = models.TextField(
        blank=True,
        help_text="Áreas de interesse separadas por ponto-e-vírgula.",
    )
    linhas_pesquisa = models.TextField(blank=True, help_text="Linhas de pesquisa (texto livre).")

    # ----- identificadores academicos -----
    orcid = models.CharField(max_length=19, blank=True)
    lattes_url = models.URLField(max_length=300, blank=True)
    linkedin_url = models.URLField(max_length=300, blank=True)
    pagina_pessoal_url = models.URLField(max_length=300, blank=True)

    # ----- papel + preferencias -----
    papel = models.CharField(
        max_length=10,
        choices=Papel.choices,
        default=Papel.LEITOR,
        db_index=True,
    )
    # Disponibilidade para revisões. Só tem efeito se também `revisor_aprovado=True`
    # (a aprovação é feita pela curadoria via SolicitacaoCadastro tipo=revisor).
    aceita_revisoes = models.BooleanField(default=True)
    revisor_aprovado = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marcado pela aprovação de uma SolicitacaoCadastro tipo=revisor.",
    )
    limite_revisoes_simultaneas = models.PositiveSmallIntegerField(default=3)

    eh_legado = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marca contas placeholder criadas pela migracao do legado.",
    )
    eh_conta_servico = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="conta de serviço",
        help_text=(
            "Conta administrativa ou de teste, nao pertencente a equipe de "
            "pesquisa. Fica fora do diretorio publico e das contagens."
        ),
    )

    # Acesso por módulo (separação ANCO × PRISMA). Camada global: settings
    # PRISMA_ATIVO / ANCO_ATIVO; camada por usuário: estes campos (UserAdmin).
    pode_prisma = models.BooleanField(
        default=True, help_text="Acessa o módulo de Revisão de escopo (PRISMA-ScR)."
    )
    pode_anco = models.BooleanField(
        default=False, help_text="Acessa o módulo de Revisão ANCO (Análise Cognitiva)."
    )

    objects = UserManager()

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

    @property
    def pode_revisar(self) -> bool:
        """Recebe revisões: precisa ser analista, ter aprovação e estar disponível."""
        return self.eh_analista and self.revisor_aprovado and self.aceita_revisoes

    def acessa_prisma(self) -> bool:
        """Pode usar o módulo PRISMA-ScR (global ligado + permissão; admin sempre)."""
        from django.conf import settings

        return getattr(settings, "PRISMA_ATIVO", True) and (self.is_staff or self.pode_prisma)

    def acessa_anco(self) -> bool:
        """Pode usar o módulo Revisão ANCO (global ligado + permissão; admin sempre)."""
        from django.conf import settings

        return getattr(settings, "ANCO_ATIVO", False) and (self.is_staff or self.pode_anco)

    @property
    def perfil_completo_minimo(self) -> bool:
        """
        Mínimo para sair do onboarding e aparecer no diretório:
        nome de exibição + instituição preenchidos.
        """
        return bool(self.nome_exibicao.strip() and self.vinculo_institucional.strip())

    def delete(self, *args, **kwargs):
        """
        Apagar User reatribui análises/revisões à Equipe AnCo antes da
        deleção (libera as FKs PROTECT do collector). Implementado aqui,
        no model, porque pre_delete dispara DEPOIS do Collector — tarde demais.
        """
        # Import local: signals.py depende de models indiretamente
        from .signals import reatribuir_trabalho_antes_de_apagar_user

        reatribuir_trabalho_antes_de_apagar_user(self)
        return super().delete(*args, **kwargs)

    @property
    def iniciais(self) -> str:
        """Iniciais (1-2 letras) usadas no fallback do avatar."""
        nome = self.nome_exibicao or self.get_full_name() or self.email or self.username
        partes = [p for p in nome.replace(".", " ").split() if p]
        if not partes:
            return "?"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[-1][0]).upper()


class SolicitacaoCadastro(models.Model):
    """
    Pedido de promoção a papel ativo no acervo (analista) ou habilitação
    como revisor por pares (revisor). Curadores aprovam/rejeitam via admin.

    Um usuário pode ter no máximo 1 solicitação **ativa** (pendente|aprovada)
    por tipo. Solicitações rejeitadas viram histórico e podem ser refeitas.
    """

    class Tipo(models.TextChoices):
        ANALISTA = "analista", "Analista"
        REVISOR = "revisor", "Revisor"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADA = "aprovada", "Aprovada"
        REJEITADA = "rejeitada", "Rejeitada"

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="solicitacoes",
    )
    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
        default=Tipo.ANALISTA,
        db_index=True,
    )
    justificativa = models.TextField(blank=True)
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
        constraints = [
            # No máximo 1 solicitação ativa (não rejeitada) por (user, tipo).
            models.UniqueConstraint(
                fields=["usuario", "tipo"],
                condition=~models.Q(status="rejeitada"),
                name="uniq_solicitacao_ativa_por_tipo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.usuario} ({self.get_status_display()})"
