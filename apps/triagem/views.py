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

from django.conf import settings
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
from .forms import (
    DecisaoTriagemForm,
    DesempateForm,
    EditarBuscaForm,
    ImportarBuscaForm,
    RegistroFonteForm,
)
from .importacao import (
    analisar_arquivo,
    decodificar,
    excluir_busca,
    importar_para_busca,
    parse_conteudo,
    pode_excluir_busca,
)
from .models import (
    AtribuicaoAnalise,
    Busca,
    DecisaoTriagem,
    ProjetoMembro,
    ProtocoloTriagem,
    RegistroTriagem,
)
from .tasks import avancar_apos_status
from .triagem_direta import atribuir_triagem_direta, revisores_validos


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


def _anco_movido(slug: str) -> bool:
    """Transição (separação ANCO × PRISMA): True se o slug já foi migrado para o
    módulo `apps/anco`. Não depende do campo `modo` (que será removido na Fase C)."""
    if not getattr(settings, "ANCO_ATIVO", False):
        return False
    from apps.anco.models import ProjetoANCO

    return ProjetoANCO.objects.filter(slug=slug).exists()


def _projeto_analista(view):
    """Resolve o projeto pelo slug e exige que o usuário seja **membro** dele."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
        if _anco_movido(slug):
            return redirect("anco_painel", slug=slug, permanent=True)
        projeto = get_object_or_404(ProtocoloTriagem, slug=slug)
        if not getattr(request.user, "eh_analista", False):
            return HttpResponseForbidden("Apenas analistas ou curadores acessam a triagem.")
        if not (request.user.is_staff or projeto.eh_membro(request.user)):
            return HttpResponseForbidden("Você não é membro deste projeto.")
        return view(request, projeto, *args, **kwargs)

    return wrapper


def _projeto_curador(view):
    """Resolve o projeto pelo slug e exige curador **do projeto** (ou admin)."""

    @functools.wraps(view)
    @login_required
    def wrapper(request: HttpRequest, slug: str, *args, **kwargs):
        if _anco_movido(slug):
            return redirect("anco_painel", slug=slug, permanent=True)
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
    pode_criar = request.user.is_staff or request.user.eh_curador
    return render(
        request,
        "triagem/projetos.html",
        {"projetos": dados, "pode_criar": pode_criar},
    )


@_exige_analista
def novo_projeto_view(request: HttpRequest) -> HttpResponse:
    """Cria um novo projeto (revisão de escopo). Curador ou admin."""
    if not (request.user.is_staff or request.user.eh_curador):
        return HttpResponseForbidden("Apenas curadores criam projetos.")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        if not nome:
            messages.error(request, "Informe um nome para o projeto.")
            return redirect("triagem_novo_projeto")
        modo = request.POST.get("modo")
        if modo not in dict(ProtocoloTriagem.Modo.choices):
            modo = ProtocoloTriagem.Modo.RIGOROSO
        projeto = ProtocoloTriagem.objects.create(
            nome=nome,
            titulo=nome,
            modo=modo,
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

    return render(
        request,
        "triagem/novo_projeto.html",
        {"modos": ProtocoloTriagem.Modo.choices},
    )


# --------------------------------------------------------------------------- #
# Painel e fluxo do projeto
# --------------------------------------------------------------------------- #


@_projeto_analista
def painel_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:

    from . import concordancia as conc

    _St = RegistroTriagem.Status
    eh_curador = projeto.eh_curador_no(request.user)

    buscas = list(
        projeto.buscas.select_related("criado_por", "base_consulta").order_by(
            "-importado_em", "-criado_em"
        )[:50]
    )
    # As ações por importação (editar/excluir) vivem na página de detalhe; aqui a
    # linha é só um resumo clicável.
    minhas_buscas = [b for b in buscas if b.criado_por_id == request.user.id]
    membros = projeto.membros.select_related("usuario").order_by("-papel", "usuario__nome_exibicao")
    contexto = {
        "projeto": projeto,
        "protocolo": projeto,
        "buscas": buscas,
        "minhas_buscas": minhas_buscas,
        "n_buscas": projeto.buscas.count(),
        "n_registros": projeto.registros.count(),
        "eh_curador": eh_curador,
        "membros": membros,
        "n_membros": membros.count(),
        "c": prisma.computar(projeto),
        "acordo": conc.calcular(projeto),
    }

    # PRISMA-ScR: painel guiado em 5 passos. Calcula o estado de
    # cada passo para acender/apagar o botão certo (ver painel.html).
    # ① protocolo completo? (tem critério de inclusão/exclusão registrado)
    contexto["protocolo_incompleto"] = not (
        projeto.criterios_inclusao.strip() or projeto.criterios_exclusao.strip()
    )
    # ③ duplicatas a revisar (mesma regra do modo ANCO)
    contexto["minha_dup"] = dup.contar_pares_do_usuario(projeto, request.user, eh_curador)
    # ④ minha fila de triagem NESTE projeto (link direto ao próximo artigo)
    minhas = DecisaoTriagem.objects.filter(revisor=request.user, registro__protocolo=projeto)
    total_fila = minhas.count()
    feitas = minhas.filter(concluido_em__isnull=False).count()
    contexto["minha_fila_total"] = total_fila
    contexto["minha_fila_feitas"] = feitas
    contexto["minha_fila_pct"] = round(feitas * 100 / total_fila) if total_fila else 0
    contexto["minha_proxima_id"] = (
        minhas.filter(concluido_em__isnull=True)
        .order_by("prazo_em")
        .values_list("pk", flat=True)
        .first()
    )
    # ④ artigos novos ainda não atribuídos — curador "inicia" (atribui) a triagem
    contexto["n_a_atribuir"] = projeto.registros.filter(
        status=_St.IDENTIFICADO, ja_no_acervo=False
    ).count()
    # ⑤ divergências aguardando desempate (curador)
    contexto["n_divergencias"] = len(registros_para_desempate(projeto)) if eh_curador else 0
    return render(request, "triagem/painel.html", contexto)


@_projeto_analista
def importar_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    if request.method == "POST":
        form = ImportarBuscaForm(request.POST, request.FILES)
        if form.is_valid():
            enviado = form.cleaned_data["arquivo"]
            raw = enviado.read()
            enviado.seek(0)
            info = analisar_arquivo(enviado.name, raw)  # valida + conta + dica
            if not info["ok"]:
                form.add_error("arquivo", f"{info['erro']} {info.get('dica', '')}".strip())
            else:
                cd = form.cleaned_data
                formato = cd["formato"] or info["formato"]
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
                    # Auto: usa a contagem do arquivo se o nº reportado ficou em branco.
                    n_identificados=cd["n_identificados"] or info["n"],
                    data_busca=cd["data_busca"],
                    formato=formato,
                    arquivo=enviado,
                    criado_por=request.user,
                )
                busca.save()
                registros = parse_conteudo(decodificar(raw), formato)
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
@require_POST
def importar_preview_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Validação imediata do arquivo (HTMX, no `change` do input): conta os
    registros ou explica o erro, e libera/trava o botão Importar via HX-Trigger."""
    import json as _json

    f = request.FILES.get("arquivo")
    if f is None:
        info = {"ok": False, "erro": "Escolha um arquivo.", "dica": ""}
    else:
        info = analisar_arquivo(f.name, f.read())
    resp = render(request, "triagem/_importar_preview.html", {"info": info})
    resp["HX-Trigger"] = _json.dumps(
        {"arquivo-validado": {"ok": bool(info["ok"]), "n": info.get("n", 0)}}
    )
    return resp


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
    pode_excluir, excluir_cascata, motivo_bloqueio = pode_excluir_busca(
        busca, request.user, projeto
    )
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
            "excluir_cascata": excluir_cascata,
            "motivo_bloqueio": motivo_bloqueio,
            "pode_gerenciar": pode_excluir,
            "pode_editar": _pode_editar_busca(busca, request.user, projeto),
        },
    )


