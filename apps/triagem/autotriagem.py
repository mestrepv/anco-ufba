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
