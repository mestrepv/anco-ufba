"""Views da triagem PRISMA-ScR.

Fase 9 — importação, triagem mascarada, desempate, PRISMA.
Fase 12 — **projetos**: as views da triagem são escopadas por projeto na URL
(`/triagem/p/<slug>/...`); o acesso exige ser **membro** do projeto. As views de
trabalho do revisor (minhas/triar/a-analisar) e a lista de projetos são globais.
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
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import duplicatas as dup
from . import prisma
from .aprovacao import consolidar_registro, registros_para_desempate
from .autotriagem import (
    autotriar,
    desfazer_autotriagem,
    pode_autotriar,
    registros_decididos_do_usuario,
    registros_para_autotriar,
    reverter_inclusao,
)
from .forms import DecisaoTriagemForm, DesempateForm, ImportarBuscaForm
from .importacao import (
    busca_pode_excluir,
    decodificar,
    detectar_formato,
    excluir_busca,
    importar_para_busca,
    parse_conteudo,
)
from .models import (
    AtribuicaoAnalise,
    Busca,
    ConsensoAnalise,
    DecisaoTriagem,
    ProjetoMembro,
    ProtocoloTriagem,
    RegistroTriagem,
    SorteioAnalise,
)
from .relevancia import termos_do_protocolo
from .sorteio_analise import analistas_do_projeto, executar_sorteio_analise
from .tasks import avancar_apos_status, iniciar_triagem


def _eh_curador(user) -> bool:
    return bool(user.is_staff or getattr(user, "eh_curador", False))


def _pode_resolver_par(projeto, user, *registros) -> bool:
    """Regra de dedup (Fase 12.4): curador do projeto resolve qualquer par;
    o analista membro resolve apenas pares que tocam **bases que ele importou**.
    """
    if projeto.eh_curador_no(user):
        return True
    donos = set()
    for r in registros:
        donos |= dup.importadores(r)
    return user.id in donos


def projetos_do_usuario(user):
    """Projetos não arquivados visíveis ao usuário (membro; admin vê todos)."""
    qs = ProtocoloTriagem.objects.filter(arquivado=False)
    if user.is_staff:
        return qs.order_by("nome")
    return qs.filter(membros__usuario=user).distinct().order_by("nome")


def _exige_analista(view):
    """Exige usuário autenticado com papel analista ou curador (rotas globais)."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not getattr(request.user, "eh_analista", False):
            return HttpResponseForbidden("Apenas analistas ou curadores acessam a triagem.")
        return view(request, *args, **kwargs)

    return wrapper


