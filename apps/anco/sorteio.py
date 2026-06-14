"""Sorteio da análise (ANCO): distribui o corpus entre os analistas por cota.

Puramente **aleatório** (embaralha o pool com `random.Random(semente)`; a semente
é gravada no `SorteioANCO` para ser reprodutível/auditável). `modo_revisao` define
1 (`unica`) ou 2 (`dupla`) analistas por artigo. Round-robin estável; idempotente
(não realoca artigos já atribuídos em sorteios anteriores). Não toca o acervo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from django.db import transaction

from apps.acervo.models import Analise

from .models import AtribuicaoANCO, MembroANCO, ProjetoANCO, SorteioANCO


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


def _pool(projeto: ProjetoANCO, excluir_artigos: set[int], semente: int | None) -> list[_ItemPool]:
    itens = (
        projeto.itens.filter(removido=False, artigo__isnull=False)
        .select_related("artigo")
        .order_by("pk")
    )
    pool, vistos = [], set()
    for it in itens:
        if it.artigo_id in vistos or it.artigo_id in excluir_artigos:
            continue
        vistos.add(it.artigo_id)
        pool.append(_ItemPool(artigo_id=it.artigo_id, base=_base_key(it.artigo)))
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
) -> ResultadoSorteio:
    """Cria um `SorteioANCO` e aloca as `AtribuicaoANCO` (idempotente por artigo)."""
    if analistas is None:
        analistas = analistas_do_projeto(projeto)
    if not analistas:
        return ResultadoSorteio(None, motivo="Sem analistas no projeto.")
    if semente is None:
        semente = random.randrange(2**31)

    ja_atribuidos = set(
        AtribuicaoANCO.objects.filter(sorteio__projeto=projeto).values_list("artigo_id", flat=True)
    )
    pool = _pool(projeto, ja_atribuidos, semente)
    if not pool:
        return ResultadoSorteio(None, motivo="Nenhum artigo no corpus disponível.")

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
