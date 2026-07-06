"""Backfill de resumos vazios do **acervo** (Artigo) via DOI.

Diferente de `backfill_resumos` (que opera no corpus ANCO / `ItemCorpus`), este
comando age direto na tabela `Artigo` — o acervo público.

Dois contratos do projeto exigem salvaguardas fortes:

- **Acervo legado é intocável** (curadoria da Dra. Eneida): mudanças no legado
  são *propostas*, nunca aplicadas. Por padrão o comando **não grava** em
  `eh_legado=True`. Para esses, use `--proposta <arquivo.csv>`: ele só
  **exporta** (doi, título do acervo, título vindo da Crossref, se batem,
  abstract recuperado) para revisão humana antes de qualquer aplicação.

- **DOI do acervo não é 100% confiável** (~23 DOIs errados): como o lookup é por
  DOI, um DOI errado traz o abstract de OUTRO artigo. Por isso comparamos o
  título retornado pela Crossref com o do acervo (`titulo_bate`): divergência =
  provável DOI errado. Na proposta isso vira coluna; na aplicação a não-legado,
  vira **trava** (não grava quando o título não bate).

Uso:
    # não-legado: aplica direto (com trava de título)
    manage.py backfill_resumos_acervo [--dry-run]
    # legado: só gera proposta para revisão (NUNCA grava)
    manage.py backfill_resumos_acervo --proposta /caminho/proposta_legado.csv
"""

from __future__ import annotations

import csv
import difflib
import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.acervo.models import Artigo
from apps.acervo.services.abstracts import melhor_abstract
from apps.acervo.services.crossref import lookup_doi

_NAO_ALFANUM = re.compile(r"[^a-z0-9]+")
# Limiares de similaridade título-acervo × título-Crossref.
_BATE = 0.85  # >= => "S" (mesmo artigo)
_TALVEZ = 0.60  # entre _TALVEZ e _BATE => "~" (revisar)


def _norm(titulo: str) -> str:
    return _NAO_ALFANUM.sub(" ", (titulo or "").lower()).strip()


def _titulo_bate(titulo_acervo: str, titulo_ref: str) -> tuple[str, float]:
    """Compara títulos e classifica: 'S' (bate), '~' (revisar), 'N' (diverge).

    Sem título de referência (a fonte não devolveu), retorna '?'.
    """
    if not titulo_ref:
        return "?", 0.0
    r = difflib.SequenceMatcher(None, _norm(titulo_acervo), _norm(titulo_ref)).ratio()
    if r >= _BATE:
        return "S", r
    if r >= _TALVEZ:
        return "~", r
    return "N", r


class Command(BaseCommand):
    help = "Backfill de resumos vazios do acervo (Artigo) via DOI, com trava de título."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="só relata, não grava")
        parser.add_argument(
            "--proposta",
            metavar="ARQUIVO.csv",
            help="modo proposta p/ LEGADO: exporta candidatos p/ revisão, sem gravar",
        )

    def handle(self, *args, **opts):
        if opts["proposta"]:
            self._modo_proposta(opts["proposta"])
        else:
            self._modo_aplicar_nao_legado(opts["dry_run"])

    def _alvos(self, *, legado: bool):
        vazio = Q(resumo="") | Q(resumo__isnull=True)
        return (
            Artigo.objects.filter(vazio, eh_legado=legado)
            .exclude(doi="")
            .exclude(doi__isnull=True)
            .order_by("pk")
        )

    # ------------------------------------------------------------------ #
    # Modo 1: aplicar nos NÃO-legado (com trava de título)
    # ------------------------------------------------------------------ #
    def _modo_aplicar_nao_legado(self, dry: bool):
        alvos = list(self._alvos(legado=False))
        self.stdout.write(f"{len(alvos)} artigo(s) não-legado com resumo vazio e DOI.")
        preenchidos = falhas = travados = 0
        por_fonte = {"crossref": 0, "openalex": 0}

        for art in alvos:
            novo, fonte = melhor_abstract(art.doi)
            if not novo:
                falhas += 1
                continue
            # Trava anti-DOI-errado: só grava se o título da Crossref bater.
            ref = lookup_doi(art.doi)  # cacheado (melhor_abstract já consultou)
            titulo_ref = ref.dados.get("titulo", "") if ref.encontrado else ""
            bate, _ = _titulo_bate(art.titulo, titulo_ref)
            if bate == "N":
                travados += 1
                self.stdout.write(f"  ⚠ {art.pk} título NÃO bate (DOI suspeito {art.doi}) — pulado")
                continue
            preenchidos += 1
            por_fonte[fonte] += 1
            self.stdout.write(f"  ✓ {art.pk} [{fonte}] +{len(novo)} chars — {art.titulo[:55]}")
            if not dry:
                art.resumo = novo
                art.save(update_fields=["resumo"])

        verbo = "seriam" if dry else "foram"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY-RUN] ' if dry else ''}{preenchidos} resumo(s) {verbo} "
                f"preenchido(s) (crossref={por_fonte['crossref']}, "
                f"openalex={por_fonte['openalex']}); {travados} travado(s) por "
                f"título divergente; {falhas} sem abstract."
            )
        )

    # ------------------------------------------------------------------ #
    # Modo 2: proposta para o LEGADO (nunca grava)
    # ------------------------------------------------------------------ #
    def _modo_proposta(self, caminho: str):
        if not caminho.endswith(".csv"):
            raise CommandError("--proposta deve terminar em .csv")
        alvos = list(self._alvos(legado=True))
        self.stdout.write(
            f"Gerando proposta para {len(alvos)} artigo(s) LEGADO com resumo vazio e DOI…"
        )
        linhas = []
        stats = {"S": 0, "~": 0, "N": 0, "?": 0, "sem_abstract": 0}
        for art in alvos:
            novo, fonte = melhor_abstract(art.doi)
            ref = lookup_doi(art.doi)
            titulo_ref = ref.dados.get("titulo", "") if ref.encontrado else ""
            bate, ratio = _titulo_bate(art.titulo, titulo_ref)
            if not novo:
                stats["sem_abstract"] += 1
            else:
                stats[bate] += 1
            linhas.append(
                {
                    "artigo_id": art.pk,
                    "doi": art.doi,
                    "titulo_acervo": art.titulo,
                    "titulo_referencia": titulo_ref,
                    "titulo_bate": bate,
                    "similaridade": f"{ratio:.2f}",
                    "fonte": fonte,
                    "len_abstract": len(novo),
                    "abstract_recuperado": novo,
                }
            )

        with open(caminho, "w", newline="", encoding="utf-8") as fh:
            campos = [
                "artigo_id",
                "doi",
                "titulo_acervo",
                "titulo_referencia",
                "titulo_bate",
                "similaridade",
                "fonte",
                "len_abstract",
                "abstract_recuperado",
            ]
            w = csv.DictWriter(fh, fieldnames=campos)
            w.writeheader()
            w.writerows(linhas)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nProposta escrita em {caminho} ({len(linhas)} linhas). "
                f"Nenhum registro do acervo foi alterado.\n"
                f"  título bate (S): {stats['S']} · revisar (~): {stats['~']} · "
                f"NÃO bate (N): {stats['N']} · sem título ref (?): {stats['?']} · "
                f"sem abstract: {stats['sem_abstract']}\n"
                f"Revisão da curadoria (Dra. Eneida): aplicar só as linhas 'S' "
                f"(e as '~' após conferência); descartar 'N' (DOI provavelmente errado)."
            )
        )
