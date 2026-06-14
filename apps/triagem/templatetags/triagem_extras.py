"""Filtros de template da triagem."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def a_analisar_count(user) -> int:
    """Nº de artigos a analisar pendentes do usuário (badge do menu): incluídos
    pela triagem que o usuário ainda não analisou."""
    if not getattr(user, "is_authenticated", False) or not getattr(user, "eh_analista", False):
        return 0
    from apps.acervo.models import Analise, Artigo

    from ..models import RegistroTriagem

    ja = Analise.objects.filter(analista=user).values_list("artigo_id", flat=True)
    return (
        Artigo.objects.filter(registros_triagem__status=RegistroTriagem.Status.INCLUIDO)
        .exclude(pk__in=ja)
        .distinct()
        .count()
    )


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