def _projeto_analista(view):
    """Resolve o projeto pelo slug e exige que o usuário seja **membro** dele."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
        if not getattr(request.user, "eh_analista", False):
            return HttpResponseForbidden("Apenas analistas ou curadores acessam a triagem.")
        projeto = get_object_or_404(ProtocoloTriagem, slug=slug)
        if not (request.user.is_staff or projeto.eh_membro(request.user)):
            return HttpResponseForbidden("Você não é membro deste projeto.")
        return view(request, projeto, *args, **kwargs)

    return wrapper


def _projeto_curador(view):
    """Resolve o projeto pelo slug e exige curador **do projeto** (ou admin)."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
        projeto = get_object_or_404(ProtocoloTriagem, slug=slug)
        if not projeto.eh_curador_no(request.user):
            return HttpResponseForbidden("Apenas curadores deste projeto.")
        return view(request, projeto, *args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------- #
# Projetos (lista + criação)
# --------------------------------------------------------------------------- #


@_exige_analista
def projetos_view(request: HttpRequest) -> HttpResponse:
    """Lista os projetos do usuário (porta de entrada da triagem)."""
    projetos = list(projetos_do_usuario(request.user))
    dados = []
    for p in projetos:
        dados.append(
            {
                "projeto": p,
                "n_registros": p.registros.count(),
                "n_buscas": p.buscas.count(),
                "eh_curador": p.eh_curador_no(request.user),
            }
        )
    return render(
        request,
        "triagem/projetos.html",
        {"projetos": dados, "pode_criar": request.user.is_staff},
    )


@_exige_analista
def novo_projeto_view(request: HttpRequest) -> HttpResponse:
    """Cria um novo projeto (revisão de escopo). Exclusivo de admin (Fase 12.3)."""
    if not request.user.is_staff:
        return HttpResponseForbidden("Apenas o admin cria projetos.")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        if not nome:
            messages.error(request, "Informe um nome para o projeto.")
            return redirect("triagem_novo_projeto")
        projeto = ProtocoloTriagem.objects.create(
            nome=nome,
            titulo=nome,
            pergunta_pesquisa=request.POST.get("pergunta_pesquisa", "").strip(),
            estrategia_busca=request.POST.get("estrategia_busca", "").strip(),
        )
        # O criador entra como curador do projeto.
        ProjetoMembro.objects.get_or_create(
            projeto=projeto,
            usuario=request.user,
            defaults={"papel": ProjetoMembro.Papel.CURADOR},
        )
        messages.success(request, f"Projeto “{projeto.nome}” criado.")
        return redirect("triagem_painel", slug=projeto.slug)

    return render(request, "triagem/novo_projeto.html", {})


# --------------------------------------------------------------------------- #
# Painel e fluxo do projeto
# --------------------------------------------------------------------------- #


@_projeto_analista
def painel_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    from django.db.models import Count

    from . import concordancia as conc

    # Só os status com registros (não polui com zeros).
    contagens = dict(projeto.registros.values_list("status").annotate(n=Count("id")))
    _reg_url = reverse("triagem_registros", args=[projeto.slug])
    _St = RegistroTriagem.Status
    eh_curador = projeto.eh_curador_no(request.user)

    buscas = projeto.buscas.select_related("criado_por", "base_consulta").order_by(
        "-importado_em", "-criado_em"
    )[:50]
    membros = projeto.membros.select_related("usuario").order_by("-papel", "usuario__nome_exibicao")
    contexto = {
        "projeto": projeto,
        "protocolo": projeto,
        "buscas": buscas,
        "n_buscas": projeto.buscas.count(),
        "n_registros": projeto.registros.count(),
        "eh_curador": eh_curador,
        "membros": membros,
        "n_membros": membros.count(),
        "c": prisma.computar(projeto),
        "acordo": conc.calcular(projeto),
    }

    if projeto.eh_anco:
        # Dois painéis: "Meu trabalho" (analista, escopo das próprias bases) e
        # "Curadoria" (visão do projeto inteiro). Não misturar.
        aba = request.GET.get("aba", "trabalho")
        if aba != "curadoria" or not eh_curador:
            aba = "trabalho"
        au = reverse("triagem_autotriar", args=[projeto.slug])

        # — Painel do analista (escopo = minhas) —
        meu_a_triar = registros_para_autotriar(projeto, request.user, "minhas").count()
        meu_inc = registros_decididos_do_usuario(
            projeto, request.user, (_St.INCLUIDO,), "minhas"
        ).count()
        meu_exc = registros_decididos_do_usuario(
            projeto, request.user, (_St.EXCLUIDO,), "minhas"
        ).count()
        from apps.acervo.models import Analise, Artigo

        ja_minhas = Analise.objects.filter(analista=request.user).values_list(
            "artigo_id", flat=True
        )
        atribuidos = list(
            AtribuicaoAnalise.objects.filter(
                analista=request.user, sorteio__projeto=projeto
            ).values_list("artigo_id", flat=True)
        )
        minha_a_analisar = (
            Artigo.objects.filter(pk__in=atribuidos).exclude(pk__in=ja_minhas).distinct().count()
            if atribuidos
            else 0
        )
        contexto["cards_trabalho"] = [
            {
                "rotulo": "A triar",
                "count": meu_a_triar,
                "href": f"{au}?escopo=minhas&lista=pendentes&i=0",
            },
            {
                "rotulo": "Incluídos",
                "count": meu_inc,
                "href": f"{au}?escopo=minhas&lista=incluidos&i=0",
            },
            {
                "rotulo": "Excluídos",
                "count": meu_exc,
                "href": f"{au}?escopo=minhas&lista=excluidos&i=0",
            },
            {
                "rotulo": "A analisar",
                "count": minha_a_analisar,
                "href": reverse("triagem_a_analisar"),
            },
        ]
        contexto["minha_dup"] = dup.contar_pares_do_usuario(projeto, request.user, False)

        # — Painel de curadoria (projeto inteiro) —
        a_triar_todas = projeto.registros.filter(
            status=_St.IDENTIFICADO, ja_no_acervo=False
        ).count()
        isentos = projeto.registros.filter(ja_no_acervo=True).count()
        brutos = [
            ("Importados", projeto.registros.count(), _reg_url),
            ("A triar", a_triar_todas, f"{au}?escopo=todas&lista=pendentes&i=0"),
            ("Já no acervo (isentos)", isentos, f"{_reg_url}?status=identificado"),
            (
                "Incluído",
                contagens.get(_St.INCLUIDO, 0),
                reverse("triagem_incluidos", args=[projeto.slug]),
            ),
            ("Excluído", contagens.get(_St.EXCLUIDO, 0), f"{_reg_url}?status=excluido"),
        ]
        # Grid do painel de curadoria (o de "Meu trabalho" usa cards_trabalho).
        contexto["cards"] = [
            {"rotulo": r, "count": n, "href": h} for r, n, h in brutos if n
        ]
        contexto["aba"] = aba
        return render(request, "triagem/painel.html", contexto)

    # Modo rigoroso (PRISMA-ScR): painel único por status.
    contexto["cards"] = [
        {
            "rotulo": rotulo,
            "count": contagens.get(codigo, 0),
            "href": f"{_reg_url}?status={codigo}",
        }
        for codigo, rotulo in RegistroTriagem.Status.choices
        if contagens.get(codigo, 0)
    ]
    return render(request, "triagem/painel.html", contexto)


@_projeto_analista
def importar_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
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
                    protocolo=projeto,
                    base_consulta=cd["base_consulta"],
                    outra_base=cd["outra_base"],
                    string_busca=cd["string_busca"],
                    campos_busca=cd["campos_busca"],
                    ano_inicio=cd["ano_inicio"],
                    ano_fim=cd["ano_fim"],
                    idiomas=cd["idiomas"],
                    idioma_outro=cd["idioma_outro"],
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
                    return redirect("triagem_busca_resumo", slug=projeto.slug, busca_id=busca.pk)
    else:
        form = ImportarBuscaForm()

    import datetime

    return render(
        request,
        "triagem/importar.html",
        {
            "form": form,
            "projeto": projeto,
            "protocolo": projeto,
            "ano_min": 2000,
            "ano_max": datetime.date.today().year,
            "ano_range": datetime.date.today().year - 2000,
        },
    )


@_projeto_analista
def busca_resumo_view(
    request: HttpRequest, projeto: ProtocoloTriagem, busca_id: int
) -> HttpResponse:
    """Detalhe de uma importação: comparação com o acervo + gestão."""
    from apps.publico.services import doi_to_slug

    busca = get_object_or_404(Busca, pk=busca_id, protocolo=projeto)
    registros = list(busca.registros.select_related("artigo").order_by("titulo"))
    ja_acervo = [
        {"reg": r, "slug": doi_to_slug(r.artigo.identificador_canonico) if r.artigo else ""}
        for r in registros
        if r.ja_no_acervo
    ]
    novos = [r for r in registros if not r.ja_no_acervo]
    pode_excluir, motivo_bloqueio = busca_pode_excluir(busca)
    # Só o importador (ou o curador) gerencia/exclui a própria importação.
    pode_gerenciar = busca.criado_por_id == request.user.id or projeto.eh_curador_no(request.user)
    return render(
        request,
        "triagem/busca_resumo.html",
        {
            "projeto": projeto,
            "busca": busca,
            "ja_acervo": ja_acervo,
            "novos": novos,
            "n_ja_acervo": len(ja_acervo),
            "n_novos": len(novos),
            "pode_excluir": pode_excluir,
            "motivo_bloqueio": motivo_bloqueio,
            "pode_gerenciar": pode_gerenciar,
        },
    )


@_projeto_analista
@require_POST
def excluir_busca_view(
    request: HttpRequest, projeto: ProtocoloTriagem, busca_id: int
) -> HttpResponse:
    """Exclui uma importação e seus registros intocados (para reimportar)."""
    busca = get_object_or_404(Busca, pk=busca_id, protocolo=projeto)
    if not (busca.criado_por_id == request.user.id or projeto.eh_curador_no(request.user)):
        return HttpResponseForbidden(
            "Só quem importou (ou o curador) pode excluir esta importação."
        )
    ok, motivo = excluir_busca(busca)
    if ok:
        messages.success(request, "Importação excluída. Você pode importar de novo.")
        return redirect("triagem_painel", slug=projeto.slug)
    messages.error(request, motivo)
    return redirect("triagem_busca_resumo", slug=projeto.slug, busca_id=busca_id)


@_projeto_analista
def registros_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    qs = projeto.registros.select_related("artigo").all()

    status = request.GET.get("status", "")
    if status in dict(RegistroTriagem.Status.choices):
        qs = qs.filter(status=status)

    pagina = Paginator(qs, 50).get_page(request.GET.get("page"))
    n_identificados = projeto.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    ).count()
    contexto = {
        "projeto": projeto,
        "protocolo": projeto,
        "pagina": pagina,
        "status_atual": status,
        "status_choices": RegistroTriagem.Status.choices,
        "n_para_triar": n_identificados,
        "pode_curar": projeto.eh_curador_no(request.user),
    }
    return render(request, "triagem/registros.html", contexto)


