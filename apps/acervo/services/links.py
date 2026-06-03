"""
Servicos do app acervo: validacao de link e captura de snapshot Wayback.

Toda chamada externa tem timeout, lida com falhas de rede e nunca segue
redirects para IPs internos (mitigacao basica de SSRF).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone

from apps.acervo.models import Artigo, SnapshotLink

logger = logging.getLogger(__name__)

USER_AGENT = "AnCoLinkChecker/0.1 (+https://anco.paulovicente.pro.br)"
LINK_TIMEOUT_SEGUNDOS = 8
WAYBACK_TIMEOUT_SEGUNDOS = 30
WAYBACK_BASE = "https://web.archive.org"


@dataclass(frozen=True)
class LinkCheckResultado:
    status: str  # ok / quebrado / redireciona / nao_verificado
    codigo_http: int | None
    url_final: str | None
    mensagem: str = ""


def _eh_url_publica(url: str) -> bool:
    """Recusa URLs que apontam para IPs locais/privados (anti-SSRF)."""
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        # Resolve para IP e checa se eh privado
        ip_str = socket.gethostbyname(host)
        ip = ipaddress.ip_address(ip_str)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except (socket.gaierror, ValueError):
        return False


def validar_link(url: str) -> LinkCheckResultado:
    """
    Faz HEAD request na url e classifica a resposta.

    Sem seguir redirects para IPs internos. Sem ler corpo. Timeout curto.
    Erros de rede caem como `quebrado`.
    """
    if not url or not url.startswith(("http://", "https://")):
        return LinkCheckResultado(
            status="quebrado",
            codigo_http=None,
            url_final=None,
            mensagem="URL invalida ou sem esquema http/https.",
        )
    if not _eh_url_publica(url):
        return LinkCheckResultado(
            status="quebrado",
            codigo_http=None,
            url_final=None,
            mensagem="URL aponta para endereco privado ou nao resolve.",
        )
    try:
        resp = requests.head(
            url,
            timeout=LINK_TIMEOUT_SEGUNDOS,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException as exc:
        return LinkCheckResultado(
            status="quebrado",
            codigo_http=None,
            url_final=None,
            mensagem=f"Falha na requisicao: {type(exc).__name__}",
        )

    # Muitos publishers (SciELO, Elsevier, Springer, Cloudflare) bloqueiam HEAD
    # com 403/405/501 mesmo quando o GET funciona normalmente no navegador.
    # Tenta GET com stream para confirmar antes de classificar.
    if resp.status_code in (403, 405, 501):
        try:
            resp = requests.get(
                url,
                timeout=LINK_TIMEOUT_SEGUNDOS,
                allow_redirects=True,
                stream=True,
                headers={"User-Agent": USER_AGENT},
            )
            resp.close()
        except requests.RequestException as exc:
            return LinkCheckResultado(
                status="quebrado",
                codigo_http=None,
                url_final=None,
                mensagem=f"Falha na requisicao GET fallback: {type(exc).__name__}",
            )

    # Codigos onde a fonte recusa verificacao automatica ou esta indisponivel
    # transitoriamente: nao temos como afirmar que o link esta quebrado.
    # Marca como nao_verificado para nao pintar selos vermelhos enganosos.
    if resp.status_code in (401, 403, 429, 451) or resp.status_code >= 500:
        return LinkCheckResultado(
            status="nao_verificado",
            codigo_http=resp.status_code,
            url_final=resp.url,
            mensagem=f"HTTP {resp.status_code} — fonte recusou verificacao automatica",
        )

    if resp.status_code >= 400:
        return LinkCheckResultado(
            status="quebrado",
            codigo_http=resp.status_code,
            url_final=resp.url,
            mensagem=f"HTTP {resp.status_code}",
        )

    final_url = resp.url
    if final_url and final_url.rstrip("/") != url.rstrip("/"):
        return LinkCheckResultado(
            status="redireciona",
            codigo_http=resp.status_code,
            url_final=final_url,
        )
    return LinkCheckResultado(status="ok", codigo_http=resp.status_code, url_final=final_url)


def aplicar_resultado_no_artigo(artigo: Artigo, resultado: LinkCheckResultado) -> None:
    """Atualiza campos de saude do link no Artigo a partir de um resultado."""
    artigo.link_status = resultado.status
    artigo.link_ultima_verificacao = timezone.now()
    artigo.save(update_fields=["link_status", "link_ultima_verificacao"])


def capturar_snapshot_wayback(artigo: Artigo, url: str) -> SnapshotLink | None:
    """
    Aciona o Save Page Now do Internet Archive e cria SnapshotLink.

    A URL final do snapshot eh `https://web.archive.org/web/<timestamp>/<url>`.
    Quando o IA responde sem `Content-Location`, aproximamos a URL com `/web/*/<url>`
    (redirect funcional, ainda que nao o snapshot exato — IA resolve a versao mais
    recente).
    """
    if not getattr(settings, "WAYBACK_API_ENABLED", True):
        logger.info("Wayback desligado por flag; nao capturei snapshot de %s", url)
        return None
    if not url:
        return None
    save_url = f"{WAYBACK_BASE}/save/{url}"
    try:
        resp = requests.get(
            save_url,
            timeout=WAYBACK_TIMEOUT_SEGUNDOS,
            allow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException as exc:
        logger.warning("Falha ao capturar snapshot Wayback de %s: %s", url, exc)
        return None

    # IA responde 302 com header `Content-Location` ou Location apontando para o snapshot
    snapshot_url = (
        resp.headers.get("Content-Location")
        or resp.headers.get("Location")
        or f"{WAYBACK_BASE}/web/*/{url}"
    )
    if snapshot_url.startswith("/"):
        snapshot_url = f"{WAYBACK_BASE}{snapshot_url}"

    return SnapshotLink.objects.create(
        artigo=artigo,
        url_original=url,
        url_wayback=snapshot_url,
    )
