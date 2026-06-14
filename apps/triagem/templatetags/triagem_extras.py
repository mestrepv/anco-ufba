"""Filtros de template da triagem."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def a_analisar_count(user) -> int:
    """Nº de artigos a analisar pendentes do usuário (para o badge do menu).

    Conta os artigos **sorteados** para o usuário que ainda não têm análise
    enviada (submetida/publicada) — ou seja, o trabalho que falta fazer. Zero
    quando não há sorteio para ele. Barato: 2 queries simples.
    """
    if not getattr(user, "is_authenticated", False) or not getattr(user, "eh_analista", False):
        return 0
    from apps.acervo.models import Analise

    from ..models import AtribuicaoAnalise

    atribuidos = set(
        AtribuicaoAnalise.objects.filter(analista=user).values_list("artigo_id", flat=True)
    )
    if not atribuidos:
        return 0
    enviadas = set(
        Analise.objects.filter(
            analista=user,
            artigo_id__in=atribuidos,
            status__in=(Analise.Status.SUBMETIDA, Analise.Status.PUBLICADA),
        ).values_list("artigo_id", flat=True)
    )
    return len(atribuidos - enviadas)


@register.filter
def realce(texto: str, termos_str: str):
    """Destaca (`<mark>`) os `termos` (separados por vírgula) em `texto`.

    Escapa o HTML antes de inserir as marcas — seguro contra XSS.
    """
    texto_esc = escape(texto or "")
    termos = [t.strip() for t in (termos_str or "").split(",") if t.strip()]
    if not termos:
        return mark_safe(texto_esc)
    termos.sort(key=len, reverse=True)  # frases antes de palavras
    padrao = "|".join(re.escape(escape(t)) for t in termos)
    resultado = re.sub(f"({padrao})", r"<mark>\1</mark>", texto_esc, flags=re.IGNORECASE)
    return mark_safe(resultado)
