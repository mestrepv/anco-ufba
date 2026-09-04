"""
Comando para importar a base referencial legada (1.443 registros).

Idempotente: rodar duas vezes nao duplica. Loga normalizacoes.

Uso:
    python manage.py migrate_legacy --path dados/legado/base-referencial-original.json
    python manage.py migrate_legacy --dry-run    # nao grava nada
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.acervo.models import Analise, Artigo
from apps.vocabulario.models import TermoVocabulario, Vocabulario

logger = logging.getLogger(__name__)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers de normalizacao
# ---------------------------------------------------------------------------

ANO_MIN = 1900
ANO_MAX = 2030

_TRUE_TOKENS = {"sim", "s", "1", "x", "yes", "y"}
_FALSE_TOKENS = {"nao", "não", "n", "0", "no"}


def normalizar_ano(valor: Any) -> int | None:
    """Inteiro entre 1900 e 2030, senao None."""
    if isinstance(valor, int) and ANO_MIN <= valor <= ANO_MAX:
        return valor
    if isinstance(valor, str):
        valor_strip = valor.strip()
        if valor_strip.isdigit():
            n = int(valor_strip)
            if ANO_MIN <= n <= ANO_MAX:
                return n
    return None


def normalizar_doi(valor: Any) -> str | None:
    """
    Retorna DOI canonico (`10.xxxx/...`) quando reconheceu, senao None.

    - Strip e remove prefixo "DOI:" / "doi:".
    - Extrai DOI de URLs `https://doi.org/10.xxxx/...`.
    - Rejeita formatos ISSN (`xxxx-xxxx`), strings vazias e placeholders.
    """
    if not isinstance(valor, str):
        return None
    v = valor.strip()
    if v in {"", "-"}:
        return None
    # Remove prefixo "DOI:" ou variacoes
    v = re.sub(r"^(?i:doi)\s*:\s*", "", v).strip()
    # Extrai de URL
    m = re.search(r"(10\.\d{2,9}/[^\s\"<>]+)", v)
    if m:
        return m.group(1).rstrip(".,;").strip()
    # ISSN nao serve como DOI
    if re.match(r"^\d{4}-\d{3}[\dxX]$", v):
        return None
    # Se ja casa o formato canonico (raro chegar aqui sem cair na regex acima)
    if re.match(r"^10\.\d{2,9}/", v):
        return v
    return None


def gerar_id_legado(titulo: str, ano: int | None, periodico: str) -> str:
    """
    ID deterministico para artigos sem DOI: `legacy:HASH16`.

    Mesma entrada -> mesmo hash (idempotencia).
    """
    base = f"{(titulo or '').strip().lower()}|{ano or 0}|{(periodico or '').strip().lower()}"
    h = hashlib.sha1(base.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"legacy:{h}"


def para_booleano(valor: Any) -> bool | None:
    """Mapeia variantes S/N/0/1/x para bool. Texto longo ou indefinido vira None."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int) and valor in (0, 1):
        return bool(valor)
    if not isinstance(valor, str):
        return None
    v = valor.strip().lower()
    if v in _TRUE_TOKENS:
        return True
    if v in _FALSE_TOKENS:
        return False
    return None


def texto_limpo(valor: Any) -> str:
    """Strip, descarta placeholders comuns ('-', 'Não', 'NÃO' isolados)."""
    if valor is None:
        return ""
    s = str(valor).strip()
    if s in {"", "-"}:
        return ""
    return s


_NOME_TAMANHO_MAX = 120


def normalizar_nome_analista(valor: Any) -> str:
    """
    Trim + Title Case para chave de deduplicacao de analistas.

    Valores muito longos (>120 chars) ou contendo pontuacao excessiva sao
    tratados como dados corrompidos (ex: descricao de artigo no campo errado)
    e devolvem string vazia, fazendo o registro cair no `legado-anonimo`.
    """
    if not isinstance(valor, str):
        return ""
    nome = valor.strip()
    if not nome:
        return ""
    # Heuristica: nome humano nao tem mais que ~120 chars nem multiplas pontuacoes finais
    if len(nome) > _NOME_TAMANHO_MAX:
        return ""
    if nome.count(".") > 2 or nome.count(",") > 3:
        return ""
    return " ".join(p.capitalize() for p in nome.split())


def slug_username(nome: str) -> str:
    """Username slug a partir do nome, prefixado com `legado-` e truncado a 150 chars (limite Django)."""
    base = slugify(nome) or "anonimo"
    return f"legado-{base}"[:150]


# ---------------------------------------------------------------------------
# Resolucao de termos do vocabulario
# ---------------------------------------------------------------------------


