"""Aplica DOIs recuperados (do referencial + verificados na Crossref) aos
Artigos da base revisada que ainda estão sem DOI.

Decisões por status da verificação Crossref:
  - ok               → aplica sempre
  - duvidoso (>=0.3) → aplica só com --incluir-duvidosos (similaridade textual
                       baixa pode ser HTML entities, alfabeto não-latino etc.)
  - duvidoso (<0.3)  → nunca aplica (provavelmente match errado)
  - inexistente      → nunca aplica (Crossref desconhece)
  - erro_*           → nunca aplica

Conflitos: se o Artigo já tem DOI diferente, loga conflito sem sobrescrever.

Uso:
  python manage.py aplicar_dois_recuperados \\
      --mapping /app/dois_recuperados.json \\
      --verificacao /app/dois_verificados.json \\
      --dry-run
  python manage.py aplicar_dois_recuperados \\
      --mapping /app/dois_recuperados.json \\
      --verificacao /app/dois_verificados.json \\
      --incluir-duvidosos
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.acervo.models import Artigo, _gerar_identificador_interno

LIMIAR_DUVIDOSO = 0.3


def normalizar(s: str) -> str:
    if not s:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().strip())


class Command(BaseCommand):
    help = "Aplica DOIs recuperados e verificados na Crossref aos Artigos eh_legado."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--mapping", required=True,
            help="JSON gerado por tools/recuperar_dois_referencial.py")
        parser.add_argument("--verificacao", required=True,
            help="JSON gerado por tools/verificar_dois_crossref.py")
        parser.add_argument("--dry-run", action="store_true",
            help="Roda em transação com rollback.")
        parser.add_argument("--incluir-duvidosos", action="store_true",
            help="Aplica também DOIs com status=duvidoso (sim >= 0.3).")
        parser.add_argument("--csv-conflitos", type=str, default=None,
            help="Caminho do CSV com os conflitos (artigo já tem DOI diferente).")

    def handle(self, *args, **options):
        mapping_path = Path(options["mapping"])
        verif_path = Path(options["verificacao"])
        dry_run = options["dry_run"]
        incluir_duv = options["incluir_duvidosos"]
        csv_conflitos = options["csv_conflitos"]

        if not mapping_path.exists():
            raise CommandError(f"Mapping não encontrado: {mapping_path}")
        if not verif_path.exists():
            raise CommandError(f"Verificação não encontrada: {verif_path}")

        mapping = json.load(open(mapping_path, encoding="utf-8"))
        verificacao = json.load(open(verif_path, encoding="utf-8"))["verificados"]

        log = Counter()
        conflitos: list[dict] = []

        with transaction.atomic():
            self._aplicar(mapping["resultados"], verificacao, incluir_duv, log, conflitos)
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY-RUN: revertendo."))
                transaction.set_rollback(True)

        self._reportar(log)

        if csv_conflitos and conflitos:
            import csv
            with open(csv_conflitos, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "artigo_id", "titulo", "ano", "doi_atual", "doi_sugerido", "fonte_match"
                ])
                w.writeheader()
                for c in conflitos:
                    w.writerow(c)
            self.stdout.write(f"  CSV de conflitos: {csv_conflitos} ({len(conflitos)} linhas)")

    def _aplicar(
        self,
        matches: list[dict],
        verificacao: dict,
        incluir_duv: bool,
        log: Counter,
        conflitos: list[dict],
    ) -> None:
        # Como múltiplas entradas podem apontar p/ mesmo DOI, evitamos aplicar
        # 2x na sessão (a 2ª aplicação violaria UNIQUE).
        dois_aplicados_nesta_sessao: set[str] = set()
        for match in matches:
            doi = match["doi_recuperado"]
            v = verificacao.get(doi, {"status": "nao_verificado"})
            status = v["status"]

            # Decide elegibilidade
            if status == "ok":
                pass
            elif status == "duvidoso":
                if not incluir_duv:
                    log["pulado:duvidoso_sem_flag"] += 1
                    continue
                if v.get("similaridade_titulo", 0) < LIMIAR_DUVIDOSO:
                    log["pulado:duvidoso_muito_baixo"] += 1
                    continue
            else:
                log[f"pulado:{status}"] += 1
                continue

            # Acha o Artigo no banco: tem identificador_interno = hash(titulo,ano,periodico)
            # da revisada. Reuso o mesmo helper que o migrate_base_revisada usa.
            # Mas como o periódico foi normalizado (Title Case) no banco, preciso
            # buscar pelo identificador atual.
            #
            # Estratégia mais simples: busca pelo título + ano. Se houver
            # múltiplos, refina por periódico normalizado.
            titulo_norm = normalizar(match["titulo_revisada"])
            ano = match["ano_revisada"]

            candidatos = list(
                Artigo.objects.filter(eh_legado=True, ano=ano).only(
                    "id", "titulo", "titulo_periodico", "doi"
                )
            )
            candidato = None
            for art in candidatos:
                if normalizar(art.titulo) == titulo_norm:
                    candidato = art
                    break

            if candidato is None:
                log["nao_encontrado_no_banco"] += 1
                continue

            # Já tem DOI?
            if candidato.doi:
                if candidato.doi == doi:
                    log["ja_tinha_mesmo_doi"] += 1
                else:
                    log["conflito_doi_diferente"] += 1
                    conflitos.append({
                        "artigo_id": candidato.id,
                        "titulo": candidato.titulo,
                        "ano": candidato.ano,
                        "doi_atual": candidato.doi,
                        "doi_sugerido": doi,
                        "fonte_match": match.get("confianca", ""),
                    })
                continue

            # DOI já foi aplicado a outro artigo nesta sessão? (mapping com duplicatas)
            if doi in dois_aplicados_nesta_sessao:
                log["pulado:doi_ja_aplicado_a_outro"] += 1
                continue

            # Verifica se o DOI já existe no banco em outro artigo (legado anterior
            # à execução, ou conflito real). Se existir, pula.
            if Artigo.objects.filter(doi=doi).exclude(pk=candidato.pk).exists():
                log["pulado:doi_em_outro_artigo_do_banco"] += 1
                continue

            # Aplica DOI. Limpa identificador_interno para que `identificador_canonico`
            # passe a usar o DOI como chave (URLs públicas mudam para /artigo/<doi-slug>/).
            candidato.doi = doi
            candidato.identificador_interno = None
            try:
                with transaction.atomic():  # savepoint individual
                    candidato.save(update_fields=["doi", "identificador_interno"])
                dois_aplicados_nesta_sessao.add(doi)
                log[f"aplicado:{status}"] += 1
            except Exception as e:  # noqa: BLE001
                log["erro_save"] += 1
                self.stdout.write(self.style.ERROR(
                    f"  erro salvando artigo {candidato.id} (doi={doi}): {e}"
                ))

    def _reportar(self, log: Counter) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Aplicação de DOIs ==="))
        for k in sorted(log):
            self.stdout.write(f"  {k:35s} {log[k]}")
        total_com_doi = Artigo.objects.filter(eh_legado=True).exclude(doi__isnull=True).count()
        total_sem_doi = Artigo.objects.filter(eh_legado=True, doi__isnull=True).count()
        self.stdout.write("")
        self.stdout.write(f"  Artigos revisada com DOI:  {total_com_doi}")
        self.stdout.write(f"  Artigos revisada sem DOI:  {total_sem_doi}")