@_projeto_analista
@require_POST
def excluir_busca_view(
    request: HttpRequest, projeto: ProtocoloTriagem, busca_id: int
) -> HttpResponse:
    """Exclui uma importação. Antes da triagem: importador ou curador. Depois:
    só curador, e a triagem é apagada junto."""
    busca = get_object_or_404(Busca, pk=busca_id, protocolo=projeto)
    pode, cascata, motivo = pode_excluir_busca(busca, request.user, projeto)
    if not pode:
        return HttpResponseForbidden(motivo)
    ok, msg = excluir_busca(busca, forcar=cascata)
    if ok:
        messages.success(
            request,
            "Importação e a triagem correspondente excluídas."
            if cascata
            else "Importação excluída. Você pode importar de novo.",
        )
        return redirect("triagem_painel", slug=projeto.slug)
    messages.error(request, msg)
    return redirect("triagem_painel", slug=projeto.slug)


def _pode_editar_busca(busca, user, projeto) -> bool:
    """Quem altera os metadados de uma importação: o importador ou o curador.

    Edição só mexe nos metadados (base, estratégia, filtros…), nunca nos
    registros já importados — por isso é liberada mesmo após a triagem começar.
    """
    return busca.criado_por_id == user.id or projeto.eh_curador_no(user)