@_projeto_analista
def duplicatas_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Revisão de possíveis duplicatas — um par por vez, navegável.

    O curador vê todos os pares; o analista membro vê só os que tocam bases que
    importou (Fase 12.4).
    """
    eh_curador = projeto.eh_curador_no(request.user)
    pares = dup.pares_do_usuario(projeto, request.user, eh_curador)
    n = len(pares)

    try:
        i = int(request.GET.get("i", 0))
    except (TypeError, ValueError):
        i = 0
    i = max(0, min(i, n - 1)) if n else 0
    par = pares[i] if n else None

    comparacao = None
    if par:
        a, b = par["a"], par["b"]
        mesmo_ano = dup.mesmo_ano(a, b)
        mesmo_autor = dup.mesmo_primeiro_autor(a.autores, b.autores)
        comparacao = {
            "mesmo_ano": mesmo_ano,
            "mesmo_autor": mesmo_autor,
            "autor_a": dup.primeiro_autor(a.autores),
            "autor_b": dup.primeiro_autor(b.autores),
            "provavel_distinto": (a.ano and b.ano and not mesmo_ano and not mesmo_autor),
        }

    return render(
        request,
        "triagem/duplicatas.html",
        {
            "projeto": projeto,
            "par": par,
            "comp": comparacao,
            "total": n,
            "i": i,
            "tem_anterior": i > 0,
            "tem_proximo": i < n - 1,
            "eh_curador": eh_curador,
        },
    )


def _voltar_duplicatas(request, projeto) -> str:
    i = request.POST.get("i", "0")
    return f"{reverse('triagem_duplicatas', args=[projeto.slug])}?i={i}"


@_projeto_analista
@require_POST
def mesclar_duplicata_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """'Selecionar este': mantém `manter`, marca o outro como duplicata dele."""
    manter = get_object_or_404(RegistroTriagem, pk=request.POST.get("manter"), protocolo=projeto)
    duplicado = get_object_or_404(
        RegistroTriagem, pk=request.POST.get("duplicado"), protocolo=projeto
    )
    if not _pode_resolver_par(projeto, request.user, manter, duplicado):
        return HttpResponseForbidden(
            "Apenas quem importou uma das bases (ou o curador) resolve este par."
        )
    dup.mesclar(manter, duplicado, por=request.user)
    messages.success(request, "Duplicata resolvida — mantido o registro selecionado.")
    return redirect(_voltar_duplicatas(request, projeto))


@_projeto_analista
@require_POST
def descartar_duplicata_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    a = get_object_or_404(RegistroTriagem, pk=request.POST.get("a"), protocolo=projeto)
    b = get_object_or_404(RegistroTriagem, pk=request.POST.get("b"), protocolo=projeto)
    if not _pode_resolver_par(projeto, request.user, a, b):
        return HttpResponseForbidden(
            "Apenas quem importou uma das bases (ou o curador) resolve este par."
        )
    dup.descartar(a, b, por=request.user)
    messages.info(request, "Par marcado como não duplicata.")
    return redirect(_voltar_duplicatas(request, projeto))


@_projeto_analista
def duplicatas_mescladas_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Lista os registros já mesclados como duplicata (auditoria + desfazer)."""
    return render(
        request,
        "triagem/duplicatas_mescladas.html",
        {"projeto": projeto, "mescladas": dup.mescladas(projeto)},
    )


