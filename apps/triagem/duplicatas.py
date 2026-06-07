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
    pares = ParDuplicataDescartado.objects.filter(registro_a__protocolo=protocolo).values_list(
        "registro_a_id", "registro_b_id"
    )
    return {frozenset(p) for p in pares}


def importadores(registro) -> set[int]:
    """IDs de quem importou as buscas de origem do registro (donos do par)."""
    return set(
        registro.origem_buscas.exclude(criado_por__isnull=True).values_list(
            "criado_por_id", flat=True
        )
    )


def primeiro_autor(autores: str) -> str:
    """Sobrenome do primeiro autor (ex.: 'Roubekas, NP; ...' -> 'Roubekas')."""
    if not autores:
        return ""
    primeiro = autores.replace("\n", ";").split(";")[0].strip()
    return primeiro.split(",")[0].strip()


def mesmo_primeiro_autor(a: str, b: str) -> bool:
    pa, pb = primeiro_autor(a).lower(), primeiro_autor(b).lower()
    return bool(pa) and pa == pb


def mesmo_ano(a, b) -> bool:
    return a.ano is not None and a.ano == b.ano


def _concordancia(par: dict) -> int:
    """Quantos sinais além do título concordam (ano, 1º autor). 0–2."""
    a, b = par["a"], par["b"]
    return int(mesmo_ano(a, b)) + int(mesmo_primeiro_autor(a.autores, b.autores))


# Campos exibidos na revisão de duplicatas (decidir não só pelo título).
_CAMPOS = (
    "id",
    "titulo",
    "doi",
    "ano",
    "identificador",
    "tipo",
    "link",
    "autores",
    "resumo",
    "palavras_chaves",
    "titulo_periodico",
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
    pares = [{"a": regs[a], "b": regs[b], "sim": s} for a, b, s in triplas]
    # Prováveis duplicatas reais primeiro: mais sinais concordando (ano, autor),
    # depois maior similaridade de título. Os "mesmo título mas tudo diferente"
    # vão para o fim.
    # Concordância (ano/autor) primeiro, depois similaridade; pk como desempate
    # estável para a navegação por índice ser consistente entre cargas.
    pares.sort(key=lambda p: (-_concordancia(p), -p["sim"], p["a"].pk, p["b"].pk))
    return pares


def pares_do_usuario(
    projeto, user, eh_curador: bool, limiar: float = LIMIAR, max_pares: int = 200
) -> list[dict]:
    """Pares que o usuário pode resolver: curador vê todos; analista só os que
    tocam bases que ele importou (Fase 12.4)."""
    pares = pares_possiveis(projeto, limiar, max_pares)
    if eh_curador:
        return pares
    return [p for p in pares if user.id in (importadores(p["a"]) | importadores(p["b"]))]


def contar_pares_do_usuario(projeto, user, eh_curador: bool, limiar: float = LIMIAR) -> int:
    """Conta os pares que o usuário pode resolver (alinha painel e tela)."""
    if eh_curador:
        return contar_pares_possiveis(projeto, limiar)
    return len(pares_do_usuario(projeto, user, False, limiar))


def contar_pares_possiveis(protocolo, limiar: float = LIMIAR) -> int:
    """Conta os pares possíveis pendentes (sem carregar objetos) — p/ badges."""
    status = [s.value for s in RegistroTriagem.EM_ABERTO]
    with connection.cursor() as cur:
        cur.execute(_SQL_PARES, [protocolo.id, protocolo.id, status, status, limiar, 1000])
        linhas = cur.fetchall()
    descartados = _pares_descartados(protocolo)
    return sum(1 for a, b, _ in linhas if frozenset({a, b}) not in descartados)


@transaction.atomic
def mesclar(canonico: RegistroTriagem, duplicado: RegistroTriagem, por=None) -> None:
    """Marca `duplicado` como DUPLICADO de `canonico` e funde as origens.

    Registra quem resolveu (`por`) e quando, para auditoria. Reversível por
    `desfazer_mescla` enquanto o registro não tiver entrado em triagem real.
    """
    from django.utils import timezone

    if canonico.pk == duplicado.pk:
        return
    for busca in duplicado.origem_buscas.all():
        canonico.origem_buscas.add(busca)
    duplicado.status = RegistroTriagem.Status.DUPLICADO
    duplicado.duplicado_de = canonico
    duplicado.duplicado_por = por
    duplicado.duplicado_em = timezone.now()
    duplicado.save(update_fields=["status", "duplicado_de", "duplicado_por", "duplicado_em"])


@transaction.atomic
def desfazer_mescla(duplicado: RegistroTriagem) -> bool:
    """Reabre um registro marcado como duplicata (volta a `identificado`).

    Remove do canônico as buscas que vieram do duplicado (pares fuzzy são, na
    prática, de bases distintas). Retorna False se já não for uma duplicata.
    """
    if duplicado.status != RegistroTriagem.Status.DUPLICADO:
        return False
    canonico = duplicado.duplicado_de
    if canonico is not None:
        for busca in duplicado.origem_buscas.all():
            canonico.origem_buscas.remove(busca)
    duplicado.status = RegistroTriagem.Status.IDENTIFICADO
    duplicado.duplicado_de = None
    duplicado.duplicado_por = None
    duplicado.duplicado_em = None
    duplicado.save(update_fields=["status", "duplicado_de", "duplicado_por", "duplicado_em"])
    return True


def mescladas(protocolo):
    """Registros marcados como duplicata neste protocolo (para auditoria/undo)."""
    return (
        RegistroTriagem.objects.filter(protocolo=protocolo, status=RegistroTriagem.Status.DUPLICADO)
        .select_related("duplicado_de", "duplicado_por")
        .order_by("-duplicado_em")
    )


def descartar(reg_a: RegistroTriagem, reg_b: RegistroTriagem, por=None) -> None:
    """Registra que o par NÃO é duplicata (ordena a<b)."""
    a, b = sorted((reg_a.pk, reg_b.pk))
    ParDuplicataDescartado.objects.get_or_create(
        registro_a_id=a, registro_b_id=b, defaults={"criado_por": por}
    )