@_projeto_analista
def editar_busca_view(
    request: HttpRequest, projeto: ProtocoloTriagem, busca_id: int
) -> HttpResponse:
    """Edita os metadados de uma importação já carregada (sem reimportar)."""
    busca = get_object_or_404(Busca, pk=busca_id, protocolo=projeto)
    if not _pode_editar_busca(busca, request.user, projeto):
        return HttpResponseForbidden("Só quem importou (ou o curador) edita esta importação.")

    campos = [
        "base_consulta",
        "outra_base",
        "string_busca",
        "campos_busca",
        "ano_inicio",
        "ano_fim",
        "idiomas",
        "idioma_outro",
        "tipos_documento",
        "filtros",
        "data_busca",
        "n_identificados",
    ]
    if request.method == "POST":
        form = EditarBuscaForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            for campo in campos:
                if campo == "n_identificados" and cd.get(campo) is None:
                    continue  # mantém a contagem existente se deixarem em branco
                setattr(busca, campo, cd[campo])
            busca.save(update_fields=campos)
            messages.success(request, "Dados da importação atualizados.")
            return redirect("triagem_busca_resumo", slug=projeto.slug, busca_id=busca.pk)
    else:
        form = EditarBuscaForm(
            initial={
                "base_consulta": busca.base_consulta_id,
                "outra_base": busca.outra_base,
                "string_busca": busca.string_busca,
                "campos_busca": busca.campos_busca,
                "ano_inicio": busca.ano_inicio,
                "ano_fim": busca.ano_fim,
                "idiomas": busca.idiomas,
                "idioma_outro": busca.idioma_outro,
                "tipos_documento": busca.tipos_documento,
                "filtros": busca.filtros,
                "data_busca": busca.data_busca,
                "n_identificados": busca.n_identificados,
            }
        )

    import datetime

    return render(
        request,
        "triagem/editar_busca.html",
        {
            "form": form,
            "busca": busca,
            "projeto": projeto,
            "protocolo": projeto,
            "ano_min": 2000,
            "ano_max": datetime.date.today().year,
            "ano_range": datetime.date.today().year - 2000,
        },
    )


def _sincronizar_artigo(registro) -> None:
    """Propaga os campos bibliográficos do registro para o `Artigo` promovido.

    Mantém a análise em sincronia com as correções feitas na fonte. Nunca toca o
    acervo legado (`eh_legado`). Se o DOI/ISBN editado colidir com outro artigo,
    salva o resto e preserva a chave antiga.
    """
    from django.db import IntegrityError

    from .promocao import _idioma

    artigo = registro.artigo
    if artigo is None or artigo.eh_legado:
        return
    artigo.titulo = registro.titulo
    artigo.autores = registro.autores
    artigo.ano = registro.ano
    artigo.resumo = registro.resumo
    artigo.palavras_chaves = registro.palavras_chaves
    artigo.titulo_periodico = registro.titulo_periodico
    artigo.idioma = _idioma(registro.idioma)
    artigo.link_acesso = registro.link or ""
    artigo.doi = registro.doi or None
    artigo.isbn = registro.isbn or None
    comuns = [
        "titulo",
        "autores",
        "ano",
        "resumo",
        "palavras_chaves",
        "titulo_periodico",
        "idioma",
        "link_acesso",
    ]
    try:
        artigo.save(update_fields=[*comuns, "doi", "isbn"])
    except IntegrityError:
        # DOI/ISBN colidiu com outro artigo: salva o resto sem mexer na chave.
        artigo.refresh_from_db(fields=["doi", "isbn"])
        for campo in comuns:
            setattr(artigo, campo, getattr(registro, campo, getattr(artigo, campo)))
        artigo.idioma = _idioma(registro.idioma)
        artigo.link_acesso = registro.link or ""
        artigo.save(update_fields=comuns)