@_projeto_analista
@require_POST
def desfazer_mescla_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    duplicado = get_object_or_404(
        RegistroTriagem, pk=request.POST.get("duplicado"), protocolo=projeto
    )
    alvos = [duplicado] + ([duplicado.duplicado_de] if duplicado.duplicado_de else [])
    if not _pode_resolver_par(projeto, request.user, *alvos):
        return HttpResponseForbidden(
            "Apenas quem importou uma das bases (ou o curador) desfaz esta mescla."
        )
    if dup.desfazer_mescla(duplicado):
        messages.success(request, "Mescla desfeita — o registro voltou para a triagem.")
    else:
        messages.info(request, "Este registro já não está marcado como duplicata.")
    return redirect("triagem_duplicatas_mescladas", slug=projeto.slug)


@_projeto_curador
def iniciar_triagem_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Curador fecha a coleta e dispara o sorteio dos identificados."""
    n_disponiveis = projeto.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    ).count()

    if request.method == "POST":
        n = iniciar_triagem(projeto)
        if n:
            messages.success(request, f"Triagem iniciada para {n} registro(s).")
        else:
            messages.info(request, "Nenhum registro identificado disponível para triar.")
        return redirect("triagem_registros", slug=projeto.slug)

    return render(
        request,
        "triagem/iniciar_confirma.html",
        {"projeto": projeto, "protocolo": projeto, "n_disponiveis": n_disponiveis},
    )


@_exige_analista
def minhas_triagens_view(request: HttpRequest) -> HttpResponse:
    pendentes = list(
        DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=True)
        .select_related("registro")
        .order_by("prazo_em")
    )
    concluidas = (
        DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=False)
        .select_related("registro")
        .order_by("-concluido_em")[:20]
    )
    total = DecisaoTriagem.objects.filter(revisor=request.user).count()
    feitas = total - len(pendentes)
    return render(
        request,
        "triagem/minhas_triagens.html",
        {
            "pendentes": pendentes,
            "concluidas": concluidas,
            "primeiro": pendentes[0] if pendentes else None,
            "total": total,
            "feitas": feitas,
            "pct": round(feitas * 100 / total) if total else 0,
        },
    )


@_exige_analista
def triar_view(request: HttpRequest, decisao_id: int) -> HttpResponse:
    """Interface de triagem mascarada: o revisor vê só os metadados do registro."""
    decisao = get_object_or_404(
        DecisaoTriagem.objects.select_related("registro__protocolo"), pk=decisao_id
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
            # Auto-avançar: vai direto ao próximo pendente (fluxo guiado).
            prox = (
                DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=True)
                .exclude(pk=decisao.pk)
                .order_by("prazo_em")
                .first()
            )
            if prox is not None:
                return redirect("triagem_triar", decisao_id=prox.pk)
            messages.success(
                request, "Triagem concluída! 🎉 Você triou todos os registros sorteados."
            )
            return redirect("triagem_minhas")
    else:
        form = DecisaoTriagemForm()

    # Progresso do revisor (X de Y) para o fluxo guiado.
    total = DecisaoTriagem.objects.filter(revisor=request.user).count()
    feitas = DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=False).count()
    pct = round(feitas * 100 / total) if total else 0
    proximo = (
        DecisaoTriagem.objects.filter(revisor=request.user, concluido_em__isnull=True)
        .exclude(pk=decisao.pk)
        .order_by("prazo_em")
        .first()
    )

    # Mascarado: nenhuma informação sobre coletor ou outros revisores.
    return render(
        request,
        "triagem/triar.html",
        {
            "decisao": decisao,
            "registro": registro,
            "form": form,
            "termos_realce": registro.protocolo.termos_realce,
            "posicao": feitas + 1,
            "total": total,
            "pct": pct,
            "proximo": proximo,
        },
    )


@_projeto_curador
def fila_desempate_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    registros = registros_para_desempate(projeto)
    return render(
        request,
        "triagem/desempate_fila.html",
        {"projeto": projeto, "registros": registros, "protocolo": projeto},
    )


@_projeto_curador
def desempatar_view(
    request: HttpRequest, projeto: ProtocoloTriagem, registro_id: int
) -> HttpResponse:
    registro = get_object_or_404(RegistroTriagem, pk=registro_id, protocolo=projeto)
    decisoes = registro.decisoes.select_related("revisor").all()

    if request.method == "POST":
        form = DesempateForm(request.POST)
        if form.is_valid():
            escolha = form.cleaned_data["decisao"]
            consolidar_registro(
                registro,
                escolha,
                motivo=form.cleaned_data["motivo_exclusao"],
                por=request.user,
            )
            avancar_apos_status(registro)  # promove ou dispara o texto completo
            messages.success(request, "Desempate registrado.")
            return redirect("triagem_desempate", slug=projeto.slug)
    else:
        form = DesempateForm()

    return render(
        request,
        "triagem/desempate.html",
        {"projeto": projeto, "registro": registro, "decisoes": decisoes, "form": form},
    )


@_projeto_analista
def protocolo_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Protocolo a priori: critérios, registro externo, versão/lock (PRISMA-ScR)."""
    if request.method == "POST":
        if not projeto.eh_curador_no(request.user):
            return HttpResponseForbidden("Apenas curadores gerenciam o protocolo.")
        acao = request.POST.get("acao")
        if acao == "salvar":
            projeto.registro_externo = request.POST.get("registro_externo", "").strip()
            projeto.usa_texto_completo = bool(request.POST.get("usa_texto_completo"))
            projeto.save(update_fields=["registro_externo", "usa_texto_completo"])
            messages.success(request, "Protocolo atualizado.")
        elif acao == "travar":
            projeto.travar(request.user)
            messages.success(request, f"Versão {projeto.versao} travada (a priori).")
        elif acao == "nova_versao":
            projeto.abrir_nova_versao()
            messages.info(request, f"Aberta a versão {projeto.versao} para edição.")
        return redirect("triagem_protocolo", slug=projeto.slug)

    return render(
        request,
        "triagem/protocolo.html",
        {"projeto": projeto, "protocolo": projeto, "versoes": projeto.versoes.all()},
    )


