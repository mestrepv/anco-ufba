"""Views da triagem PRISMA-ScR.

Fase 9.0 — painel placeholder.
Fase 9.2 — importação de arquivos (RIS/BibTeX/CSV) + listagem de registros.
A interface de triagem por revisor (mascarada) e o desempate entram na 9.4.
"""

from __future__ import annotations

import csv
import functools
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import duplicatas as dup
from . import prisma
from .aprovacao import registros_para_desempate
from .forms import DecisaoTriagemForm, DesempateForm, ImportarBuscaForm
from .importacao import (
    decodificar,
    detectar_formato,
    importar_para_busca,
    parse_conteudo,
)
from .models import Busca, DecisaoTriagem, ProtocoloTriagem, RegistroTriagem
from .promocao import promover_para_acervo
from .tasks import iniciar_triagem


def _eh_curador(user) -> bool:
    return bool(user.is_staff or getattr(user, "eh_curador", False))


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


def _exige_curador(view):
    """Exige curador ou admin."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not _eh_curador(request.user):
            return HttpResponseForbidden("Apenas curadores fazem o desempate.")
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
                cd = form.cleaned_data
                busca = Busca(
                    protocolo=protocolo,
                    base_consulta=cd["base_consulta"],
                    outra_base=cd["outra_base"],
                    string_busca=cd["string_busca"],
                    campo_busca=cd["campo_busca"],
                    ano_inicio=cd["ano_inicio"],
                    ano_fim=cd["ano_fim"],
                    idiomas=cd["idiomas"],
                    tipos_documento=cd["tipos_documento"],
                    filtros=cd["filtros"],
                    n_identificados=cd["n_identificados"] or 0,
                    data_busca=cd["data_busca"],
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
                    importar_para_busca(busca, registros)
                    return redirect("triagem_busca_resumo", busca_id=busca.pk)
    else:
        form = ImportarBuscaForm()

    return render(
        request,
        "triagem/importar.html",
        {"form": form, "protocolo": protocolo},
    )


@_exige_analista
def busca_resumo_view(request: HttpRequest, busca_id: int) -> HttpResponse:
    """Resumo da deduplicação de uma busca recém-importada."""
    busca = get_object_or_404(Busca, pk=busca_id)
    registros = (
        busca.registros.select_related("artigo")
        .order_by("ja_no_acervo", "titulo")
    )
    return render(
        request,
        "triagem/busca_resumo.html",
        {"busca": busca, "registros": registros},
    )


@_exige_analista
def registros_view(request: HttpRequest) -> HttpResponse:
    protocolo = ProtocoloTriagem.ativo()
    qs = protocolo.registros.select_related("artigo").all()

    status = request.GET.get("status", "")
    if status in dict(RegistroTriagem.Status.choices):
        qs = qs.filter(status=status)

    pagina = Paginator(qs, 50).get_page(request.GET.get("page"))
    n_identificados = protocolo.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    ).count()
    contexto = {
        "protocolo": protocolo,
        "pagina": pagina,
        "status_atual": status,
        "status_choices": RegistroTriagem.Status.choices,
        "n_para_triar": n_identificados,
        "pode_curar": _eh_curador(request.user),
    }
    return render(request, "triagem/registros.html", contexto)


@_exige_analista
def duplicatas_view(request: HttpRequest) -> HttpResponse:
    """Revisão de possíveis duplicatas por similaridade de título."""
    protocolo = ProtocoloTriagem.ativo()
    pares = dup.pares_possiveis(protocolo)
    return render(request, "triagem/duplicatas.html", {"pares": pares})


def _par_do_post(request) -> tuple[RegistroTriagem, RegistroTriagem]:
    a = get_object_or_404(RegistroTriagem, pk=request.POST.get("a"))
    b = get_object_or_404(RegistroTriagem, pk=request.POST.get("b"))
    return a, b


@_exige_analista
@require_POST
def mesclar_duplicata_view(request: HttpRequest) -> HttpResponse:
    a, b = _par_do_post(request)
    # canônico = menor pk (mantém o mais antigo); o outro vira duplicado.
    canonico, duplicado = (a, b) if a.pk < b.pk else (b, a)
    dup.mesclar(canonico, duplicado)
    messages.success(request, "Registros mesclados (duplicata marcada).")
    return redirect("triagem_duplicatas")


@_exige_analista
@require_POST
def descartar_duplicata_view(request: HttpRequest) -> HttpResponse:
    a, b = _par_do_post(request)
    dup.descartar(a, b)
    messages.info(request, "Par marcado como não duplicata.")
    return redirect("triagem_duplicatas")


@_exige_curador
def iniciar_triagem_view(request: HttpRequest) -> HttpResponse:
    """Curador fecha a coleta e dispara o sorteio dos identificados.

    GET: confirmação (quantos serão sorteados). POST: enfileira o sorteio.
    """
    protocolo = ProtocoloTriagem.ativo()
    n_disponiveis = protocolo.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    ).count()

    if request.method == "POST":
        n = iniciar_triagem(protocolo)
        if n:
            messages.success(request, f"Triagem iniciada para {n} registro(s).")
        else:
            messages.info(request, "Nenhum registro identificado disponível para triar.")
        return redirect("triagem_registros")

    return render(
        request,
        "triagem/iniciar_confirma.html",
        {"protocolo": protocolo, "n_disponiveis": n_disponiveis},
    )


@_exige_analista
def minhas_triagens_view(request: HttpRequest) -> HttpResponse:
    pendentes = (
        DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=True)
        .select_related("registro")
        .order_by("prazo_em")
    )
    concluidas = (
        DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=False)
        .select_related("registro")
        .order_by("-concluido_em")[:20]
    )
    return render(
        request,
        "triagem/minhas_triagens.html",
        {"pendentes": pendentes, "concluidas": concluidas},
    )


@_exige_analista
def triar_view(request: HttpRequest, decisao_id: int) -> HttpResponse:
    """Interface de triagem mascarada: o revisor vê só os metadados do registro."""
    decisao = get_object_or_404(
        DecisaoTriagem.objects.select_related("registro"), pk=decisao_id
    )
    if decisao.revisor_id != request.user.id:
        return HttpResponseForbidden("Esta triagem não é sua.")
    if decisao.concluido_em is not None:
        messages.info(request, "Você já concluiu esta triagem.")
        return redirect("triagem_minhas")

    registro = decisao.registro
    if request.method == "POST":
        form = DecisaoTriagemForm(request.POST)
        if form.is_valid():
            decisao.decisao = form.cleaned_data["decisao"]
            decisao.motivo_exclusao = form.cleaned_data["motivo_exclusao"]
            decisao.comentario = form.cleaned_data["comentario"]
            decisao.concluido_em = timezone.now()
            decisao.save()  # signal dispara a avaliação
            messages.success(request, "Decisão registrada. Obrigado!")
            return redirect("triagem_minhas")
    else:
        form = DecisaoTriagemForm()

    # Mascarado: nenhuma informação sobre coletor ou outros revisores.
    return render(
        request,
        "triagem/triar.html",
        {"decisao": decisao, "registro": registro, "form": form},
    )


@_exige_curador
def fila_desempate_view(request: HttpRequest) -> HttpResponse:
    protocolo = ProtocoloTriagem.ativo()
    registros = registros_para_desempate(protocolo)
    return render(
        request, "triagem/desempate_fila.html",
        {"registros": registros, "protocolo": protocolo},
    )


@_exige_curador
def desempatar_view(request: HttpRequest, registro_id: int) -> HttpResponse:
    registro = get_object_or_404(RegistroTriagem, pk=registro_id)
    decisoes = registro.decisoes.select_related("revisor").all()

    if request.method == "POST":
        form = DesempateForm(request.POST)
        if form.is_valid():
            escolha = form.cleaned_data["decisao"]
            if escolha == RegistroTriagem.Decisao.INCLUIR:
                registro.status = RegistroTriagem.Status.INCLUIDO
            else:
                registro.status = RegistroTriagem.Status.EXCLUIDO
                registro.motivo_exclusao = form.cleaned_data["motivo_exclusao"]
            registro.decisao_final = escolha
            registro.decidida_por = request.user
            registro.decidida_em = timezone.now()
            registro.save()
            if registro.status == RegistroTriagem.Status.INCLUIDO:
                promover_para_acervo(registro)
            messages.success(request, "Desempate registrado.")
            return redirect("triagem_desempate")
    else:
        form = DesempateForm()

    return render(
        request,
        "triagem/desempate.html",
        {"registro": registro, "decisoes": decisoes, "form": form},
    )


@_exige_analista
def ajuda_view(request: HttpRequest) -> HttpResponse:
    """Como funciona a triagem: protocolo, fluxo e papéis (página de apoio)."""
    return render(
        request, "triagem/ajuda.html", {"protocolo": ProtocoloTriagem.ativo()}
    )


@_exige_analista
def a_analisar_view(request: HttpRequest) -> HttpResponse:
    """Artigos incluídos pela triagem que o usuário ainda não analisou."""
    from apps.acervo.models import Analise, Artigo

    minhas = Analise.objects.filter(analista=request.user).values_list(
        "artigo_id", flat=True
    )
    artigos = (
        Artigo.objects.filter(
            registros_triagem__status=RegistroTriagem.Status.INCLUIDO
        )
        .exclude(pk__in=minhas)
        .distinct()
        .order_by("-ano", "titulo")
    )
    pagina = Paginator(artigos, 50).get_page(request.GET.get("page"))
    return render(request, "triagem/a_analisar.html", {"pagina": pagina})


@_exige_analista
def prisma_view(request: HttpRequest) -> HttpResponse:
    """Fluxograma PRISMA-ScR (contagens) + export CSV/JSON."""
    protocolo = ProtocoloTriagem.ativo()
    contagem = prisma.computar(protocolo)
    formato = request.GET.get("formato")

    if formato == "json":
        return JsonResponse(contagem.como_dict())

    if formato == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="prisma_anco.csv"'
        escritor = csv.writer(resp)
        escritor.writerow(["etapa", "n"])
        for chave, valor in contagem.como_dict().items():
            if chave in ("excluidos_por_motivo",):
                continue
            escritor.writerow([chave, valor])
        for item in contagem.excluidos_por_motivo:
            escritor.writerow([f"excluido: {item['motivo_exclusao']}", item["n"]])
        return resp

    return render(
        request,
        "triagem/prisma.html",
        {"protocolo": protocolo, "c": contagem, "json": json.dumps(contagem.como_dict())},
    )
