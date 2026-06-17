"""
Servicos do app publico:

- Conversao DOI <-> slug citavel (URL-safe, deterministica e reversivel).
- Geracao de citacoes ABNT e APA a partir dos metadados de Artigo + Analise.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings

# ---------------------------------------------------------------------------
# DOI <-> slug
# ---------------------------------------------------------------------------
#
# Estrategia:
# - DOIs canonicos (10.xxxx/yyy) trocam '/' por '__' (raro em DOIs reais).
# - IDs do legado (legacy:HASH) trocam ':' por '__'.
# - Demais caracteres seguros sao mantidos. Espacos viram '-'.
# - A funcao reversa funciona em ambos os formatos. Conversao eh determinada
#   pela presenca de '__' que separa o prefixo do sufixo.


_SUBST = "__"


def doi_to_slug(doi: str) -> str:
    """
    Converte DOI/identificador interno em slug seguro para URL.

    >>> doi_to_slug("10.1234/abc.456")
    '10.1234__abc.456'
    >>> doi_to_slug("legacy:abcdef0123456789")
    'legacy__abcdef0123456789'
    """
    if not doi:
        return ""
    s = str(doi).strip()
    s = s.replace("/", _SUBST).replace(":", _SUBST)
    s = s.replace(" ", "-")
    return s


def slug_to_doi(slug: str) -> str:
    """
    Inverte `doi_to_slug`. Nao consulta o banco — apenas a heuristica:
    repoe '/' para DOIs (10.xxxx) e ':' para legacy.

    >>> slug_to_doi("10.1234__abc.456")
    '10.1234/abc.456'
    >>> slug_to_doi("10.54103__2037-3597__29116")
    '10.54103/2037-3597/29116'
    >>> slug_to_doi("legacy__abcdef")
    'legacy:abcdef'
    """
    if not slug:
        return ""
    s = str(slug).strip()
    if s.startswith("legacy" + _SUBST):
        # legacy__HASH -> legacy:HASH (só o prefixo)
        return s.replace(_SUBST, ":", 1)
    # DOI canonico: repõe TODAS as barras (doi_to_slug troca toda '/' por '__';
    # DOIs com >1 barra, ex. 10.x/a/b, exigem reverter todas).
    return s.replace(_SUBST, "/")


# ---------------------------------------------------------------------------
# Citacoes
# ---------------------------------------------------------------------------


def _formatar_autores_abnt(autores: str) -> str:
    """
    Formata uma string de autores para citacao ABNT (sobrenome em
    maiusculas, demais nomes abreviados).

    Aceita string solta (separada por ';' ou ',') do legado.
    """
    if not autores:
        return ""
    autores = autores.strip()
    # Separadores comuns no legado: ';', ' e ', ' & '
    for sep in [";", " and ", " e ", " & "]:
        if sep in autores:
            partes = [p.strip() for p in autores.split(sep) if p.strip()]
            return "; ".join(_um_autor_abnt(p) for p in partes)
    return _um_autor_abnt(autores)


_PREPOSICOES = {"da", "de", "do", "das", "dos", "e", "del", "von", "van"}


def _um_autor_abnt(nome: str) -> str:
    """Converte 'Maria da Silva' em 'SILVA, M. da' (preposicoes preservadas)."""
    nome = nome.strip()
    if not nome:
        return ""
    if "," in nome:
        sobrenome, *resto = nome.split(",", 1)
        return f"{sobrenome.strip().upper()}, {resto[0].strip() if resto else ''}".rstrip(", ")
    partes = nome.split()
    if len(partes) == 1:
        return partes[0].upper()
    sobrenome = partes[-1]
    iniciais = []
    for p in partes[:-1]:
        if not p:
            continue
        if p.lower() in _PREPOSICOES:
            iniciais.append(p.lower())  # preserva preposicao
        else:
            iniciais.append(f"{p[0].upper()}.")
    return f"{sobrenome.upper()}, {' '.join(iniciais)}"


def _formatar_autores_apa(autores: str) -> str:
    """APA usa 'Sobrenome, N.' separado por '&'."""
    if not autores:
        return ""
    for sep in [";", " and ", " e ", " & "]:
        if sep in autores:
            partes = [p.strip() for p in autores.split(sep) if p.strip()]
            formatados = [_um_autor_apa(p) for p in partes]
            if len(formatados) == 1:
                return formatados[0]
            return ", ".join(formatados[:-1]) + ", & " + formatados[-1]
    return _um_autor_apa(autores)


def _um_autor_apa(nome: str) -> str:
    nome = nome.strip()
    if not nome:
        return ""
    if "," in nome:
        sobrenome, *resto = nome.split(",", 1)
        return f"{sobrenome.strip()}, {resto[0].strip() if resto else ''}".rstrip(", ")
    partes = nome.split()
    if len(partes) == 1:
        return partes[0]
    sobrenome = partes[-1]
    iniciais = []
    for p in partes[:-1]:
        if not p:
            continue
        if p.lower() in _PREPOSICOES:
            iniciais.append(p.lower())
        else:
            iniciais.append(f"{p[0].upper()}.")
    return f"{sobrenome}, {' '.join(iniciais)}"


def gerar_citacao_abnt(analise) -> str:
    """
    Gera citacao da analise no estilo ABNT 6023:2018 (simplificada).

    Formato:
    SOBRENOME, N. *Análise cognitiva: <título do artigo>*. AnCo: Plataforma
    de Análise Cognitiva, <ano de publicação>. Disponível em: <URL>.
    Acesso em: <data atual>.
    """
    autor = analise.analista
    nome_autor = autor.nome_exibicao or autor.get_full_name() or autor.username
    autor_fmt = _um_autor_abnt(nome_autor)
    titulo = (analise.artigo.titulo or "(sem título)").strip()
    ano_pub = analise.publicada_em.year if analise.publicada_em else analise.criado_em.year
    url_base = getattr(settings, "URL_PUBLICA_CITAVEL", settings.BASE_URL).rstrip("/")
    url = f"{url_base}/analise/{analise.pk}/"
    hoje = date.today().strftime("%d %b. %Y").lower()
    return (
        f"{autor_fmt}. *Análise cognitiva: {titulo}*. "
        f"AnCo: Plataforma de Análise Cognitiva, {ano_pub}. "
        f"Disponível em: {url}. Acesso em: {hoje}."
    )


def gerar_citacao_apa(analise) -> str:
    """
    Gera citacao no estilo APA 7th edition (simplificada).

    Formato:
    Sobrenome, N. (<ano>). Análise cognitiva: <título>. AnCo. <URL>
    """
    autor = analise.analista
    nome_autor = autor.nome_exibicao or autor.get_full_name() or autor.username
    autor_fmt = _um_autor_apa(nome_autor)
    titulo = (analise.artigo.titulo or "(sem título)").strip()
    ano_pub = analise.publicada_em.year if analise.publicada_em else analise.criado_em.year
    url_base = getattr(settings, "URL_PUBLICA_CITAVEL", settings.BASE_URL).rstrip("/")
    url = f"{url_base}/analise/{analise.pk}/"
    return f"{autor_fmt} ({ano_pub}). Análise cognitiva: {titulo}. AnCo. {url}"
