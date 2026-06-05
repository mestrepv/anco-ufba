"""Relevância por correspondência de termos (Revisão ANCO, Fase 13).

Sem embeddings (decisão 2026-06-05): a relevância de um registro é o **nº de
termos distintos da estratégia de busca** presentes no título/resumo/palavras-
chave (normalizados, sem acento, caixa-baixa). É explicável ao analista
("casou com N termos") e auditável. O valor é cacheado em
`RegistroTriagem.relevancia_score` e usado para ordenar o pool de incluídos e
para priorizar o sorteio de análise.
"""

from __future__ import annotations

import re
import unicodedata

from .models import ProtocoloTriagem, RegistroTriagem

_OPERADORES = {"and", "or", "not", "near", "adj", "with"}
_MIN_TAMANHO = 3  # ignora tokens muito curtos (ruído booleano/colagem)


def _normalizar(texto: str) -> str:
    """Caixa-baixa, sem acento, espaços colapsados."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def termos_do_protocolo(protocolo: ProtocoloTriagem) -> list[str]:
    """Termos de relevância: `termos_realce` (vírgula) ou, em falta, tokens da
    estratégia/strings de busca, sem operadores booleanos nem tokens curtos.
    """
    if protocolo.termos_realce.strip():
        brutos = [t.strip() for t in protocolo.termos_realce.split(",")]
    else:
        fonte = " ".join(
            [protocolo.estrategia_busca]
            + list(protocolo.buscas.exclude(string_busca="").values_list("string_busca", flat=True))
        )
        brutos = re.split(r"[^\wÀ-ÿ]+", fonte)

    termos, vistos = [], set()
    for bruto in brutos:
        norm = _normalizar(bruto)
        if len(norm) < _MIN_TAMANHO or norm in _OPERADORES or norm in vistos:
            continue
        vistos.add(norm)
        termos.append(norm)
    return termos


def score_registro(registro: RegistroTriagem, termos: list[str] | None = None) -> int:
    """Nº de termos distintos presentes no título+resumo+palavras-chave."""
    if termos is None:
        termos = termos_do_protocolo(registro.protocolo)
    if not termos:
        return 0
    texto = _normalizar(" ".join([registro.titulo, registro.resumo, registro.palavras_chaves]))
    return sum(1 for termo in termos if termo in texto)


def atualizar_relevancia(registro: RegistroTriagem, termos: list[str] | None = None) -> int:
    """Calcula e persiste `relevancia_score` (sem disparar histórico/auto_now)."""
    score = score_registro(registro, termos)
    if score != registro.relevancia_score:
        registro.relevancia_score = score
        RegistroTriagem.objects.filter(pk=registro.pk).update(relevancia_score=score)
    return score


def recalcular_protocolo(protocolo: ProtocoloTriagem) -> int:
    """Recalcula o score de todos os registros do protocolo. Retorna a contagem."""
    termos = termos_do_protocolo(protocolo)
    registros = list(protocolo.registros.all())
    for r in registros:
        r.relevancia_score = score_registro(r, termos)
    if registros:
        RegistroTriagem.objects.bulk_update(registros, ["relevancia_score"], batch_size=500)
    return len(registros)
