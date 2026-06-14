"""Migração triagem(modo=anco) → apps/anco (comando migrar_anco)."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.acervo.models import Artigo
from apps.anco.models import FonteImport, ItemCorpus, MembroANCO, ProjetoANCO
from apps.triagem.models import Busca, ProjetoMembro, ProtocoloTriagem, RegistroTriagem

User = get_user_model()
pytestmark = pytest.mark.django_db


def _proto_anco() -> ProtocoloTriagem:
    proto = ProtocoloTriagem.objects.create(nome="Piloto", modo=ProtocoloTriagem.Modo.ANCO)
    u = User.objects.create_user(username="c", email="c@u.edu", password="x")
    ProjetoMembro.objects.create(projeto=proto, usuario=u, papel="curador")
    busca = Busca.objects.create(protocolo=proto, outra_base="Scopus")
    art = Artigo.objects.create(titulo="Incluído", ano=2020)
    r_inc = RegistroTriagem.objects.create(
        protocolo=proto,
        titulo="Incluído",
        identificador="doi:10.1/inc",
        status=RegistroTriagem.Status.INCLUIDO,
        artigo=art,
    )
    r_inc.origem_buscas.add(busca)
    RegistroTriagem.objects.create(
        protocolo=proto,
        titulo="Pendente",
        identificador="doi:10.1/pend",
        status=RegistroTriagem.Status.IDENTIFICADO,
    )
    RegistroTriagem.objects.create(
        protocolo=proto,
        titulo="Excluído",
        identificador="doi:10.1/exc",
        status=RegistroTriagem.Status.EXCLUIDO,
        motivo_exclusao="fora do escopo",
    )
    RegistroTriagem.objects.create(
        protocolo=proto,
        titulo="Duplicado",
        identificador="doi:10.1/dup",
        status=RegistroTriagem.Status.DUPLICADO,
    )
    return proto


def test_migracao_cria_projeto_e_corpus():
    proto = _proto_anco()
    call_command("migrar_anco", "--projeto", proto.slug)
    proj = ProjetoANCO.objects.get(slug=proto.slug)
    assert MembroANCO.objects.filter(projeto=proj).count() == 1
    assert FonteImport.objects.filter(projeto=proj).count() == 1
    # INCLUIDO + IDENTIFICADO + EXCLUIDO migram (3); DUPLICADO é ignorado.
    assert ItemCorpus.objects.filter(projeto=proj).count() == 3
    assert ItemCorpus.objects.filter(projeto=proj, removido=True).count() == 1  # o excluído
    inc = ItemCorpus.objects.get(projeto=proj, identificador="doi:10.1/inc")
    assert inc.artigo_id is not None and inc.origem_fontes.count() == 1


def test_dry_run_nao_grava():
    proto = _proto_anco()
    call_command("migrar_anco", "--projeto", proto.slug, "--dry-run")
    assert not ProjetoANCO.objects.filter(slug=proto.slug).exists()


def test_reset_remigra_sem_duplicar():
    proto = _proto_anco()
    call_command("migrar_anco", "--projeto", proto.slug)
    call_command("migrar_anco", "--projeto", proto.slug, "--reset")
    proj = ProjetoANCO.objects.get(slug=proto.slug)
    assert ItemCorpus.objects.filter(projeto=proj).count() == 3


def test_sem_reset_em_projeto_existente_falha():
    proto = _proto_anco()
    call_command("migrar_anco", "--projeto", proto.slug)
    with pytest.raises(CommandError):
        call_command("migrar_anco", "--projeto", proto.slug)
