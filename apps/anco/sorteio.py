"""Sorteio da análise (ANCO): distribui o corpus entre os analistas por cota.

Puramente **aleatório** (embaralha o pool com `random.Random(semente)`; a semente
é gravada no `SorteioANCO` para ser reprodutível/auditável). `modo_revisao` define
1 (`unica`) ou 2 (`dupla`) analistas por artigo. Round-robin estável; idempotente
(não realoca artigos já atribuídos em sorteios anteriores). Não toca o acervo.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import transaction

from apps.acervo.models import Analise

from .models import AtribuicaoANCO, MembroANCO, ProjetoANCO, SorteioANCO

# "Onde o termo aparece": campos selecionáveis (checkboxes). Nenhum = todos.
CAMPOS_CHOICES = [
    ("titulo", "Título"),
    ("resumo", "Resumo"),
    ("palavras_chave", "Palavras-chave"),
]
_CAMPOS_VALIDOS = [c for c, _ in CAMPOS_CHOICES]
_ROTULO_CAMPO = {"titulo": "título", "resumo": "resumo", "palavras_chave": "palavras-chave"}

# Grupos de sinônimos (normalizados, sem acento): digitar qualquer termo do
# grupo casa com TODOS os outros — ex.: "análise cognitiva" ≡ "cognitive analysis".
_SINONIMOS = [
    {
        "analise cognitiva",
        "analises cognitivas",
        "cognitive analysis",
        "cognitive analyses",
        "cognitive analytics",
    },
]


def _normalizar(texto: str) -> str:
    """Caixa-baixa, sem acento, espaços colapsados (port de relevancia.py)."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def _campos_efetivos(campos: list[str] | None) -> list[str]:
    """Campos válidos selecionados; vazio = todos os campos."""
    sel = [c for c in (campos or []) if c in _CAMPOS_VALIDOS]
    return sel or list(_CAMPOS_VALIDOS)


def _termos_equivalentes(termo_norm: str) -> set[str]:
    """O termo + seus sinônimos (PT↔EN). Vazio se o termo for vazio."""
    if not termo_norm:
        return set()
    termos = {termo_norm}
    for grupo in _SINONIMOS:
        if termo_norm in grupo:
            termos |= grupo
    return termos


def _texto_do_campo(item, campo: str) -> str:
    if campo == "titulo":
        return item.titulo or ""
    if campo == "resumo":
        return item.resumo or ""
    return item.palavras_chaves or ""  # palavras_chave


def _campo_casado(item, termos: set[str], campos: list[str] | None) -> str:
    """Rótulo do 1º campo (entre os selecionados) onde casa QUALQUER um dos
    termos (equivalentes), ou ''."""
    for chave in _campos_efetivos(campos):
        texto = _normalizar(_texto_do_campo(item, chave))
        if any(t in texto for t in termos):
            return _ROTULO_CAMPO[chave]
    return ""


@dataclass
class _ItemPool:
    artigo_id: int
    base: str


@dataclass
class ResultadoSorteio:
    sorteio: SorteioANCO | None
    atribuidas: int = 0
    analistas: int = 0
    faltas: dict = field(default_factory=dict)
    motivo: str = ""


def _base_key(artigo) -> str:
    if artigo.base_consulta_id:
        return f"base:{artigo.base_consulta_id}"
    outra = (artigo.outra_base_consulta or "").strip().lower()
    if outra:
        return f"outra:{outra}"
    return f"art:{artigo.pk}"


