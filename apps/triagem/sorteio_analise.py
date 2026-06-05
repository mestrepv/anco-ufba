"""Sorteio da análise — Revisão ANCO (Fase 13).

Distribui os artigos **incluídos** na triagem entre os analistas do projeto:
uma **cota** por analista, **priorizando maior relevância** e **preferindo bases
distintas** (preferência, nunca bloqueia — decisão §8.2). `modo_revisao` define
1 (`unica`) ou 2 (`dupla`) analistas por artigo.

Determinístico: pool ordenado por (-relevância, -ano, pk); round-robin estável
entre analistas. Não toca o acervo curado nem o protocolo rigoroso.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from apps.acervo.models import Analise

from .models import (
    AtribuicaoAnalise,
    ProjetoMembro,
    ProtocoloTriagem,
    RegistroTriagem,
    SorteioAnalise,
)


@dataclass
class _ItemPool:
    artigo_id: int
    base: str
    score: int
    ano: int


@dataclass
class ResultadoSorteioAnalise:
    sorteio: SorteioAnalise | None
    atribuidas: int = 0
    analistas: int = 0
    faltas: dict = field(default_factory=dict)  # {analista_id: nº de vagas não preenchidas}
    motivo: str = ""


def _base_key(artigo) -> str:
    """Chave de base para a regra de diversidade. Bases desconhecidas viram
    chaves únicas (tratadas como distintas — não penalizam)."""
    if artigo.base_consulta_id:
        return f"base:{artigo.base_consulta_id}"
    outra = (artigo.outra_base_consulta or "").strip().lower()
    if outra:
        return f"outra:{outra}"
    return f"art:{artigo.pk}"


def analistas_do_projeto(projeto: ProtocoloTriagem):
    """Usuários com papel analista **no projeto**, ativos."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    ids = projeto.membros.filter(papel=ProjetoMembro.Papel.ANALISTA).values_list(
        "usuario_id", flat=True
    )
    return list(User.objects.filter(pk__in=ids, is_active=True).order_by("pk"))


def _pool(projeto: ProtocoloTriagem, excluir_artigos: set[int]) -> list[_ItemPool]:
    regs = (
        projeto.registros.filter(status=RegistroTriagem.Status.INCLUIDO, artigo__isnull=False)
        .select_related("artigo")
        .order_by("-relevancia_score", "-artigo__ano", "pk")
    )
    pool, vistos = [], set()
    for r in regs:
        if r.artigo_id in vistos or r.artigo_id in excluir_artigos:
            continue
        vistos.add(r.artigo_id)
        pool.append(
            _ItemPool(
                artigo_id=r.artigo_id,
                base=_base_key(r.artigo),
                score=r.relevancia_score,
                ano=r.artigo.ano or 0,
            )
        )
    return pool


@transaction.atomic
def executar_sorteio_analise(
    projeto: ProtocoloTriagem,
    *,
    modo_revisao: str = SorteioAnalise.ModoRevisao.UNICA,
    cota: int = 5,
    por=None,
    observacoes: str = "",
    analistas=None,
) -> ResultadoSorteioAnalise:
    """Cria um `SorteioAnalise` e aloca as `AtribuicaoAnalise` (idempotente por
    artigo: não realoca artigos já atribuídos em sorteios anteriores do projeto).
    """
    if analistas is None:
        analistas = analistas_do_projeto(projeto)
    if not analistas:
        return ResultadoSorteioAnalise(None, motivo="Sem analistas no projeto.")

    # Não realocar artigos já distribuídos por sorteios anteriores deste projeto.
    ja_atribuidos = set(
        AtribuicaoAnalise.objects.filter(sorteio__projeto=projeto).values_list(
            "artigo_id", flat=True
        )
    )
    pool = _pool(projeto, ja_atribuidos)
    if not pool:
        return ResultadoSorteioAnalise(None, motivo="Nenhum artigo incluído disponível.")

    assentos = 2 if modo_revisao == SorteioAnalise.ModoRevisao.DUPLA else 1
    vagas = {item.artigo_id: assentos for item in pool}

    # Estado por analista + artigos que cada um já analisou (unique artigo+analista).
    estado = {u.id: {"bases": set(), "artigos": set(), "n": 0} for u in analistas}
    analisados = {
        u.id: set(Analise.objects.filter(analista=u).values_list("artigo_id", flat=True))
        for u in analistas
    }

    sorteio = SorteioAnalise.objects.create(
        projeto=projeto,
        modo_revisao=modo_revisao,
        cota=cota,
        criado_por=por,
        observacoes=observacoes,
    )

    def _escolher(uid: int) -> _ItemPool | None:
        st = estado[uid]
        # 1ª passada: prefere base nova. 2ª: relaxa a diversidade.
        for prefere_base_nova in (True, False):
            for item in pool:
                if vagas[item.artigo_id] <= 0:
                    continue
                if item.artigo_id in st["artigos"] or item.artigo_id in analisados[uid]:
                    continue
                if prefere_base_nova and item.base in st["bases"]:
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
                AtribuicaoAnalise(sorteio=sorteio, analista=u, artigo_id=item.artigo_id)
            )
            vagas[item.artigo_id] -= 1
            st = estado[u.id]
            st["artigos"].add(item.artigo_id)
            st["bases"].add(item.base)
            st["n"] += 1
            progresso = True

    AtribuicaoAnalise.objects.bulk_create(atribuicoes)
    faltas = {uid: cota - est["n"] for uid, est in estado.items() if est["n"] < cota}
    return ResultadoSorteioAnalise(
        sorteio=sorteio,
        atribuidas=len(atribuicoes),
        analistas=len(analistas),
        faltas=faltas,
    )
