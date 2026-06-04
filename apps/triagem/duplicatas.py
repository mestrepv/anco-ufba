"""Possíveis duplicatas por similaridade de título (pg_trgm).

Complementa a dedup determinística (DOI/ISBN/hash) cobrindo o mesmo artigo
**sem DOI** ou com **DOI divergente** entre bases. Um humano confirma cada par:
**mesclar** (vira `duplicado_de`, soma origens, marca DUPLICADO) ou **descartar**
(registra que não são duplicatas, para não reaparecer).
"""

from __future__ import annotations

from django.db import connection, transaction

from .models import ParDuplicataDescartado, RegistroTriagem

LIMIAR = 0.6

# Self-join por similaridade de título; `%%` é o operador `%` do pg_trgm (usa o
# índice GIN). Uma única consulta no lugar de uma por registro.
_SQL_PARES = """
SELECT a.id AS a_id, b.id AS b_id, similarity(a.titulo, b.titulo) AS sim
FROM triagem_registrotriagem a
JOIN triagem_registrotriagem b
  ON a.id < b.id
 AND a.titulo %% b.titulo
WHERE a.protocolo_id = %s AND b.protocolo_id = %s
  AND a.status = ANY(%s) AND b.status = ANY(%s)
  AND a.ja_no_acervo = false AND b.ja_no_acervo = false
  AND a.identificador <> b.identificador
  AND similarity(a.titulo, b.titulo) >= %s
ORDER BY sim DESC
LIMIT %s
"""


def _pares_descartados(protocolo) -> set[frozenset]:
    pares = ParDuplicataDescartado.objects.filter(
        registro_a__protocolo=protocolo
    ).values_list("registro_a_id", "registro_b_id")
    return {frozenset(p) for p in pares}


# Campos exibidos na revisão de duplicatas (decidir não só pelo título).
_CAMPOS = (
    "id", "titulo", "doi", "ano", "identificador",
    "autores", "resumo", "palavras_chaves", "titulo_periodico",
)


def pares_possiveis(protocolo, limiar: float = LIMIAR, max_pares: int = 200) -> list[dict]:
    """Pares (a, b, sim) de registros em aberto com títulos semelhantes."""
    status = [s.value for s in RegistroTriagem.EM_ABERTO]
    with connection.cursor() as cur:
        cur.execute(
            _SQL_PARES,
            [protocolo.id, protocolo.id, status, status, limiar, max_pares * 2],
        )
        linhas = cur.fetchall()

    descartados = _pares_descartados(protocolo)
    triplas = [
        (a_id, b_id, round(sim, 2))
        for a_id, b_id, sim in linhas
        if frozenset({a_id, b_id}) not in descartados
    ][:max_pares]
    if not triplas:
        return []

    ids = {i for a, b, _ in triplas for i in (a, b)}
    regs = {r.id: r for r in RegistroTriagem.objects.filter(id__in=ids).only(*_CAMPOS)}
    return [{"a": regs[a], "b": regs[b], "sim": s} for a, b, s in triplas]


@transaction.atomic
def mesclar(canonico: RegistroTriagem, duplicado: RegistroTriagem) -> None:
    """Marca `duplicado` como DUPLICADO de `canonico` e funde as origens."""
    if canonico.pk == duplicado.pk:
        return
    for busca in duplicado.origem_buscas.all():
        canonico.origem_buscas.add(busca)
    duplicado.status = RegistroTriagem.Status.DUPLICADO
    duplicado.duplicado_de = canonico
    duplicado.save(update_fields=["status", "duplicado_de"])


def descartar(reg_a: RegistroTriagem, reg_b: RegistroTriagem) -> None:
    """Registra que o par NÃO é duplicata (ordena a<b)."""
    a, b = sorted((reg_a.pk, reg_b.pk))
    ParDuplicataDescartado.objects.get_or_create(registro_a_id=a, registro_b_id=b)
