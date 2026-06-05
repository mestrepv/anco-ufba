"""Importa um arquivo (RIS/BibTeX/CSV) de uma base como uma `Busca` da triagem.

Exemplo:
    python manage.py importar_triagem export_scopus.ris --base Scopus \
        --string-busca '"cognitive analysis"' --n-identificados 256

Idempotente: rodar de novo na mesma base/arquivo não duplica registros.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from apps.triagem.importacao import (
    decodificar,
    detectar_formato,
    importar_para_busca,
    parse_conteudo,
)
from apps.triagem.models import Busca, ProtocoloTriagem
from apps.vocabulario.models import TermoVocabulario


class Command(BaseCommand):
    help = "Importa um export (RIS/BibTeX/CSV) de uma base como Busca da triagem."

    def add_arguments(self, parser) -> None:
        parser.add_argument("arquivo", type=str)
        parser.add_argument("--formato", choices=["ris", "bibtex", "csv"], default=None)
        parser.add_argument("--base", type=str, default=None,
                            help="Nome do termo do vocabulário `base` (ex.: Scopus).")
        parser.add_argument("--outra-base", type=str, default=None,
                            help="Base fora do vocabulário controlado.")
        parser.add_argument("--string-busca", type=str, default="")
        parser.add_argument("--n-identificados", type=int, default=0)
        parser.add_argument("--data", type=str, default=None, help="YYYY-MM-DD")
        parser.add_argument("--projeto", type=str, default=None,
                            help="Slug do projeto (default: projeto ativo).")

    def handle(self, *args, **opts) -> None:
        caminho = Path(opts["arquivo"])
        if not caminho.exists():
            raise CommandError(f"Arquivo não encontrado: {caminho}")

        formato = opts["formato"] or detectar_formato(caminho.name)
        if not formato:
            raise CommandError(
                "Não consegui inferir o formato pela extensão; use --formato."
            )

        base_termo = None
        if opts["base"]:
            base_termo = TermoVocabulario.objects.filter(
                vocabulario__codigo="base", nome__iexact=opts["base"]
            ).first()
            if base_termo is None:
                raise CommandError(
                    f"Base '{opts['base']}' não está no vocabulário. "
                    "Cadastre no admin ou use --outra-base."
                )

        if opts["projeto"]:
            protocolo = ProtocoloTriagem.objects.filter(slug=opts["projeto"]).first()
            if protocolo is None:
                raise CommandError(f"Projeto '{opts['projeto']}' não encontrado.")
        else:
            protocolo = ProtocoloTriagem.ativo()
        busca = Busca.objects.create(
            protocolo=protocolo,
            base_consulta=base_termo,
            outra_base=opts["outra_base"] or "",
            string_busca=opts["string_busca"],
            n_identificados=opts["n_identificados"],
            formato=formato,
            data_busca=parse_date(opts["data"]) if opts["data"] else None,
        )

        conteudo = decodificar(caminho.read_bytes())
        registros = parse_conteudo(conteudo, formato)
        res = importar_para_busca(busca, registros)

        self.stdout.write(self.style.SUCCESS(
            f"Busca #{busca.pk} ({busca.base_nome}): "
            f"{res.total} lidos · {res.criados} novos · {res.duplicados} duplicados · "
            f"{res.ja_no_acervo} já no acervo · {res.ignorados} ignorados."
        ))