@_projeto_analista
def calibracao_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Piloto de calibração: equipe tria amostra comum, mede-se κ (Fase 11.5)."""
    from . import calibracao as cal
    from .models import RodadaCalibracao

    if request.method == "POST":
        if not projeto.eh_curador_no(request.user):
            return HttpResponseForbidden("Apenas curadores gerenciam a calibração.")
        acao = request.POST.get("acao")
        if acao == "iniciar":
            try:
                tamanho = int(request.POST.get("tamanho", "10"))
            except ValueError:
                tamanho = 10
            rodada = cal.iniciar_calibracao(projeto, max(1, tamanho), criada_por=request.user)
            if rodada:
                messages.success(
                    request,
                    f"Calibração iniciada: {rodada.registros.count()} registros "
                    f"para {rodada.n_revisores} revisores.",
                )
            else:
                messages.error(
                    request,
                    "Não foi possível iniciar (faltam registros identificados ou "
                    "revisores aprovados suficientes no projeto).",
                )
        elif acao == "fechar":
            rodada = get_object_or_404(
                RodadaCalibracao, pk=request.POST.get("rodada_id"), protocolo=projeto
            )
            res = cal.fechar_calibracao(rodada)
            messages.success(
                request,
                f"Calibração fechada: κ={res.kappa if res.kappa is not None else '—'} "
                f"({res.interpretacao}).",
            )
        return redirect("triagem_calibracao", slug=projeto.slug)

    rodadas = []
    for r in projeto.calibracoes.all().prefetch_related("registros"):
        rodadas.append({"rodada": r, "resultado": cal.calcular(r)})
    return render(
        request,
        "triagem/calibracao.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "rodadas": rodadas,
            "eh_curador": projeto.eh_curador_no(request.user),
        },
    )


@_projeto_analista
def checklist_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Checklist PRISMA-ScR (Tricco 2018) — página + export CSV."""
    from . import checklist as cl

    if request.GET.get("formato") == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="prisma-scr_checklist.csv"'
        w = csv.writer(resp)
        w.writerow(["secao", "item", "titulo", "descricao", "onde_no_anco", "opcional"])
        for secao, num, titulo, desc, anco, _link, opc in cl.ITENS:
            w.writerow([secao, num, titulo, desc, anco, "sim" if opc else "não"])
        return resp

    return render(
        request,
        "triagem/checklist.html",
        {"projeto": projeto, "protocolo": projeto, "secoes": cl.secoes()},
    )


