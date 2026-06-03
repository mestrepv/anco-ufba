"""
Importa a base revisada pela curadoria bibliotecária (`base-anco-revisada.json`).

Esta base **substitui** o legado importado por `migrate_legacy`. Use `--reset`
para limpar previamente os registros legados (analises status=`legado`,
artigos eh_legado=True, usuários `legado-*`) numa única transação.

Idempotente: re-rodar sem `--reset` reaplica os dados (update_or_create por
identificador determinístico). Loga estatísticas e desvios.

Uso:
    python manage.py migrate_base_revisada --path /app/base-anco-revisada.json --dry-run
    python manage.py migrate_base_revisada --path /app/base-anco-revisada.json --reset
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

logger = logging.getLogger(__name__)

User = get_user_model()

USERNAME_BIBLIOTECARIA = "curadoria-bibliotecaria"
NOME_BIBLIOTECARIA = "Equipe AnCo"
EMAIL_BIBLIOTECARIA = "bibliotecaria@anco.local"


# ---------------------------------------------------------------------------
# Resolução de termo de vocabulário
# ---------------------------------------------------------------------------


def resolver_termo(codigo_vocab: str, nome: str, log: Counter) -> TermoVocabulario | None:
    """get_or_create de termo dentro do vocabulário identificado por `codigo`."""
    nome = (nome or "").strip()
    if not nome:
        return None
    vocab, _ = Vocabulario.objects.get_or_create(
        codigo=codigo_vocab,
        defaults={"nome": codigo_vocab.title()},
    )
    termo, criado = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab,
        nome=nome,
    )
    if criado:
        log[f"vocab:{codigo_vocab}:criado"] += 1
    return termo


class Command(BaseCommand):
    help = "Importa a base revisada (xlsx -> JSON) substituindo o legado."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--path",
            type=str,
            default="/app/base-anco-revisada.json",
            help="Caminho do JSON gerado por tools/converter_base_revisada.py",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Roda em transação com rollback no final; nada persiste.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Antes de importar, apaga registros legado: análises com "
                "status=legado, artigos eh_legado=True, usuários legado-*. "
                "Não afeta análises/artigos não-legado."
            ),
        )

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        path = Path(options["path"])
        dry_run = options["dry_run"]
        reset = options["reset"]

        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")

        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        registros = payload["registros"]
        self.stdout.write(f"Lidos {len(registros)} registros de {path.name}.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: nada será persistido."))

        log = Counter()

        with transaction.atomic():
            if reset:
                self._limpar_legado(log)
            self._importar(registros, log)
            if dry_run:
                transaction.set_rollback(True)

        self._reportar(log)

    # ------------------------------------------------------------------
    # Limpeza do legado
    # ------------------------------------------------------------------

    def _limpar_legado(self, log: Counter) -> None:
        self.stdout.write(self.style.WARNING("--reset: limpando registros legado…"))

        # Ordem importa por causa dos PROTECT em FKs.
        # 1) Análises legado (cascade -> Revisao, ComentarioRevisao)
        n_an, _ = Analise.objects.filter(status=Analise.Status.LEGADO).delete()
        log["reset:analises_legado_deletadas"] = n_an

        # 2) Artigos legado (cascade -> SnapshotLink)
        n_ar, _ = Artigo.objects.filter(eh_legado=True).delete()
        log["reset:artigos_legado_deletados"] = n_ar

        # 3) Usuários legado-* (já sem FK protegendo)
        n_u, _ = User.objects.filter(username__startswith="legado-").delete()
        log["reset:users_legado_deletados"] = n_u

        # 4) Termos órfãos de vocabulário (sem artigo nem análise associados)
        orfaos = TermoVocabulario.objects.filter(
            artigos_por_base__isnull=True,
            analises_por_epistemologia__isnull=True,
            analises_por_teoria__isnull=True,
        )
        n_t, _ = orfaos.delete()
        log["reset:termos_orfaos_deletados"] = n_t

    # ------------------------------------------------------------------
    # Importação
    # ------------------------------------------------------------------

    def _get_or_create_bibliotecaria(self) -> User:
        user, criado = User.objects.get_or_create(
            username=USERNAME_BIBLIOTECARIA,
            defaults={
                "email": EMAIL_BIBLIOTECARIA,
                "nome_exibicao": NOME_BIBLIOTECARIA,
                "papel": User.Papel.ANALISTA,
                "eh_legado": True,
                "is_active": False,
            },
        )
        if criado:
            self.stdout.write(f"  + usuária {USERNAME_BIBLIOTECARIA} criada")
        return user

    def _importar(self, registros: list[dict], log: Counter) -> None:
        bibliotecaria = self._get_or_create_bibliotecaria()
        artigos_processados: set[int] = set()

        for reg in registros:
            try:
                self._importar_um(reg, bibliotecaria, log, artigos_processados)
            except Exception as exc:  # noqa: BLE001
                log["erro"] += 1
                logger.exception(
                    "Falha no registro xlsx L%s: %s",
                    reg.get("_origem", {}).get("linha_xlsx"),
                    exc,
                )

    def _importar_um(
        self,
        reg: dict,
        analista: User,
        log: Counter,
        artigos_processados: set[int],
    ) -> None:
        origem = reg["_origem"]
        artigo_data = reg["artigo"]
        analise_data = reg["analise"]

        # Aviso: linhas com `alertas` (apenas L616 atualmente) são importadas
        # mesmo assim, com flag no campo `observacoes` da análise.
        observacoes_extras = []
        if origem.get("alertas"):
            log["alerta:linha_com_problema"] += 1
            observacoes_extras.append(
                f"[Migração] Linha xlsx {origem['linha_xlsx']} marcada com alertas: "
                + "; ".join(origem["alertas"])
            )
        if origem.get("alinhamento_corrigido"):
            log["info:alinhamento_corrigido"] += 1

        # 1) Resolve a base de consulta como TermoVocabulario
        base_termo = resolver_termo("base", artigo_data["base_consulta"], log)

        # 2) Cria/atualiza Artigo. Identificador: DOI quando houver; senão
        # `identificador_interno` determinístico gerado pelo save() do modelo.
        doi = (artigo_data["doi"] or "").strip().lower() or None
        defaults = {
            "titulo": artigo_data["titulo"] or "(sem título)",
            "titulo_traduzido": artigo_data["titulo_traduzido"],
            "titulo_periodico": artigo_data["titulo_periodico"],
            "ano": artigo_data["ano"],
            "area": artigo_data["area"][:200],
            "autores": artigo_data["autores"],
            "palavras_chaves": artigo_data["palavras_chaves"],
            "vinculacao_institucional": artigo_data["vinculacao_institucional"],
            "base_consulta": base_termo,
            "outra_base_consulta": artigo_data["outra_base_consulta"],
            "link_acesso": artigo_data["link_acesso"][:600]
            if artigo_data["link_acesso"].startswith(("http://", "https://"))
            else "",
            "artigo_pago": artigo_data["artigo_pago"] or False,
            "eh_legado": True,
        }

        artigo: Artigo
        if doi:
            artigo, criado_art = Artigo.objects.update_or_create(
                doi=doi, defaults=defaults
            )
            log["artigo:com_doi"] += 1
        else:
            # Gera identificador determinístico para casar com mesma chave em re-runs.
            from apps.acervo.models import _gerar_identificador_interno
            ident = _gerar_identificador_interno(
                defaults["titulo"], defaults["ano"], defaults["titulo_periodico"]
            )
            artigo, criado_art = Artigo.objects.update_or_create(
                identificador_interno=ident, defaults=defaults
            )
            log["artigo:identificador_interno"] += 1

        log["artigo:criado" if criado_art else "artigo:atualizado"] += 1

        # Pula 2ª análise sobre o mesmo artigo (UniqueConstraint analista+artigo).
        if artigo.id in artigos_processados:
            log["analise:pulada_duplicata_interna"] += 1
            return
        artigos_processados.add(artigo.id)

        # 3) Cria/atualiza Análise
        analise_defaults = {
            "status": Analise.Status.LEGADO,
            "presenca_titulo": analise_data["presenca_titulo"],
            "presenca_resumo": analise_data["presenca_resumo"],
            "presenca_palavras_chave": analise_data["presenca_palavras_chave"],
            "presenca_referencias": analise_data["presenca_referencias"],
            "presenca_corpo": analise_data["presenca_corpo"],
            "pertinencia": analise_data["pertinencia"],
            "define_conceito": analise_data["define_conceito"],
            "objeto": analise_data["objeto"],
            "objetivo": analise_data["objetivo"],
            "foco": analise_data["foco"],
            "metodologia": analise_data["metodologia"],
            "resultados": analise_data["resultados"],
            "observacoes": "\n\n".join(observacoes_extras),
        }

        analise, criada = Analise.objects.update_or_create(
            artigo=artigo, analista=analista, defaults=analise_defaults
        )
        log["analise:criada" if criada else "analise:atualizada"] += 1

        # 4) M2M de epistemologia e teoria (após save do objeto)
        analise.epistemologia.clear()
        for nome in analise_data["epistemologia"]:
            termo = resolver_termo("epistemologia", nome, log)
            if termo:
                analise.epistemologia.add(termo)
        analise.teoria.clear()
        for nome in analise_data["teoria"]:
            termo = resolver_termo("teoria", nome, log)
            if termo:
                analise.teoria.add(termo)

    # ------------------------------------------------------------------
    # Relatório
    # ------------------------------------------------------------------

    def _reportar(self, log: Counter) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Relatório ==="))
        for chave in sorted(log):
            self.stdout.write(f"  {chave:42s} {log[chave]}")
        self.stdout.write("")
        self.stdout.write(f"  Total Artigo:                              {Artigo.objects.count()}")
        self.stdout.write(f"    eh_legado=True:                          {Artigo.objects.filter(eh_legado=True).count()}")
        self.stdout.write(f"  Total Analise:                             {Analise.objects.count()}")
        self.stdout.write(f"    status=legado:                           {Analise.objects.filter(status=Analise.Status.LEGADO).count()}")
        self.stdout.write(f"  Total User:                                {User.objects.count()}")