def _navegar_fontes(request, projeto, ids, *, base_url, voltar_url, voltar_label, titulo_fontes):
    """Núcleo do navegador de fontes (1 registro por vez, edição inline)."""
    total = len(ids)

    def _idx(valor) -> int:
        try:
            return max(0, min(int(valor), total - 1)) if total else 0
        except (TypeError, ValueError):
            return 0

    i = _idx(request.POST.get("i") if request.method == "POST" else request.GET.get("i"))
    registro = RegistroTriagem.objects.select_related("artigo").get(pk=ids[i]) if total else None

    if request.method == "POST" and registro is not None:
        form = RegistroFonteForm(request.POST, instance=registro)
        if form.is_valid():
            form.save()
            _sincronizar_artigo(registro)
            messages.success(request, "Fonte atualizada.")
            # Edição inline: fica na mesma fonte (a navegação é por Voltar/Avançar).
            return redirect(f"{base_url}?i={i}")
    else:
        form = RegistroFonteForm(instance=registro) if registro else None

    # Termos destacados (<mark>) nos campos de texto: os do projeto ou o padrão AnCo.
    realce_termos = projeto.termos_realce or (
        "cognitive analysis, cognitive analyses, análise cognitiva, "
        "analise cognitiva, análises cognitivas, analises cognitivas"
    )
    return render(
        request,
        "triagem/fonte.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "registro": registro,
            "form": form,
            "pos": i + 1,
            "total": total,
            "realce_termos": realce_termos,
            "voltar_url": voltar_url,
            "voltar_label": voltar_label,
            "titulo_fontes": titulo_fontes,
            "url_anterior": f"{base_url}?i={i - 1}" if i > 0 else "",
            "url_proximo": f"{base_url}?i={i + 1}" if i < total - 1 else "",
        },
    )


@_projeto_analista
def fonte_view(request: HttpRequest, projeto: ProtocoloTriagem, busca_id: int) -> HttpResponse:
    """Navega as fontes de uma importação. Gate: importador ou curador."""
    busca = get_object_or_404(Busca, pk=busca_id, protocolo=projeto)
    if not _pode_editar_busca(busca, request.user, projeto):
        return HttpResponseForbidden("Só quem importou (ou o curador) navega/edita as fontes.")
    ids = list(busca.registros.order_by("titulo", "pk").values_list("pk", flat=True))
    return _navegar_fontes(
        request,
        projeto,
        ids,
        base_url=reverse("triagem_busca_fonte", args=[projeto.slug, busca.pk]),
        voltar_url=reverse("triagem_busca_resumo", args=[projeto.slug, busca.pk]),
        voltar_label=busca.base_nome or "Importação",
        titulo_fontes=busca.base_nome or "Importação",
    )


@_projeto_analista
def fontes_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Navega TODAS as fontes do projeto que o usuário pode editar (as suas
    importações; o curador vê todas). Entrada pelo painel."""
    # Só as fontes incluídas pelo próprio usuário (as suas importações/artigos).
    qs = projeto.registros.filter(
        status=RegistroTriagem.Status.INCLUIDO, origem_buscas__criado_por=request.user
    )
    ids = list(qs.order_by("titulo", "pk").values_list("pk", flat=True).distinct())
    return _navegar_fontes(
        request,
        projeto,
        ids,
        base_url=reverse("triagem_fontes", args=[projeto.slug]),
        voltar_url=reverse("triagem_painel", args=[projeto.slug]),
        voltar_label=projeto.nome or "Projeto",
        titulo_fontes="suas fontes",
    )


@_projeto_analista
def registros_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    qs = projeto.registros.select_related("artigo").all()

    status = request.GET.get("status", "")
    if status in dict(RegistroTriagem.Status.choices):
        qs = qs.filter(status=status)

    # Filtro opcional por importação (cards clicáveis da página de detalhe da busca).
    busca_filtro = None
    busca_id = request.GET.get("busca", "")
    if busca_id:
        busca_filtro = projeto.buscas.filter(pk=busca_id).first()
        if busca_filtro:
            qs = qs.filter(origem_buscas=busca_filtro)

    # Recorte por situação no acervo: 0 = novos no corpus, 1 = já no acervo.
    acervo = request.GET.get("acervo", "")
    if acervo == "1":
        qs = qs.filter(ja_no_acervo=True)
    elif acervo == "0":
        qs = qs.filter(ja_no_acervo=False)

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
        "busca_filtro": busca_filtro,
        "acervo_atual": acervo,
    }
    return render(request, "triagem/registros.html", contexto)


@_projeto_analista
def duplicatas_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Revisão de possíveis duplicatas — um par por vez, navegável.

    O curador vê todos os pares; o analista membro vê só os que tocam bases que
    importou (Fase 12.4).
    """
    eh_curador = projeto.eh_curador_no(request.user)
    # Escopo (espelha a autotriagem): 'minhas' (só as suas bases, padrão — mesmo
    # p/ curador) ou 'todas' (curadoria, só curador).
    escopo = request.GET.get("escopo", "minhas")
    if escopo != "todas" or not eh_curador:
        escopo = "minhas"
    ver_todas = escopo == "todas"
    pares = dup.pares_do_usuario(projeto, request.user, ver_todas)
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
            "escopo": escopo,
        },
    )


