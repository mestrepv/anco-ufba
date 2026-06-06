"""Autotriagem — Revisão ANCO (Fase 13).

No modo `anco`, o **dono da base tria a própria base** (revisor único), em vez do
sorteio de ≥2 revisores independentes do modo rigoroso. Reaproveita a
consolidação de `aprovacao` (um único parecer → consenso trivial) e a promoção
ao acervo. Gate de propriedade espelha a dedup (Fase 12.4): curador resolve
qualquer registro; o analista só os de **bases que importou**.

Decisões aceitas: `incluir`/`excluir` (sem `dúvida` — não há desempate no modo
simplificado). O acervo curado e o protocolo rigoroso permanecem intactos.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from . import duplicatas as dup
from .aprovacao import avaliar_apos_triagem
from .models import DecisaoTriagem, ProtocoloTriagem, RegistroTriagem
from .relevancia import atualizar_relevancia

_St = RegistroTriagem.Status
_Et = DecisaoTriagem.Etapa


def pode_autotriar(projeto: ProtocoloTriagem, user, registro: RegistroTriagem) -> bool:
    """Só no modo ANCO: curador do projeto, ou quem importou a base do registro."""
    if not projeto.eh_anco:
        return False
    if projeto.eh_curador_no(user):
        return True
    return user.id in dup.importadores(registro)


def registros_para_autotriar(projeto: ProtocoloTriagem, user):
    """Identificados (não no acervo) que o usuário pode autotriar."""
    qs = projeto.registros.filter(status=_St.IDENTIFICADO, ja_no_acervo=False).order_by("criado_em")
    if projeto.eh_curador_no(user):
        return qs
    return qs.filter(origem_buscas__criado_por=user).distinct()


def registros_decididos_do_usuario(projeto: ProtocoloTriagem, user, status=None):
    """Decididos que o usuário pode rever/desfazer. `status` filtra (incluídos
    e/ou excluídos); padrão = ambos."""
    sts = status or (_St.INCLUIDO, _St.EXCLUIDO)
    qs = projeto.registros.filter(status__in=sts).order_by("-decidida_em", "-criado_em")
    if projeto.eh_curador_no(user):
        return qs
    return qs.filter(origem_buscas__criado_por=user).distinct()


@transaction.atomic
def autotriar(registro: RegistroTriagem, decisao: str, *, por, motivo: str = "") -> str:
    """Aplica a decisão do dono e consolida (revisor único). Retorna o status.

    Cria a `DecisaoTriagem` já concluída — que **não** dispara o signal (este só
    age na transição de `concluido_em`) —, por isso a avaliação é chamada aqui.
    """
    agora = timezone.now()
    registro.status = _St.EM_TRIAGEM
    registro.save(update_fields=["status"])
    DecisaoTriagem.objects.create(
        registro=registro,
        revisor=por,
        etapa=_Et.TITULO_RESUMO,
        decisao=decisao,
        motivo_exclusao=motivo if decisao == RegistroTriagem.Decisao.EXCLUIR else "",
        concluido_em=agora,
        prazo_em=agora,
    )
    resultado = avaliar_apos_triagem(registro)
    if resultado.decidida:
        # Importado tarde para evitar ciclo de import com tasks.
        from .tasks import avancar_apos_status

        avancar_apos_status(registro)  # promove ao acervo se incluído
    atualizar_relevancia(registro)
    return registro.status


@transaction.atomic
def reverter_inclusao(registro: RegistroTriagem, *, por, motivo: str = "") -> bool:
    """Exclui um registro **incluído** (Revisão ANCO): volta a `excluido` e sai do
    pool de análise. Remove o `Artigo` promovido **somente** se foi criado por esta
    triagem — não-legado, sem análises e sem outro registro o referenciando
    (o acervo curado nunca é tocado). Retorna True se reverteu.
    """
    if registro.status != _St.INCLUIDO:
        return False

    artigo = registro.artigo
    pode_apagar_artigo = bool(
        artigo
        and not artigo.eh_legado
        and artigo.analises.count() == 0
        and artigo.registros_triagem.exclude(pk=registro.pk).count() == 0
    )

    registro.status = _St.EXCLUIDO
    registro.decisao_final = RegistroTriagem.Decisao.EXCLUIR
    registro.motivo_exclusao = motivo
    registro.decidida_por = por
    registro.decidida_em = timezone.now()
    registro.artigo = None
    registro.save(
        update_fields=[
            "status",
            "decisao_final",
            "motivo_exclusao",
            "decidida_por",
            "decidida_em",
            "artigo",
        ]
    )
    if pode_apagar_artigo:
        artigo.delete()
    return True


@transaction.atomic
def desfazer_autotriagem(registro: RegistroTriagem, *, por) -> bool:
    """Desfaz a decisão de um registro decidido: volta a `identificado`.

    Remove as decisões de triagem e o `Artigo` promovido órfão (não-legado, sem
    análises, sem outro registro o referenciando). O acervo curado é preservado.
    Retorna True se desfez.
    """
    if registro.status not in (_St.INCLUIDO, _St.EXCLUIDO):
        return False

    artigo = registro.artigo
    pode_apagar_artigo = bool(
        artigo
        and not artigo.eh_legado
        and artigo.analises.count() == 0
        and artigo.registros_triagem.exclude(pk=registro.pk).count() == 0
    )

    registro.status = _St.IDENTIFICADO
    registro.decisao_final = ""
    registro.motivo_exclusao = ""
    registro.decidida_por = None
    registro.decidida_em = None
    registro.artigo = None
    registro.save(
        update_fields=[
            "status",
            "decisao_final",
            "motivo_exclusao",
            "decidida_por",
            "decidida_em",
            "artigo",
        ]
    )
    DecisaoTriagem.objects.filter(registro=registro).delete()
    if pode_apagar_artigo:
        artigo.delete()
    return True
