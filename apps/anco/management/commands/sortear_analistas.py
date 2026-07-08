"""Sorteio complementar para um subconjunto de analistas do projeto ANCO.

Caso de uso: analistas que entraram no projeto DEPOIS do sorteio geral e ficaram
sem artigos. A tela de sorteio (`anco_sorteio`) sorteia sempre para todos os
analistas (daria cota nova também aos veteranos); este comando delega ao mesmo
`executar_sorteio` restringindo os beneficiários.

Garantias herdadas do motor: artigos únicos (nunca re-sorteia artigo já
atribuído no projeto), diversidade de base preferida, semente gravada no
`SorteioANCO` (auditável), reversível pela tela de sorteio (desfazer).

Exemplos:
    manage.py sortear_analistas --projeto piloto-revisao-anco --sem-atribuicao --dry-run
    manage.py sortear_analistas --projeto piloto-revisao-anco --emails a@x.br b@y.br --cota 5
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.anco.models import ProjetoANCO
from apps.anco.sorteio import (
    analistas_do_projeto,
    analistas_sem_atribuicao,
    executar_sorteio,
)


class Command(BaseCommand):
    help = "Sorteia artigos (cota fixa) só para os analistas indicados do projeto ANCO."

    def add_arguments(self, parser):
        parser.add_argument("--projeto", required=True, help="Slug do projeto ANCO.")
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument(
            "--sem-atribuicao",
            action="store_true",
            help="Seleciona os analistas do projeto que ainda não têm NENHUM artigo.",
        )
        grupo.add_argument(
            "--emails",
            nargs="+",
            help="E-mails dos analistas beneficiários (membros do projeto).",
        )
        parser.add_argument("--cota", type=int, default=5, help="Artigos por analista (padrão 5).")
        parser.add_argument(
            "--incluir-sem-resumo",
            action="store_true",
            help="Permite sortear itens sem resumo (padrão: exige resumo).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o resultado e desfaz tudo (nada é gravado).",
        )

    def handle(self, *args, **opts):
        projeto = ProjetoANCO.objects.filter(slug=opts["projeto"]).first()
        if projeto is None:
            raise CommandError(f"Projeto ANCO não encontrado: {opts['projeto']}")

        membros = analistas_do_projeto(projeto)
        if opts["sem_atribuicao"]:
            beneficiarios = analistas_sem_atribuicao(projeto)
            if not beneficiarios:
                self.stdout.write("Todos os analistas do projeto já têm atribuição. Nada a fazer.")
                return
        else:
            por_email = {u.email: u for u in membros}
            faltando = [e for e in opts["emails"] if e not in por_email]
            if faltando:
                raise CommandError(
                    "Não são analistas deste projeto: " + ", ".join(faltando)
                )
            beneficiarios = [por_email[e] for e in opts["emails"]]

        with transaction.atomic():
            res = executar_sorteio(
                projeto,
                analistas=beneficiarios,
                cota=opts["cota"],
                exigir_resumo=not opts["incluir_sem_resumo"],
                observacoes=(
                    "Sorteio complementar (manage.py sortear_analistas) para: "
                    + ", ".join(u.email for u in beneficiarios)
                ),
            )
            if res.sorteio is None:
                raise CommandError(res.motivo or "Nada a sortear.")

            self.stdout.write(
                f"Sorteio #{res.sorteio.pk} (semente {res.sorteio.semente}): "
                f"{res.atribuidas} atribuição(ões) para {res.analistas} analista(s)."
            )
            for at in res.sorteio.atribuicoes.select_related("analista", "artigo").order_by(
                "analista__email", "pk"
            ):
                self.stdout.write(
                    f"  {at.analista.nome_exibicao or at.analista.email}: "
                    f"[{at.artigo_id}] {at.artigo.titulo[:80]}"
                )
            for uid, falta in (res.faltas or {}).items():
                self.stdout.write(
                    self.style.WARNING(f"  analista id={uid}: faltaram {falta} artigo(s) no pool")
                )

            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("DRY-RUN: nada foi gravado."))