def _voltar_duplicatas(request, projeto) -> str:
    i = request.POST.get("i", "0")
    escopo = request.POST.get("escopo", "minhas")
    return f"{reverse('triagem_duplicatas', args=[projeto.slug])}?escopo={escopo}&i={i}"


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
    """Curador fecha a coleta e inicia a triagem para todos os membros — sem sorteio.

    PRISMA-ScR: cada registro identificado é atribuído a **todos os membros do
    projeto** (≥2 revisores independentes), que triam de forma independente. Não
    há distribuição aleatória; reaproveita `atribuir_triagem_direta`.
    """
    n_disponiveis = projeto.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    ).count()
    membros = [m.usuario for m in projeto.membros.select_related("usuario")]

    if request.method == "POST":
        if not membros:
            messages.error(
                request,
                "O projeto não tem membros para triar. Adicione revisores em Equipe.",
            )
            return redirect("triagem_registros", slug=projeto.slug)
        res = atribuir_triagem_direta(projeto, membros)
        if res.registros:
            messages.success(
                request,
                f"Triagem iniciada para {res.registros} registro(s) "
                f"({res.revisores} revisor(es)).",
            )
        else:
            messages.info(request, "Nenhum registro identificado disponível para triar.")
        return redirect("triagem_registros", slug=projeto.slug)

    # Sem nada a iniciar: não mostra página vazia — volta ao painel com aviso.
    if not n_disponiveis:
        messages.info(
            request,
            "Nada novo a iniciar — todos os registros importados já estão em triagem.",
        )
        return redirect("triagem_painel", slug=projeto.slug)

    return render(
        request,
        "triagem/iniciar_confirma.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "n_disponiveis": n_disponiveis,
            "n_membros": len(membros),
        },
    )


