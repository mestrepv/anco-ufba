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
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.utils.text import slugify
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
    """Projeto de revisão de escopo: critérios, parâmetros e equipe.

    Cada projeto é uma revisão independente (pergunta/estratégia próprias), com seu
    corpus, dedup, triagem, PRISMA e concordância. Acervo (`Artigo`) e análise são
    globais. Fase 12.
    """

    titulo = models.CharField(max_length=300, default="Revisão de escopo — Análise Cognitiva")
    nome = models.CharField(
        max_length=120, blank=True, help_text="Nome curto do projeto (para a interface)."
    )
    slug = models.SlugField(
        max_length=140,
        unique=True,
        blank=True,
        help_text="Identificador do projeto na URL (/triagem/p/<slug>/).",
    )
    estrategia_busca = models.TextField(
        blank=True,
        help_text="String/lógica de busca que define a revisão (ex.: BLOCO 1 AND BLOCO 2).",
    )
    arquivado = models.BooleanField(
        default=False, help_text="Projeto concluído: some dos seletores, sem ser apagado."
    )
    pergunta_pesquisa = models.TextField(blank=True)
    criterios_inclusao = models.TextField(
        blank=True, help_text="Critérios de inclusão pré-registrados (PRISMA-ScR)."
    )
    criterios_exclusao = models.TextField(
        blank=True, help_text="Critérios de exclusão pré-registrados (PRISMA-ScR)."
    )
    termos_realce = models.TextField(
        blank=True,
        help_text="Termos destacados no título/resumo durante a triagem (separados por vírgula).",
    )
    n_revisores = models.PositiveSmallIntegerField(
        default=2, help_text="Revisores independentes por registro (≥2)."
    )
    prazo_dias = models.PositiveSmallIntegerField(
        default=21, help_text="Prazo (dias) para concluir cada triagem."
    )
    usa_texto_completo = models.BooleanField(
        default=False,
        help_text="Ativa a 2ª etapa de triagem (texto completo) após o título/resumo.",
    )

    registro_externo = models.URLField(
        max_length=300,
        blank=True,
        help_text="Registro público do protocolo (ex.: OSF) — a priori.",
    )
    versao = models.PositiveSmallIntegerField(default=1)
    travado_em = models.DateTimeField(
        null=True, blank=True, help_text="Quando esta versão foi travada (a priori)."
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "protocolo de triagem"
        verbose_name_plural = "protocolos de triagem"

    def __str__(self) -> str:
        return self.nome or self.titulo

    def save(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if not self.slug:
            base = slugify(self.nome or self.titulo or "projeto") or "projeto"
            slug, i = base, 2
            while ProtocoloTriagem.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @classmethod
    def ativo(cls) -> ProtocoloTriagem:
        """Retorna o protocolo único (cria com padrões se não existir).

        Transição (Fase 12): enquanto a navegação por projeto não substitui todos
        os pontos de uso, `ativo()` devolve o primeiro projeto não arquivado.
        """
        obj = cls.objects.filter(arquivado=False).order_by("id").first()
        if obj is None:
            obj = cls.objects.order_by("id").first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def papel_de(self, user) -> str | None:
        """Papel do usuário NESTE projeto (ou None se não for membro)."""
        if user is None or not user.is_authenticated:
            return None
        m = self.membros.filter(usuario=user).first()
        return m.papel if m else None

    def eh_membro(self, user) -> bool:
        return self.papel_de(user) is not None

    def eh_curador_no(self, user) -> bool:
        """Curador do projeto (ou admin global)."""
        if user is not None and getattr(user, "is_staff", False):
            return True
        return self.papel_de(user) == ProjetoMembro.Papel.CURADOR

    def snapshot_dados(self) -> dict:
        return {
            "titulo": self.titulo,
            "pergunta_pesquisa": self.pergunta_pesquisa,
            "criterios_inclusao": self.criterios_inclusao,
            "criterios_exclusao": self.criterios_exclusao,
            "n_revisores": self.n_revisores,
            "prazo_dias": self.prazo_dias,
            "usa_texto_completo": self.usa_texto_completo,
            "termos_realce": self.termos_realce,
            "registro_externo": self.registro_externo,
        }

    def travar(self, user) -> None:
        """Congela a versão atual (a priori) num snapshot e marca travado_em."""
        from django.utils import timezone

        SnapshotProtocolo.objects.get_or_create(
            protocolo=self,
            versao=self.versao,
            defaults={"dados": self.snapshot_dados(), "travado_por": user},
        )
        self.travado_em = timezone.now()
        self.save(update_fields=["travado_em"])

    def abrir_nova_versao(self) -> None:
        """Destrava para edição como uma nova versão."""
        self.versao += 1
        self.travado_em = None
        self.save(update_fields=["versao", "travado_em"])


class SnapshotProtocolo(models.Model):
    """Versão congelada do protocolo (auditável; a priori)."""

    protocolo = models.ForeignKey(
        ProtocoloTriagem, on_delete=models.CASCADE, related_name="versoes"
    )
    versao = models.PositiveSmallIntegerField()
    dados = models.JSONField(default=dict)
    travado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "versão do protocolo"
        verbose_name_plural = "versões do protocolo"
        ordering = ["-versao"]
        constraints = [
            models.UniqueConstraint(
                fields=["protocolo", "versao"], name="uniq_versao_por_protocolo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.protocolo_id} v{self.versao}"


class ProjetoMembro(models.Model):
    """Vínculo de um usuário a um projeto, com papel **no projeto** (Fase 12).

    O papel global de `User` rege o acesso à plataforma; este papel rege as ações
    da triagem do projeto. Alguém pode ser curador de um projeto e analista de outro.
    """

    class Papel(models.TextChoices):
        ANALISTA = "analista", "Analista"
        CURADOR = "curador", "Curador"

    projeto = models.ForeignKey(ProtocoloTriagem, on_delete=models.CASCADE, related_name="membros")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projetos_triagem"
    )
    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.ANALISTA)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membro do projeto"
        verbose_name_plural = "membros do projeto"
        ordering = ["projeto", "usuario"]
        constraints = [
            models.UniqueConstraint(fields=["projeto", "usuario"], name="uniq_membro_por_projeto"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario_id} em {self.projeto_id} ({self.papel})"


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

    protocolo = models.ForeignKey(ProtocoloTriagem, on_delete=models.CASCADE, related_name="buscas")
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
        models.CharField(max_length=10),
        default=list,
        blank=True,
        help_text="Idiomas filtrados na base.",
    )
    idioma_outro = models.CharField(
        max_length=100,
        blank=True,
        help_text="Especificação quando 'Outro' é escolhido em idiomas.",
    )
    tipos_documento = ArrayField(
        models.CharField(max_length=20),
        default=list,
        blank=True,
        help_text="Tipos de documento filtrados na base.",
    )
    campos_busca = ArrayField(
        models.CharField(max_length=20),
        default=list,
        blank=True,
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
        upload_to="triagem/buscas/",
        null=True,
        blank=True,
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
        EM_TRIAGEM = "em_triagem", "Em triagem (título/resumo)"
        INCLUIDO_TA = "incluido_ta", "Incluído no título/resumo"
        EM_TEXTO = "em_texto", "Em triagem (texto completo)"
        INCLUIDO = "incluido", "Incluído"
        EXCLUIDO = "excluido", "Excluído (título/resumo)"
        EXCLUIDO_TC = "excluido_tc", "Excluído (texto completo)"
        DUPLICADO = "duplicado", "Duplicado"

    class Decisao(models.TextChoices):
        INCLUIR = "incluir", "Incluir"
        EXCLUIR = "excluir", "Excluir"
        DUVIDA = "duvida", "Em dúvida"

    # Status que aguardam ou já passaram pela triagem por pares.
    EM_ABERTO = (Status.IDENTIFICADO, Status.EM_TRIAGEM)
    # Status terminais de uma decisão consolidada (consenso ou desempate).
    TERMINAIS = (Status.INCLUIDO, Status.EXCLUIDO, Status.EXCLUIDO_TC)
    # Status em que o registro já entrou no processo de triagem (não-deletável).
    TRIADOS = (
        Status.EM_TRIAGEM,
        Status.INCLUIDO_TA,
        Status.EM_TEXTO,
        Status.INCLUIDO,
        Status.EXCLUIDO,
        Status.EXCLUIDO_TC,
    )

    protocolo = models.ForeignKey(
        ProtocoloTriagem, on_delete=models.CASCADE, related_name="registros"
    )
    origem_buscas = models.ManyToManyField(
        Busca,
        blank=True,
        related_name="registros",
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
    tipo = models.CharField(
        max_length=40, blank=True, help_text="Tipo de documento (Artigo, Livro…)."
    )
    link = models.URLField(max_length=600, blank=True)

    identificador = models.CharField(
        max_length=80,
        db_index=True,
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
    duplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicatas_resolvidas",
        help_text="Quem resolveu este registro como duplicata (auditoria).",
    )
    duplicado_em = models.DateTimeField(null=True, blank=True)
    ja_no_acervo = models.BooleanField(
        default=False,
        db_index=True,
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
        max_length=10,
        choices=Decisao.choices,
        blank=True,
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
        indexes = [
            # Acelera a busca de possíveis duplicatas por similaridade de título.
            GinIndex(
                OpClass(models.F("titulo"), name="gin_trgm_ops"),
                name="triagem_reg_titulo_trgm",
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

    def ficha(self) -> dict:
        """Dados bibliográficos normalizados para o componente de ficha único
        (templates/partials/_ficha_artigo.html). Mesmas chaves que
        acervo.Artigo.ficha(), para a ficha ser idêntica nas duas origens."""
        return {
            "titulo": self.titulo,
            "autores": self.autores,
            "ano": self.ano,
            "periodico": self.titulo_periodico,
            "tipo": self.tipo or "",  # CharField livre (sem choices)
            "doi": self.doi or "",
            "isbn": self.isbn or "",
            "idioma": self.idioma or "",
            "link": self.link,
            "link_alt": "",
            "palavras_chaves": self.palavras_chaves,
            "resumo": self.resumo,
            "base": "",  # base é por importação (origem_buscas), não do registro
            "area": "",  # registro não tem grande área (é metadado do Artigo)
        }

    @property
    def procedencia(self) -> list[dict]:
        """Bases e importadores de origem (para informar a decisão de dedup)."""
        itens = []
        for b in self.origem_buscas.all():
            por = b.criado_por
            itens.append(
                {
                    "base": b.base_nome or "base não informada",
                    "por": (por.nome_exibicao or por.email) if por else "—",
                }
            )
        return itens


class DecisaoTriagem(models.Model):
    """Parecer de triagem de um revisor (análogo a `acervo.Revisao`)."""

    class Etapa(models.TextChoices):
        TITULO_RESUMO = "ta", "Título e resumo"
        TEXTO_COMPLETO = "tc", "Texto completo"
        CALIBRACAO = "ca", "Calibração (piloto)"

    registro = models.ForeignKey(RegistroTriagem, on_delete=models.CASCADE, related_name="decisoes")
    revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="triagens_feitas"
    )
    etapa = models.CharField(
        max_length=2,
        choices=Etapa.choices,
        default=Etapa.TITULO_RESUMO,
        db_index=True,
        help_text="Etapa da triagem (título/resumo ou texto completo).",
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
                fields=["registro", "revisor", "etapa"],
                name="uniq_decisao_por_revisor_registro_etapa",
            ),
        ]

    def __str__(self) -> str:
        return f"Triagem do registro {self.registro_id} por {self.revisor_id}"


class ParDuplicataDescartado(models.Model):
    """Par de registros que um humano marcou como **não** sendo duplicatas.

    Evita reexibir o par na revisão de "possíveis duplicatas". Convenção:
    `registro_a_id < registro_b_id`.
    """

    registro_a = models.ForeignKey(RegistroTriagem, on_delete=models.CASCADE, related_name="+")
    registro_b = models.ForeignKey(RegistroTriagem, on_delete=models.CASCADE, related_name="+")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pares_descartados",
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


class RodadaCalibracao(models.Model):
    """Piloto de calibração: toda a equipe tria uma amostra comum antes do run.

    Mede a confiabilidade entre avaliadores (κ de Fleiss) sobre os mesmos itens,
    para decidir se os critérios estão claros o suficiente. As decisões usam a
    etapa `CALIBRACAO` em `DecisaoTriagem` — isoladas da triagem real (não mudam
    o status do registro nem entram nas contagens PRISMA/concordância oficiais).
    """

    protocolo = models.ForeignKey(
        ProtocoloTriagem, on_delete=models.CASCADE, related_name="calibracoes"
    )
    registros = models.ManyToManyField(
        RegistroTriagem,
        related_name="calibracoes",
        help_text="Amostra comum triada por toda a equipe.",
    )
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calibracoes_criadas",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    fechada_em = models.DateTimeField(null=True, blank=True)
    # Resultados congelados no fechamento (auditável).
    n_itens = models.PositiveIntegerField(default=0)
    n_revisores = models.PositiveIntegerField(default=0)
    perc_acordo = models.FloatField(null=True, blank=True)
    kappa = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "rodada de calibração"
        verbose_name_plural = "rodadas de calibração"
        ordering = ["-criada_em"]

    def __str__(self) -> str:
        return f"Calibração {self.pk} do protocolo {self.protocolo_id}"

