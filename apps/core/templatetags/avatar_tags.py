"""Template tags para renderizar avatar do usuário.

Prioridade: foto local (upload) > foto do Google (OAuth) > iniciais.
"""

from __future__ import annotations

from django import template

register = template.Library()


def _foto_google(user) -> str:
    """Lê a URL da foto do Google armazenada na SocialAccount, se existir."""
    if not user.is_authenticated:
        return ""
    try:
        # Import local para não acoplar carregamento do app a allauth
        from allauth.socialaccount.models import SocialAccount

        sa = SocialAccount.objects.filter(user=user, provider="google").first()
        if sa and sa.extra_data:
            return sa.extra_data.get("picture") or ""
    except Exception:
        return ""
    return ""


@register.filter
def split(value: str, sep: str = ";"):
    """Filtro `{{ valor|split:";" }}` — útil para listas separadas por delimitador."""
    if not value:
        return []
    return [p.strip() for p in str(value).split(sep) if p.strip()]


@register.inclusion_tag("partials/_avatar.html")
def avatar(user, size: int = 28):
    """Renderiza o avatar inline. `size` em pixels (default 28)."""
    foto_url = ""
    if user.is_authenticated:
        if user.foto:
            foto_url = user.foto.url
        else:
            foto_url = _foto_google(user)
    iniciais = user.iniciais if user.is_authenticated else "?"
    # Fonte das iniciais proporcional ao avatar
    font_size = max(10, int(size * 0.42))
    return {
        "foto_url": foto_url,
        "iniciais": iniciais,
        "size": size,
        "font_size": font_size,
    }