@_exige_analista
def ajuda_view(request: HttpRequest) -> HttpResponse:
    """Como funciona a triagem: protocolo, fluxo e papéis (página de apoio global)."""
    projeto = projetos_do_usuario(request.user).first()
    return render(request, "triagem/ajuda.html", {"protocolo": projeto})


@_exige_analista
def a_analisar_view(request: HttpRequest) -> HttpResponse:
    """Artigos a analisar. Se o usuário tem **atribuições** (Revisão ANCO), vê só
    as suas; senão, o pool aberto de incluídos (modo rigoroso/compat)."""
    from apps.acervo.models import Analise, Artigo

    minhas = Analise.objects.filter(analista=request.user).values_list("artigo_id", flat=True)
    atribuidos = list(
        AtribuicaoAnalise.objects.filter(analista=request.user).values_list("artigo_id", flat=True)
    )
    por_atribuicao = bool(atribuidos)
    if por_atribuicao:
        artigos = Artigo.objects.filter(pk__in=atribuidos)
    else:
        artigos = Artigo.objects.filter(registros_triagem__status=RegistroTriagem.Status.INCLUIDO)
    artigos = artigos.exclude(pk__in=minhas).distinct().order_by("-ano", "titulo")
    pagina = Paginator(artigos, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "triagem/a_analisar.html",
        {"pagina": pagina, "por_atribuicao": por_atribuicao},
    )


