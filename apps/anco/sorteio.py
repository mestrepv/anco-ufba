"""Sorteio da análise (ANCO): distribui o corpus entre os analistas por cota.

Embaralha o pool com `random.Random(semente)` (a semente é gravada no
`SorteioANCO` para ser reprodutível/auditável) e distribui em round-robin
**preferindo diversidade de base**: cada analista tende a receber um artigo de
cada base diferente; a **repetição de base só ocorre quando não há itens de base
nova suficientes** (cota > nº de bases, ou base escassa). A diversidade atravessa
sorteios (considera as bases já recebidas pelo analista). `modo_revisao` define 1
(`unica`) ou 2 (`dupla`) analistas por artigo. Idempotente (não realoca artigos já
atribuídos). Não toca o acervo.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import transaction

from apps.acervo.models import Analise

from .models import AtribuicaoANCO, MembroANCO, ProjetoANCO, SorteioANCO

# Categorias de tipo de documento (checkboxes do filtro). Nenhuma marcada = todas.
# O `tipo` cru vem heterogêneo das bases ("Artigo", "Journal Article", "Periodico",
# "journalArticle", "Doctoralthesis"…); `categoria_tipo` normaliza para estes baldes.
CATEGORIAS_TIPO = [
    ("artigo", "Artigos"),
    ("tese", "Teses/Dissertações"),
    ("livro", "Livros"),
    ("capitulo", "Capítulos"),
    ("outro", "Outros/sem tipo"),
]
_CATEGORIAS_VALIDAS = {c for c, _ in CATEGORIAS_TIPO}


def _normalizar(texto: str) -> str:
    """Caixa-baixa, sem acento, espaços colapsados (port de relevancia.py)."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def categoria_tipo(tipo: str) -> str:
    """Normaliza o `tipo` cru de um item para uma das categorias do filtro.

    Ordem importa: 'doctoralthesis' contém 'thesis' (→ tese); 'booksection' é
    capítulo antes de casar 'book' (→ livro)."""
    t = _normalizar(tipo)
    if not t:
        return "outro"
    if "tese" in t or "dissert" in t or "thesis" in t:
        return "tese"
    if "capitul" in t or "chapter" in t or "booksection" in t or "incollection" in t:
        return "capitulo"
    if t == "livro" or t == "book" or "livro" in t:
        return "livro"
    if "artigo" in t or "article" in t or "periodic" in t:
        return "artigo"
    return "outro"


def _tipos_efetivos(tipos: list[str] | set[str] | None) -> set[str] | None:
    """Categorias válidas selecionadas. `None` = sem filtro (todas); uma coleção
    explícita = exatamente aquelas (coleção vazia = nenhuma casa)."""
    if tipos is None:
        return None
    return {c for c in tipos if c in _CATEGORIAS_VALIDAS}


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
    tipos: list[str] | set[str] | None = None,
    ja_atribuidos: set[int] | None = None,
    exigir_resumo: bool = True,
):
    """`ItemCorpus` que entrariam no sorteio AGORA — fonte única do preview e do
    sorteio. Regra: novos (não acervo `eh_legado`), não removidos, ainda **não
    atribuídos** em sorteios anteriores, opcionalmente **com resumo**
    (`exigir_resumo`; a análise AnCo pede o resumo) e opcionalmente restritos às
    categorias de `tipos` (artigo/tese/livro/capitulo/outro; vazio = todos). Dedup
    por artigo. Cada item recebe `.categoria` (o balde de tipo)."""
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
    sel = _tipos_efetivos(tipos)
    elegiveis, vistos = [], set()
    for it in itens:
        if it.artigo_id in ja_atribuidos or it.artigo_id in vistos:
            continue
        if exigir_resumo and not (it.resumo or "").strip():
            continue
        it.categoria = categoria_tipo(it.tipo)
        if sel is not None and it.categoria not in sel:
            continue
        vistos.add(it.artigo_id)
        elegiveis.append(it)
    return elegiveis


def _pool(
    projeto: ProjetoANCO,
    excluir_artigos: set[int],
    semente: int | None,
    *,
    tipos: list[str] | set[str] | None = None,
    exigir_resumo: bool = True,
) -> list[_ItemPool]:
    # Pool = itens elegíveis (mesma regra do preview), embaralhado pela semente.
    elegiveis = itens_elegiveis(
        projeto, tipos=tipos, exigir_resumo=exigir_resumo, ja_atribuidos=excluir_artigos
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
    tipos: list[str] | set[str] | None = None,
    exigir_resumo: bool = True,
) -> ResultadoSorteio:
    """Cria um `SorteioANCO` e aloca as `AtribuicaoANCO` (idempotente por artigo).

    `tipos` restringe às categorias de documento selecionadas (vazio = todas);
    `exigir_resumo` mantém fora os itens sem resumo.
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
    pool = _pool(projeto, ja_atribuidos, semente, tipos=tipos, exigir_resumo=exigir_resumo)
    if not pool:
        return ResultadoSorteio(None, motivo="Nenhum artigo disponível com esses filtros.")

    assentos = 2 if modo_revisao == SorteioANCO.ModoRevisao.DUPLA else 1
    vagas = {item.artigo_id: assentos for item in pool}
    # Bases que cada analista JÁ recebeu em sorteios anteriores — a diversidade
    # de base atravessa sorteios (num sorteio novo pós-exclusão, isto é vazio).
    bases_previas = {u.id: set() for u in analistas}
    for at in AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).select_related("artigo"):
        if at.analista_id in bases_previas:
            bases_previas[at.analista_id].add(_base_key(at.artigo))
    estado = {
        u.id: {"artigos": set(), "n": 0, "bases": set(bases_previas[u.id])} for u in analistas
    }
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
        """Prefere diversidade de base: 1ª passada devolve um item de base que o
        analista **ainda não tem**; só cai numa base repetida (fallback) se não
        houver item de base nova disponível — repetição só quando é inevitável."""
        st = estado[uid]
        fallback = None
        for item in pool:
            if vagas[item.artigo_id] <= 0:
                continue
            if item.artigo_id in st["artigos"] or item.artigo_id in analisados[uid]:
                continue
            if item.base not in st["bases"]:
                return item  # base inédita para este analista → melhor escolha
            if fallback is None:
                fallback = item  # 1º disponível de base repetida (reserva)
        return fallback

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
            estado[u.id]["bases"].add(item.base)
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
