"""Views da triagem PRISMA-ScR.

Fase 9.0 — painel placeholder.
Fase 9.2 — importação de arquivos (RIS/BibTeX/CSV) + listagem de registros.
A interface de triagem por revisor (mascarada) e o desempate entram na 9.4.
"""

from __future__ import annotations

import functools

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render

from .forms import ImportarBuscaForm
from .importacao import (
    decodificar,
    detectar_formato,
    importar_para_busca,
    parse_conteudo,
)
from .models import Busca, ProtocoloTriagem, RegistroTriagem


def _exige_analista(view):
    """Exige usuário autenticado com papel analista ou curador."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not getattr(request.user, "eh_analista", False):
            return HttpResponseForbidden(
                "Apenas analistas ou curadores acessam a triagem."
            )
        return view(request, *args, **kwargs)

    return wrapper


@_exige_analista
def painel_view(request: HttpRequest) -> HttpResponse:
    protocolo = ProtocoloTriagem.ativo()
    cards = [
        {
            "codigo": codigo,
            "rotulo": rotulo,
            "count": protocolo.registros.filter(status=codigo).count(),
        }
        for codigo, rotulo in RegistroTriagem.Status.choices
    ]
    contexto = {
        "protocolo": protocolo,
        "buscas": protocolo.buscas.all()[:20],
        "n_buscas": protocolo.buscas.count(),
        "cards": cards,
        "n_registros": protocolo.registros.count(),
    }
    return render(request, "triagem/painel.html", contexto)


@_exige_analista
def importar_view(request: HttpRequest) -> HttpResponse:
    protocolo = ProtocoloTriagem.ativo()
    resultado = None

    if request.method == "POST":
        form = ImportarBuscaForm(request.POST, request.FILES)
        if form.is_valid():
            enviado = form.cleaned_data["arquivo"]
            formato = form.cleaned_data["formato"] or detectar_formato(enviado.name)
            if not formato:
                form.add_error(
                    "arquivo",
                    "Não reconheci o formato pela extensão; escolha um em 'Formato'.",
                )
            else:
                raw = enviado.read()
                enviado.seek(0)
                busca = Busca(
                    protocolo=protocolo,
                    base_consulta=form.cleaned_data["base_consulta"],
                    outra_base=form.cleaned_data["outra_base"],
                    string_busca=form.cleaned_data["string_busca"],
                    n_identificados=form.cleaned_data["n_identificados"] or 0,
                    data_busca=form.cleaned_data["data_busca"],
                    formato=formato,
                    arquivo=enviado,
                    criado_por=request.user,
                )
                busca.save()
                try:
                    registros = parse_conteudo(decodificar(raw), formato)
                except Exception as exc:  # noqa: BLE001 — erro de parsing vira mensagem
                    busca.delete()
                    form.add_error("arquivo", f"Falha ao ler o arquivo: {exc}")
                else:
                    resultado = importar_para_busca(busca, registros)
                    messages.success(
                        request,
                        f"Busca #{busca.pk} ({busca.base_nome}): {resultado.criados} "
                        f"novos, {resultado.duplicados} duplicados, "
                        f"{resultado.ja_no_acervo} já no acervo.",
                    )
                    return redirect("triagem_registros")
    else:
        form = ImportarBuscaForm()

    return render(
        request,
        "triagem/importar.html",
        {"form": form, "protocolo": protocolo, "resultado": resultado},
    )


@_exige_analista
def registros_view(request: HttpRequest) -> HttpResponse:
    protocolo = ProtocoloTriagem.ativo()
    qs = protocolo.registros.select_related("artigo").all()

    status = request.GET.get("status", "")
    if status in dict(RegistroTriagem.Status.choices):
        qs = qs.filter(status=status)

    pagina = Paginator(qs, 50).get_page(request.GET.get("page"))
    contexto = {
        "protocolo": protocolo,
        "pagina": pagina,
        "status_atual": status,
        "status_choices": RegistroTriagem.Status.choices,
    }
    return render(request, "triagem/registros.html", contexto)