@_projeto_analista
def prisma_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Fluxograma PRISMA-ScR (contagens + concordância) + export CSV/JSON."""
    from . import concordancia as conc

    contagem = prisma.computar(projeto)
    acordo = conc.calcular(projeto)
    formato = request.GET.get("formato")

    export = {**contagem.como_dict(), **acordo.como_dict()}

    if formato == "json":
        return JsonResponse(export)

    if formato == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="prisma_anco.csv"'
        escritor = csv.writer(resp)
        escritor.writerow(["etapa", "n"])
        for chave, valor in export.items():
            if chave in ("excluidos_por_motivo", "excluidos_tc_por_motivo"):
                continue
            escritor.writerow([chave, valor])
        for item in contagem.excluidos_por_motivo:
            escritor.writerow([f"excluido: {item['motivo_exclusao']}", item["n"]])
        return resp

    return render(
        request,
        "triagem/prisma.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "c": contagem,
            "acordo": acordo,
            "json": json.dumps(export),
        },
    )


# --------------------------------------------------------------------------- #
# Revisão ANCO (Fase 13): autotriagem · pool por relevância · sorteio · consenso
# --------------------------------------------------------------------------- #


def _autotriar_url(slug: str, lista: str, i: int, escopo: str = "minhas") -> str:
    return f"{reverse('triagem_autotriar', args=[slug])}?escopo={escopo}&lista={lista}&i={i}"


@_projeto_analista
def autotriar_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Autotriagem (modo ANCO): navega itens e decide com botões no topo.

    Duas listas: `pendentes` (a triar) e `decididos` (incluídos/excluídos, com
    desfazer). Navegação por índice `i` — pode avançar/voltar sem decidir.
    """
    if not projeto.eh_anco:
        messages.info(request, "Este projeto usa triagem por revisores independentes.")
        return redirect("triagem_registros", slug=projeto.slug)

    eh_curador = projeto.eh_curador_no(request.user)

    def _escopo(valor):
        # 'todas' só vale para curador; senão cai em 'minhas'.
        return "todas" if (valor == "todas" and eh_curador) else "minhas"

    if request.method == "POST":
        registro = get_object_or_404(
            RegistroTriagem, pk=request.POST.get("registro_id"), protocolo=projeto
        )
        if not pode_autotriar(projeto, request.user, registro):
            return HttpResponseForbidden("Você só tria registros de bases que importou.")
        acao = request.POST.get("acao")
        lista = request.POST.get("lista", "pendentes")
        escopo = _escopo(request.POST.get("escopo"))
        try:
            i = int(request.POST.get("i", 0))
        except (TypeError, ValueError):
            i = 0
        if acao == "desfazer":
            if desfazer_autotriagem(registro, por=request.user):
                messages.success(request, "Decisão desfeita — voltou para a fila.")
        elif acao in ("incluir", "excluir"):
            if registro.status == RegistroTriagem.Status.IDENTIFICADO and not registro.ja_no_acervo:
                novo = autotriar(registro, acao, por=request.user)
                rotulo = "incluído" if novo == RegistroTriagem.Status.INCLUIDO else "excluído"
                messages.success(request, f"Registro {rotulo}.")
            else:
                messages.info(request, "Este registro não está disponível para triagem.")
        else:
            messages.error(request, "Ação inválida.")
        return redirect(_autotriar_url(projeto.slug, lista, i, escopo))

    escopo = _escopo(request.GET.get("escopo"))
    lista = request.GET.get("lista", "pendentes")
    if lista == "incluidos":
        qs = registros_decididos_do_usuario(
            projeto, request.user, (RegistroTriagem.Status.INCLUIDO,), escopo
        )
    elif lista == "excluidos":
        qs = registros_decididos_do_usuario(
            projeto, request.user, (RegistroTriagem.Status.EXCLUIDO,), escopo
        )
    else:
        lista = "pendentes"
        qs = registros_para_autotriar(projeto, request.user, escopo)
    ids = list(qs.values_list("pk", flat=True))
    total = len(ids)
    try:
        i = int(request.GET.get("i", 0))
    except (TypeError, ValueError):
        i = 0
    i = max(0, min(i, total - 1)) if total else 0
    registro = RegistroTriagem.objects.select_related("artigo").get(pk=ids[i]) if total else None
    return render(
        request,
        "triagem/autotriar.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "registro": registro,
            "eh_curador": eh_curador,
            "escopo": escopo,
            "lista": lista,
            "i": i,
            "pos": i + 1,
            "total": total,
            "tem_anterior": i > 0,
            "tem_proximo": i < total - 1,
            "url_anterior": _autotriar_url(projeto.slug, lista, i - 1, escopo) if i > 0 else "",
            "url_proximo": _autotriar_url(projeto.slug, lista, i + 1, escopo)
            if i < total - 1
            else "",
            "n_pendentes": registros_para_autotriar(projeto, request.user, escopo).count(),
            "n_incluidos": registros_decididos_do_usuario(
                projeto, request.user, (RegistroTriagem.Status.INCLUIDO,), escopo
            ).count(),
            "n_excluidos": registros_decididos_do_usuario(
                projeto, request.user, (RegistroTriagem.Status.EXCLUIDO,), escopo
            ).count(),
            "termos_realce": projeto.termos_realce,
        },
    )


@_projeto_analista
def incluidos_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Pool de incluídos ordenado por relevância (correspondência de termos)."""
    regs = (
        projeto.registros.filter(status=RegistroTriagem.Status.INCLUIDO)
        .select_related("artigo", "artigo__base_consulta")
        .order_by("-relevancia_score", "-artigo__ano", "titulo")
    )
    pagina = Paginator(regs, 50).get_page(request.GET.get("page"))
    eh_cur = projeto.eh_curador_no(request.user)
    # Quem pode excluir cada incluído: curador (todos) ou quem importou a base.
    if eh_cur:
        excluiveis_ids = {r.pk for r in pagina.object_list}
    else:
        excluiveis_ids = set(
            projeto.registros.filter(
                status=RegistroTriagem.Status.INCLUIDO,
                origem_buscas__criado_por=request.user,
            ).values_list("pk", flat=True)
        )
    return render(
        request,
        "triagem/incluidos.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "pagina": pagina,
            "n_termos": len(termos_do_protocolo(projeto)),
            "pode_curar": eh_cur,
            "excluiveis_ids": excluiveis_ids,
        },
    )


@_projeto_analista
@require_POST
def excluir_incluido_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Exclui um incluído do pool (Revisão ANCO): reverte a inclusão."""
    if not projeto.eh_anco:
        return HttpResponseForbidden("Disponível apenas na Revisão ANCO.")
    registro = get_object_or_404(
        RegistroTriagem, pk=request.POST.get("registro_id"), protocolo=projeto
    )
    if not pode_autotriar(projeto, request.user, registro):
        return HttpResponseForbidden("Você só exclui incluídos de bases que importou.")
    if reverter_inclusao(registro, por=request.user, motivo=request.POST.get("motivo", "").strip()):
        messages.success(request, "Artigo excluído do pool de análise.")
    else:
        messages.info(request, "Este registro não estava incluído.")
    return redirect("triagem_incluidos", slug=projeto.slug)


