"""Filtros de template da triagem."""

from __future__ import annotations

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


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