def analistas_do_projeto(projeto: ProjetoANCO):
    """Usuários com papel analista **no projeto**, ativos."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    ids = projeto.membros.filter(papel=MembroANCO.Papel.ANALISTA).values_list(
        "usuario_id", flat=True
    )
    return list(User.objects.filter(pk__in=ids, is_active=True).order_by("pk"))


def itens_elegiveis(
    projeto: ProjetoANCO,
    *,
    termo: str = "",
    campos: list[str] | None = None,
    ja_atribuidos: set[int] | None = None,
):
    """`ItemCorpus` que entrariam no sorteio AGORA — fonte única do preview e do
    sorteio. Regra: novos (não acervo `eh_legado`), não removidos, ainda **não
    atribuídos** em sorteios anteriores, e que contêm `termo` em algum dos
    `campos` selecionados (vazio = todos). Dedup por artigo. Cada item recebe
    `.casou_em` (campo onde o termo bateu)."""
    if ja_atribuidos is None:
        ja_atribuidos = set(
            AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).values_list(
                "artigo_id", flat=True
            )
        )
    itens = (
        projeto.itens.filter(removido=False, artigo__isnull=False, artigo__eh_legado=False)
        .select_related("artigo")
        .order_by("titulo")
    )
    termos = _termos_equivalentes(_normalizar(termo))
    elegiveis, vistos = [], set()
    for it in itens:
        if it.artigo_id in ja_atribuidos or it.artigo_id in vistos:
            continue
        if termos:
            campo = _campo_casado(it, termos, campos)
            if not campo:
                continue
            it.casou_em = campo
        else:
            it.casou_em = ""
        vistos.add(it.artigo_id)
        elegiveis.append(it)
    return elegiveis


def _pool(
    projeto: ProjetoANCO,
    excluir_artigos: set[int],
    semente: int | None,
    *,
    termo: str = "",
    campos: list[str] | None = None,
) -> list[_ItemPool]:
    # Pool = itens elegíveis (mesma regra do preview), embaralhado pela semente.
    elegiveis = itens_elegiveis(
        projeto, termo=termo, campos=campos, ja_atribuidos=excluir_artigos
    )
    pool = [_ItemPool(artigo_id=it.artigo_id, base=_base_key(it.artigo)) for it in elegiveis]
    random.Random(semente).shuffle(pool)
    return pool


@transaction.atomic
def executar_sorteio(
    projeto: ProjetoANCO,
    *,
    modo_revisao: str = SorteioANCO.ModoRevisao.UNICA,
    cota: int = 5,
    por=None,
    observacoes: str = "",
    analistas=None,
    semente: int | None = None,
    termo: str = "",
    campos: list[str] | None = None,
) -> ResultadoSorteio:
    """Cria um `SorteioANCO` e aloca as `AtribuicaoANCO` (idempotente por artigo).

    `termo`/`campos` exigem a presença do termo em algum dos campos selecionados
    (título/resumo/palavras-chave; vazio = todos).
    """
    if analistas is None:
        analistas = analistas_do_projeto(projeto)
    if not analistas:
        return ResultadoSorteio(None, motivo="Sem analistas no projeto.")
    if semente is None:
        semente = random.randrange(2**31)

    ja_atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).values_list("artigo_id", flat=True)
    )
    pool = _pool(projeto, ja_atribuidos, semente, termo=termo, campos=campos)
    if not pool:
        return ResultadoSorteio(None, motivo="Nenhum artigo disponível com esses filtros.")

    assentos = 2 if modo_revisao == SorteioANCO.ModoRevisao.DUPLA else 1
    vagas = {item.artigo_id: assentos for item in pool}
    estado = {u.id: {"artigos": set(), "n": 0} for u in analistas}
    analisados = {
        u.id: set(Analise.objects.filter(analista=u).values_list("artigo_id", flat=True))
        for u in analistas
    }

    sorteio = SorteioANCO.objects.create(
        projeto=projeto,
        modo_revisao=modo_revisao,
        cota=cota,
        criado_por=por,
        observacoes=observacoes,
        semente=semente,
    )

    def _escolher(uid: int) -> _ItemPool | None:
        st = estado[uid]
        for item in pool:
            if vagas[item.artigo_id] <= 0:
                continue
            if item.artigo_id in st["artigos"] or item.artigo_id in analisados[uid]:
                continue
            return item
        return None

    atribuicoes, progresso = [], True
    while progresso:
        progresso = False
        for u in analistas:
            if estado[u.id]["n"] >= cota:
                continue
            item = _escolher(u.id)
            if item is None:
                continue
            atribuicoes.append(
                AtribuicaoANCO(sorteio=sorteio, analista=u, artigo_id=item.artigo_id)
            )
            vagas[item.artigo_id] -= 1
            estado[u.id]["artigos"].add(item.artigo_id)
            estado[u.id]["n"] += 1
            progresso = True

    AtribuicaoANCO.objects.bulk_create(atribuicoes)
    faltas = {uid: cota - est["n"] for uid, est in estado.items() if est["n"] < cota}
    return ResultadoSorteio(
        sorteio=sorteio,
        atribuidas=len(atribuicoes),
        analistas=len(analistas),
        faltas=faltas,
    )


@transaction.atomic
def desfazer_sorteio(sorteio: SorteioANCO) -> int:
    """Remove as atribuições e o sorteio. As `Analise` já iniciadas não são apagadas."""
    n = sorteio.atribuicoes.count()
    sorteio.delete()  # cascata remove as AtribuicaoANCO
    return n