@_projeto_curador
def sorteio_analise_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Curador sorteia os incluídos entre os analistas (cota, única/dupla)."""
    if request.method == "POST":
        modo = request.POST.get("modo_revisao", SorteioAnalise.ModoRevisao.UNICA)
        if modo not in dict(SorteioAnalise.ModoRevisao.choices):
            modo = SorteioAnalise.ModoRevisao.UNICA
        try:
            cota = max(1, int(request.POST.get("cota") or 5))
        except (TypeError, ValueError):
            cota = 5
        res = executar_sorteio_analise(
            projeto,
            modo_revisao=modo,
            cota=cota,
            por=request.user,
            observacoes=request.POST.get("observacoes", "").strip(),
        )
        if res.sorteio is not None:
            msg = f"Sorteio criado: {res.atribuidas} atribuições para {res.analistas} analista(s)."
            faltaram = sum(1 for v in res.faltas.values() if v)
            if faltaram:
                msg += f" {faltaram} analista(s) não completaram a cota (pool insuficiente)."
            messages.success(request, msg)
        else:
            messages.info(request, res.motivo or "Nada a sortear.")
        return redirect("triagem_sorteio_analise", slug=projeto.slug)

    sorteios = projeto.sorteios_analise.prefetch_related("atribuicoes").all()
    n_incluidos = projeto.registros.filter(status=RegistroTriagem.Status.INCLUIDO).count()
    ja_atribuidos = (
        AtribuicaoAnalise.objects.filter(sorteio__projeto=projeto)
        .values("artigo_id")
        .distinct()
        .count()
    )
    return render(
        request,
        "triagem/sorteio_analise.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "sorteios": sorteios,
            "n_incluidos": n_incluidos,
            "n_disponiveis": n_incluidos - ja_atribuidos,
            "n_analistas": len(analistas_do_projeto(projeto)),
            "modos": SorteioAnalise.ModoRevisao.choices,
        },
    )


def _artigos_para_consenso(projeto: ProtocoloTriagem):
    """Artigos de sorteios `dupla` com ≥2 análises enviadas e sem consenso ainda."""
    from apps.acervo.models import Analise

    artigo_ids = set(
        AtribuicaoAnalise.objects.filter(
            sorteio__projeto=projeto,
            sorteio__modo_revisao=SorteioAnalise.ModoRevisao.DUPLA,
        ).values_list("artigo_id", flat=True)
    )
    ja_conciliados = set(
        ConsensoAnalise.objects.filter(
            artigo_id__in=artigo_ids, conciliado_em__isnull=False
        ).values_list("artigo_id", flat=True)
    )
    pendentes = []
    enviadas = (Analise.Status.SUBMETIDA, Analise.Status.PUBLICADA)
    for aid in artigo_ids - ja_conciliados:
        analises = list(
            Analise.objects.filter(artigo_id=aid, status__in=enviadas).select_related(
                "analista", "artigo"
            )
        )
        if len(analises) >= 2:
            pendentes.append({"artigo": analises[0].artigo, "analises": analises})
    return pendentes


@_projeto_curador
def consenso_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Conciliação da revisão dupla (curador): registra a análise final."""
    if request.method == "POST":
        from apps.acervo.models import Analise

        artigo_id = request.POST.get("artigo_id")
        final_id = request.POST.get("analise_final")
        analises = list(
            Analise.objects.filter(
                artigo_id=artigo_id,
                status__in=(Analise.Status.SUBMETIDA, Analise.Status.PUBLICADA),
            )
        )
        if len(analises) < 2 or str(final_id) not in {str(a.pk) for a in analises}:
            messages.error(request, "Selecione a análise final entre as enviadas.")
            return redirect("triagem_consenso", slug=projeto.slug)
        consenso = ConsensoAnalise.objects.create(
            artigo_id=artigo_id,
            analise_final_id=final_id,
            conciliado_por=request.user,
            conciliado_em=timezone.now(),
        )
        consenso.analises.set(analises)
        messages.success(request, "Consenso registrado.")
        return redirect("triagem_consenso", slug=projeto.slug)

    return render(
        request,
        "triagem/consenso.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "pendentes": _artigos_para_consenso(projeto),
        },
    )