@_projeto_curador
def triagem_direta_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Triagem **sem sorteio**: o curador designa os revisores e todos triam tudo.

    Atribui os revisores escolhidos a cada registro identificado (ver
    `triagem_direta.atribuir_triagem_direta`). Recomenda-se escolher todos os
    revisores de uma vez (≥2) antes de iniciar — registros já decididos não
    recebem revisores adicionados depois.
    """
    n_disponiveis = projeto.registros.filter(
        status=RegistroTriagem.Status.IDENTIFICADO, ja_no_acervo=False
    ).count()
    membros = list(
        projeto.membros.select_related("usuario").order_by(
            "-papel", "usuario__nome_exibicao"
        )
    )

    if request.method == "POST":
        ids = [int(i) for i in request.POST.getlist("revisores") if i.isdigit()]
        revisores = revisores_validos(projeto, ids)
        if not revisores:
            messages.error(request, "Selecione ao menos um revisor (membro do projeto).")
            return redirect("triagem_direta", slug=projeto.slug)
        res = atribuir_triagem_direta(projeto, revisores)
        if res.registros:
            messages.success(
                request,
                f"Triagem direta atribuída: {res.registros} registro(s) para "
                f"{res.revisores} revisor(es) ({res.decisoes} decisão/ões criadas).",
            )
        else:
            messages.info(
                request,
                "Nenhum registro novo para atribuir (os disponíveis já estavam em triagem).",
            )
        return redirect("triagem_registros", slug=projeto.slug)

    return render(
        request,
        "triagem/triagem_direta_confirma.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "n_disponiveis": n_disponiveis,
            "membros": membros,
        },
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
        elif acao == "salvar_criterios":
            # Objetivo, estratégia e critérios: editáveis só com a versão
            # destravada (preserva o protocolo a priori do PRISMA-ScR).
            if projeto.travado_em:
                messages.error(
                    request, "Protocolo travado: abra uma nova versão para editar os critérios."
                )
            else:
                campos = (
                    "pergunta_pesquisa",
                    "estrategia_busca",
                    "criterios_inclusao",
                    "criterios_exclusao",
                    "termos_realce",
                )
                for campo in campos:
                    setattr(projeto, campo, request.POST.get(campo, "").strip())
                projeto.save(update_fields=list(campos))
                messages.success(request, "Objetivo, critérios e termos de realce atualizados.")
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
        {
            "projeto": projeto,
            "protocolo": projeto,
            "versoes": projeto.versoes.all(),
            "eh_curador": projeto.eh_curador_no(request.user),
        },
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
    """Artigos a analisar. Com **atribuições** (sorteio da Revisão ANCO): só as
    suas. Sem atribuições: pool self-serve apenas dos projetos **rigorosos** — em
    projeto ANCO a análise espera o **sorteio da curadoria** (nada aparece antes)."""
    from apps.acervo.models import Analise, Artigo

    minhas = Analise.objects.filter(analista=request.user).values_list("artigo_id", flat=True)
    atribuidos = list(
        AtribuicaoAnalise.objects.filter(analista=request.user).values_list("artigo_id", flat=True)
    )
    por_atribuicao = bool(atribuidos)
    if por_atribuicao:
        # Mostra TODOS os atribuídos (mesmo já analisados) — permanecem no painel
        # com o status da análise. Não some ao iniciar/concluir.
        artigos = Artigo.objects.filter(pk__in=atribuidos).distinct().order_by("-ano", "titulo")
    else:
        # Pool self-serve (rigoroso): some o que já analisei (não re-pegar).
        artigos = (
            Artigo.objects.filter(
                registros_triagem__status=RegistroTriagem.Status.INCLUIDO,
                registros_triagem__protocolo__modo=ProtocoloTriagem.Modo.RIGOROSO,
            )
            .exclude(pk__in=minhas)
            .distinct()
            .order_by("-ano", "titulo")
        )
    pagina = Paginator(artigos, 50).get_page(request.GET.get("page"))

    # Anexa a análise do usuário a cada artigo da página (status + ação certa).
    page_ids = [a.pk for a in pagina.object_list]
    minhas_analises = {
        an.artigo_id: an
        for an in Analise.objects.filter(analista=request.user, artigo_id__in=page_ids)
    }
    for art in pagina.object_list:
        art.minha_analise = minhas_analises.get(art.pk)

    # Em projeto ANCO com incluídos, mas sem sorteio para o usuário: aguardando.
    aguardando_sorteio = (
        not por_atribuicao
        and ProtocoloTriagem.objects.filter(
            modo=ProtocoloTriagem.Modo.ANCO,
            membros__usuario=request.user,
            registros__status=RegistroTriagem.Status.INCLUIDO,
        ).exists()
    )
    return render(
        request,
        "triagem/a_analisar.html",
        {
            "pagina": pagina,
            "por_atribuicao": por_atribuicao,
            "aguardando_sorteio": aguardando_sorteio,
        },
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
# Incluídos (corpus PRISMA)
# --------------------------------------------------------------------------- #


@_projeto_analista
def incluidos_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Corpus do projeto: resumo, busca/filtros e status de análise por artigo."""
    from urllib.parse import urlencode

    from django.db.models import Exists, Max, Min, OuterRef, Q

    from apps.acervo.models import Analise

    _St = RegistroTriagem.Status
    enviadas = (Analise.Status.SUBMETIDA, Analise.Status.PUBLICADA)

    base_qs = (
        projeto.registros.filter(status=_St.INCLUIDO, artigo__isnull=False)
        .select_related("artigo", "artigo__base_consulta")
        .annotate(
            _analisado=Exists(
                Analise.objects.filter(artigo_id=OuterRef("artigo_id"), status__in=enviadas)
            ),
            _rascunho=Exists(
                Analise.objects.filter(
                    artigo_id=OuterRef("artigo_id"), status=Analise.Status.RASCUNHO
                )
            ),
            _atribuido=Exists(
                AtribuicaoAnalise.objects.filter(
                    artigo_id=OuterRef("artigo_id"), sorteio__projeto=projeto
                )
            ),
            eh_individual=Exists(
                Busca.objects.filter(registros=OuterRef("pk"), outra_base="Artigos individuais")
            ),
        )
    )

    # ── Resumo do corpus (sobre o total, não o filtrado) ────────────────
    total = base_qs.count()
    anos = base_qs.exclude(artigo__ano__isnull=True).aggregate(
        mn=Min("artigo__ano"), mx=Max("artigo__ano")
    )
    n_teses = base_qs.filter(Q(tipo__icontains="tese") | Q(tipo__icontains="disserta")).count()
    n_bases = (
        Busca.objects.filter(protocolo=projeto, registros__status=_St.INCLUIDO).distinct().count()
    )
    n_analisado = base_qs.filter(_analisado=True).count()
    n_pendente_envio = (
        base_qs.filter(_analisado=False).filter(Q(_atribuido=True) | Q(_rascunho=True)).count()
    )
    n_sem = total - n_analisado - n_pendente_envio

    # ── Busca + filtros + ordenação ─────────────────────────────────────
    q = request.GET.get("q", "").strip()
    f_base = request.GET.get("base", "").strip()
    f_tipo = request.GET.get("tipo", "").strip()
    f_idioma = request.GET.get("idioma", "").strip()
    f_status = request.GET.get("status", "").strip()
    ordem = request.GET.get("ordem", "recentes")

    qs = base_qs
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(autores__icontains=q))
    if f_base:
        # Filtra pelo NOME da base (uma base pode vir de várias importações).
        qs = qs.filter(
            Q(origem_buscas__base_consulta__nome=f_base) | Q(origem_buscas__outra_base=f_base)
        )
    if f_tipo:
        qs = qs.filter(tipo=f_tipo)
    if f_idioma:
        qs = qs.filter(idioma=f_idioma)
    if f_status == "analisado":
        qs = qs.filter(_analisado=True)
    elif f_status == "pendente":
        qs = qs.filter(_analisado=False).filter(Q(_atribuido=True) | Q(_rascunho=True))
    elif f_status == "sem":
        qs = qs.filter(_analisado=False, _atribuido=False, _rascunho=False)

    qs = qs.order_by("titulo") if ordem == "titulo" else qs.order_by("-artigo__ano", "titulo")
    qs = qs.distinct()
    n_filtrado = qs.count()
    pagina = Paginator(qs, 50).get_page(request.GET.get("page"))

    # Nome do analista atribuído (só os da página).
    page_art_ids = [r.artigo_id for r in pagina.object_list]
    # Análise do PRÓPRIO usuário em cada artigo da página (curador/admin pode
    # analisar qualquer artigo sem sorteio — o botão usa isto p/ Analisar/Continuar/Ver).
    minha_analise: dict[int, Analise] = {
        an.artigo_id: an
        for an in Analise.objects.filter(analista=request.user, artigo_id__in=page_art_ids)
    }
    atrib_nome: dict[int, str] = {}
    for a in (
        AtribuicaoAnalise.objects.filter(sorteio__projeto=projeto, artigo_id__in=page_art_ids)
        .select_related("analista")
        .order_by("criado_em")
    ):
        atrib_nome.setdefault(a.artigo_id, a.analista.nome_exibicao or a.analista.email)

    # Estado de análise por item (o template não lê atributos com "_").
    for r in pagina.object_list:
        nome = atrib_nome.get(r.artigo_id, "")
        r.minha_analise = minha_analise.get(r.artigo_id)
        if r._analisado:
            r.estado_rotulo, r.estado_cor = "● analisado", "ok"
        elif r._rascunho:
            r.estado_rotulo, r.estado_cor = "◐ em análise", "warn"
        elif r._atribuido:
            r.estado_rotulo = f"◐ atribuído a {nome}" if nome else "◐ atribuído"
            r.estado_cor = "warn"
        else:
            r.estado_rotulo, r.estado_cor = "○ sem análise", "muted"

    # Opções dos filtros — a partir de um queryset SEM anotações (senão o
    # .values().distinct() agruparia também pelos Exists e repetiria os valores).
    # `.order_by(campo)` limpa a ordenação padrão do modelo (que, senão, entra no
    # DISTINCT e repete os valores).
    corpus = projeto.registros.filter(status=_St.INCLUIDO, artigo__isnull=False)
    tipos = list(
        corpus.exclude(tipo="").order_by("tipo").values_list("tipo", flat=True).distinct()
    )
    idiomas = list(
        corpus.exclude(idioma="").order_by("idioma").values_list("idioma", flat=True).distinct()
    )
    # Bases distintas por NOME (várias importações da mesma base contam uma vez).
    bases = sorted(
        {
            b.base_nome
            for b in Busca.objects.filter(protocolo=projeto, registros__status=_St.INCLUIDO)
            .select_related("base_consulta")
            .distinct()
            if b.base_nome
        }
    )

    eh_cur = projeto.eh_curador_no(request.user)
    if eh_cur:
        excluiveis_ids = {r.pk for r in pagina.object_list}
    else:
        excluiveis_ids = set(
            projeto.registros.filter(
                status=_St.INCLUIDO, origem_buscas__criado_por=request.user
            ).values_list("pk", flat=True)
        )

    filtros = {
        "q": q,
        "base": f_base,
        "tipo": f_tipo,
        "idioma": f_idioma,
        "status": f_status,
        "ordem": ordem,
    }
    querystring = urlencode(
        {
            k: v
            for k, v in filtros.items()
            if v and k != "ordem" or (k == "ordem" and v != "recentes")
        }
    )

    return render(
        request,
        "triagem/incluidos.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "pagina": pagina,
            "total": total,
            "n_filtrado": n_filtrado,
            "tem_filtro": bool(q or f_base or f_tipo or f_idioma or f_status),
            "ano_min": anos["mn"],
            "ano_max": anos["mx"],
            "n_teses": n_teses,
            "n_bases": n_bases,
            "n_analisado": n_analisado,
            "n_pendente": n_pendente_envio,
            "n_sem": n_sem,
            "atrib_nome": atrib_nome,
            "tipos": tipos,
            "idiomas": idiomas,
            "bases": bases,
            "filtros": filtros,
            "querystring": querystring,
            "pode_curar": eh_cur,
            "excluiveis_ids": excluiveis_ids,
        },
    )