def resolver_ou_criar_termo(
    vocabulario_codigo: str,
    valor: str,
    log: Counter,
) -> TermoVocabulario | None:
    """
    Devolve termo canonico para `valor`. Se nao existir, cria com ativo=False
    para revisao posterior. Retorna None se valor for vazio.
    """
    valor_limpo = texto_limpo(valor)
    if not valor_limpo:
        return None

    canonico = TermoVocabulario.buscar_canonico(vocabulario_codigo, valor_limpo)
    if canonico:
        log[f"termo:{vocabulario_codigo}:resolvido_canonico"] += 1
        return canonico

    # Criar termo inativo com nome truncado
    vocab, _ = Vocabulario.objects.get_or_create(
        codigo=vocabulario_codigo,
        defaults={"nome": vocabulario_codigo.title()},
    )
    nome_truncado = valor_limpo[:200]
    termo, criado = TermoVocabulario.objects.get_or_create(
        vocabulario=vocab,
        nome=nome_truncado,
        defaults={"ativo": False},
    )
    if criado:
        log[f"termo:{vocabulario_codigo}:criado_inativo"] += 1
    return termo


# ---------------------------------------------------------------------------
# Comando
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Importa a base referencial legada (JSON) para Artigo + Analise."

    DEFAULT_PATH = "dados/legado/base-referencial-original.json"
    USERNAME_ANONIMO = "legado-anonimo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=self.DEFAULT_PATH,
            help=f"Caminho do JSON de origem (default: {self.DEFAULT_PATH}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nao grava nada; apenas reporta o que seria feito.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Importa apenas os N primeiros registros (0 = todos).",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        dry_run = options["dry_run"]
        limit = options["limit"]

        if not path.exists():
            raise CommandError(f"Arquivo nao encontrado: {path}")

        with path.open() as f:
            registros = json.load(f)

        if limit:
            registros = registros[:limit]

        self.stdout.write(f"Lidos {len(registros)} registros de {path}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: nada sera gravado."))

        log = Counter()

        if dry_run:
            # roda em transaction e da rollback
            with transaction.atomic():
                self._importar_lote(registros, log)
                transaction.set_rollback(True)
        else:
            with transaction.atomic():
                self._importar_lote(registros, log)

        self._reportar(log)

    # ---- Importacao -----------------------------------------------------

    def _importar_lote(self, registros: list[dict], log: Counter) -> None:
        # Pre-cria User legado-anonimo (chave estavel)
        anonimo, _ = User.objects.get_or_create(
            username=self.USERNAME_ANONIMO,
            defaults={
                "email": f"{self.USERNAME_ANONIMO}@anco.local",
                "nome_exibicao": "Análise legada (analista não identificado)",
                "eh_legado": True,
                "papel": User.Papel.LEITOR,
                "is_active": False,
            },
        )

        cache_users: dict[str, User] = {self.USERNAME_ANONIMO: anonimo}

        for idx, reg in enumerate(registros, start=1):
            try:
                self._importar_registro(reg, log, cache_users, anonimo)
            except Exception as exc:  # noqa: BLE001
                log["erro"] += 1
                logger.exception(
                    "Falha no registro #%d (linha %s): %s", idx, reg.get("_linha"), exc
                )

    def _importar_registro(
        self,
        reg: dict,
        log: Counter,
        cache_users: dict[str, User],
        anonimo: User,
    ) -> None:
        # Resolver analista
        nome = normalizar_nome_analista(reg.get("Analista"))
        if nome:
            username = slug_username(nome)
            if username in cache_users:
                user = cache_users[username]
            else:
                user, criado = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": f"{username}@anco.local",
                        "nome_exibicao": nome,
                        "eh_legado": True,
                        "papel": User.Papel.LEITOR,
                        "is_active": False,
                    },
                )
                cache_users[username] = user
                if criado:
                    log["user:legado:criado"] += 1
            log["analise:com_analista"] += 1
        else:
            user = anonimo
            log["analise:analista_anonimo"] += 1

        # Resolver / criar Artigo
        titulo = texto_limpo(reg.get("Titulo_do_artigo"))
        ano = normalizar_ano(reg.get("Ano"))
        if ano is None and reg.get("Ano") not in (None, ""):
            log["ano:invalido_para_null"] += 1
        periodico = texto_limpo(reg.get("Titulo_do_Periodico"))

        doi = normalizar_doi(reg.get("Numero_DOI"))
        if doi is None:
            doi = gerar_id_legado(titulo, ano, periodico)
            log["artigo:id_gerado_legacy"] += 1
        else:
            log["artigo:doi_canonico"] += 1

        # Base de consulta
        base_termo = resolver_ou_criar_termo("base", reg.get("Base_de_Consulta"), log)

        link_principal = texto_limpo(reg.get("Link_de_Acesso"))
        if not link_principal:
            log["link:vazio"] += 1
        else:
            log["link:preenchido"] += 1

        artigo, _ = Artigo.objects.update_or_create(
            doi=doi,
            defaults={
                "titulo": titulo or "(sem título)",
                "titulo_periodico": periodico,
                "ano": ano,
                "volume": str(reg.get("Volume") or "")[:50],
                "numero": str(reg.get("Numero") or "")[:50],
                "pagina_inicial": str(reg.get("Pagina_Inicial") or "")[:20],
                "pagina_final": str(reg.get("Pagina_Final") or "")[:20],
                "area": texto_limpo(reg.get("Area"))[:200],
                "autores": texto_limpo(reg.get("Nomes")),
                "vinculacao_institucional": texto_limpo(reg.get("Vinculacao_Institucional")),
                "palavras_chaves": texto_limpo(reg.get("Palavras_Chaves")),
                "resumo": texto_limpo(reg.get("Resumo")),
                "base_consulta": base_termo,
                "link_acesso": link_principal[:600]
                if link_principal.startswith(("http://", "https://"))
                else "",
                "artigo_pago": para_booleano(reg.get("Artigo_Pago")) or False,
                "eh_legado": True,
            },
        )

        # Compor observacoes (campos do legado sem destino direto)
        partes_obs = []
        outra_base = texto_limpo(reg.get("Outra_Base_de_Consulta"))
        if outra_base:
            partes_obs.append(f"Outra base: {outra_base}")
        termos_freq = texto_limpo(reg.get("Termos_mais_frequentes"))
        if termos_freq:
            partes_obs.append(f"Termos mais frequentes: {termos_freq}")
        outras = texto_limpo(reg.get("Outras_Observacoes"))
        if outras:
            partes_obs.append(outras)
        observacoes = "\n\n".join(partes_obs)

        # Pertinencia / Define como booleano OU texto longo em campos textuais
        pertinencia = para_booleano(reg.get("Pertinencia_para_Area"))
        aspectos_relevantes = texto_limpo(reg.get("Aspectos_Relevantes"))
        if pertinencia is None:
            # Se Pertinencia tem texto longo, anexa em aspectos_relevantes
            pert_texto = texto_limpo(reg.get("Pertinencia_para_Area"))
            if pert_texto and len(pert_texto) > 3:
                aspectos_relevantes = (
                    f"[do campo Pertinência] {pert_texto}\n\n{aspectos_relevantes}".strip()
                )

        define = para_booleano(reg.get("Define_Conceito"))
        definicao_extraida = ""
        if define is None:
            def_texto = texto_limpo(reg.get("Define_Conceito"))
            if def_texto and len(def_texto) > 3:
                definicao_extraida = def_texto

        analise, criada = Analise.objects.update_or_create(
            artigo=artigo,
            analista=user,
            defaults={
                "status": Analise.Status.LEGADO,
                "presenca_titulo": para_booleano(reg.get("Presenca_AC_no_Titulo")),
                "presenca_resumo": para_booleano(reg.get("Presenca_AC_no_Resumo")),
                "presenca_palavras_chave": para_booleano(reg.get("Presenca_AC_nas_PalavrasChaves")),
                "presenca_referencias": para_booleano(reg.get("Presenca_AC_nas_Referencias")),
                "presenca_corpo": para_booleano(reg.get("Presenca_AC_no_Corpo")),
                "pertinencia": pertinencia,
                "aspectos_relevantes": aspectos_relevantes,
                "define_conceito": define,
                "definicao_extraida": definicao_extraida,
                "objeto": texto_limpo(reg.get("Objeto")),
                "objetivo": texto_limpo(reg.get("Objetivo")),
                "foco": texto_limpo(reg.get("Foco")),
                "metodologia": texto_limpo(reg.get("Metodologia")),
                "referenciais": texto_limpo(reg.get("Referenciais")),
                "resultados": texto_limpo(reg.get("Resultados")),
                "contexto_producao": texto_limpo(reg.get("Contexto_de_Producao")),
                "observacoes": observacoes,
            },
        )

        # M2M depois do save
        epist_termo = resolver_ou_criar_termo("epistemologia", reg.get("Epistemologia"), log)
        teoria_termo = resolver_ou_criar_termo("teoria", reg.get("Teoria"), log)
        if epist_termo:
            analise.epistemologia.add(epist_termo)
        if teoria_termo:
            analise.teoria.add(teoria_termo)

        if criada:
            log["analise:criada"] += 1
        else:
            log["analise:atualizada"] += 1

    # ---- Relatorio ------------------------------------------------------

    def _reportar(self, log: Counter) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Relatório de migração ==="))
        for chave in sorted(log):
            self.stdout.write(f"  {chave:40s}  {log[chave]}")
        self.stdout.write("")
        total_artigos = Artigo.objects.filter(eh_legado=True).count()
        total_analises = Analise.objects.filter(status=Analise.Status.LEGADO).count()
        total_users_legado = User.objects.filter(eh_legado=True).count()
        self.stdout.write(f"  Artigos legado no DB:  {total_artigos}")
        self.stdout.write(f"  Análises legado no DB: {total_analises}")
        self.stdout.write(f"  Users legado no DB:    {total_users_legado}")