# --------------------------------------------------------------------------- #
# Equipe do projeto (gerenciar membros sem passar pelo admin)
# --------------------------------------------------------------------------- #


def _candidatos_equipe(projeto: ProtocoloTriagem, termo: str = "", limite: int = 12):
    """Usuários elegíveis a entrar na equipe: analistas/curadores ativos que
    ainda **não** são membros. `termo` filtra por e-mail ou nome (case-insensitive).
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    User = get_user_model()
    ja_membros = projeto.membros.values_list("usuario_id", flat=True)
    qs = User.objects.filter(
        is_active=True,
        papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
    ).exclude(pk__in=ja_membros)
    termo = (termo or "").strip()
    if termo:
        qs = qs.filter(
            Q(email__icontains=termo)
            | Q(nome_exibicao__icontains=termo)
            | Q(first_name__icontains=termo)
            | Q(last_name__icontains=termo)
        )
    return qs.order_by("nome_exibicao", "email")[:limite]


@_projeto_curador
def equipe_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Gerencia a equipe do projeto: adicionar por e-mail/nome, trocar papel,
    remover. Substitui o link antigo para o Django admin.
    """
    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "adicionar":
            from django.contrib.auth import get_user_model

            User = get_user_model()
            usuario_id = request.POST.get("usuario_id")
            papel = request.POST.get("papel")
            if papel not in dict(ProjetoMembro.Papel.choices):
                papel = ProjetoMembro.Papel.ANALISTA
            usuario = User.objects.filter(
                pk=usuario_id,
                is_active=True,
                papel__in=[User.Papel.ANALISTA, User.Papel.CURADOR],
            ).first()
            if not usuario:
                messages.error(request, "Usuário inválido ou não habilitado para a triagem.")
            else:
                _, criado = ProjetoMembro.objects.get_or_create(
                    projeto=projeto, usuario=usuario, defaults={"papel": papel}
                )
                nome = usuario.nome_exibicao or usuario.email
                if criado:
                    messages.success(request, f"{nome} adicionado(a) como {papel}.")
                else:
                    messages.info(request, f"{nome} já era membro.")

        elif acao in {"remover", "papel"}:
            membro = projeto.membros.filter(pk=request.POST.get("membro_id")).first()
            if not membro:
                messages.error(request, "Membro não encontrado.")
            elif acao == "remover":
                if _eh_ultimo_curador(projeto, membro):
                    messages.error(request, "Não dá para remover o último curador do projeto.")
                else:
                    nome = membro.usuario.nome_exibicao or membro.usuario.email
                    membro.delete()
                    messages.success(request, f"{nome} removido(a) da equipe.")
            else:  # papel
                novo = request.POST.get("papel")
                if novo not in dict(ProjetoMembro.Papel.choices):
                    messages.error(request, "Papel inválido.")
                elif novo != ProjetoMembro.Papel.CURADOR and _eh_ultimo_curador(projeto, membro):
                    messages.error(request, "O projeto precisa de ao menos um curador.")
                else:
                    membro.papel = novo
                    membro.save(update_fields=["papel"])
                    nome = membro.usuario.nome_exibicao or membro.usuario.email
                    messages.success(request, f"{nome} agora é {novo}.")

        return redirect("triagem_equipe", slug=projeto.slug)

    membros = projeto.membros.select_related("usuario").order_by("-papel", "usuario__nome_exibicao")
    return render(
        request,
        "triagem/equipe.html",
        {
            "projeto": projeto,
            "protocolo": projeto,
            "membros": membros,
            "n_membros": membros.count(),
            "candidatos": _candidatos_equipe(projeto),
        },
    )


@_projeto_curador
def equipe_buscar_view(request: HttpRequest, projeto: ProtocoloTriagem) -> HttpResponse:
    """Fragmento HTMX: lista de candidatos que casam com o termo digitado."""
    candidatos = _candidatos_equipe(projeto, request.GET.get("q", ""))
    return render(
        request,
        "triagem/_equipe_candidatos.html",
        {"projeto": projeto, "candidatos": candidatos, "q": request.GET.get("q", "")},
    )


def _eh_ultimo_curador(projeto: ProtocoloTriagem, membro: ProjetoMembro) -> bool:
    """True se `membro` é curador e é o único curador do projeto."""
    if membro.papel != ProjetoMembro.Papel.CURADOR:
        return False
    outros = projeto.membros.filter(papel=ProjetoMembro.Papel.CURADOR).exclude(pk=membro.pk)
    return not outros.exists()
