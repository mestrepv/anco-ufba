"""Migra projetos `modo=anco` do `apps/triagem` para o `apps/anco`.

Mapa: ProtocoloTriagem→ProjetoANCO, ProjetoMembro→MembroANCO, Busca→FonteImport,
RegistroTriagem→ItemCorpus, Sorteio/Atribuição/Consenso→*ANCO. Duplicatas
(status DUPLICADO) são ignoradas; excluídos viram itens `removido=True`.

Idempotente: `--reset` apaga os dados ANCO do projeto antes de remigrar
(os `Artigo`/`Analise` do acervo NUNCA são tocados — `ItemCorpus.artigo` é
SET_NULL). `--dry-run` só relata o que faria. O acervo curado é intocável.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.anco.models import (
    AtribuicaoANCO,
    ConsensoANCO,
    FonteImport,
    ItemCorpus,
    MembroANCO,
    ProjetoANCO,
    SorteioANCO,
)
from apps.triagem.models import (
    Busca,
    ConsensoAnalise,
    ProjetoMembro,
    ProtocoloTriagem,
    RegistroTriagem,
    SorteioAnalise,
)


class Command(BaseCommand):
    help = "Migra projetos modo=anco do apps/triagem para o apps/anco."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--projeto", help="slug de um projeto específico (default: todos anco)")
        parser.add_argument("--dry-run", action="store_true", help="não grava; só relata")
        parser.add_argument(
            "--reset", action="store_true", help="apaga dados ANCO do projeto antes de remigrar"
        )

    def handle(self, *args, **opts) -> None:
        qs = ProtocoloTriagem.objects.filter(modo=ProtocoloTriagem.Modo.ANCO)
        if opts["projeto"]:
            qs = qs.filter(slug=opts["projeto"])
        if not qs.exists():
            self.stdout.write(self.style.WARNING("Nenhum projeto ANCO encontrado."))
            return
        for proto in qs.order_by("id"):
            self._migrar(proto, dry=opts["dry_run"], reset=opts["reset"])

    # ------------------------------------------------------------------ #

    def _migrar(self, proto: ProtocoloTriagem, *, dry: bool, reset: bool) -> None:
        regs = RegistroTriagem.objects.filter(protocolo=proto)
        por_status = {
            s: regs.filter(status=s).count() for s, _ in RegistroTriagem.Status.choices
        }
        dups = por_status.get(RegistroTriagem.Status.DUPLICADO, 0)
        excl = por_status.get(RegistroTriagem.Status.EXCLUIDO, 0)
        corpus_qs = regs.exclude(
            status__in=[RegistroTriagem.Status.DUPLICADO, RegistroTriagem.Status.EXCLUIDO]
        )
        corpus = corpus_qs.count()
        com_artigo = corpus_qs.filter(artigo__isnull=False).count()

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n== {proto.slug} ({proto.nome or proto.titulo}) =="))
        self.stdout.write(
            f"  membros={ProjetoMembro.objects.filter(projeto=proto).count()} "
            f"buscas={Busca.objects.filter(protocolo=proto).count()} "
            f"registros={regs.count()}"
        )
        self.stdout.write(f"  status: {por_status}")
        self.stdout.write(
            f"  → ItemCorpus ativos={corpus} (com Artigo/analisáveis={com_artigo}, "
            f"sem Artigo={corpus - com_artigo}), removidos(excluídos)={excl}, ignorados(dup)={dups}"
        )
        self.stdout.write(
            f"  sorteios={SorteioAnalise.objects.filter(projeto=proto).count()} "
            f"consensos={ConsensoAnalise.objects.filter(sorteio__projeto=proto).count()}"
        )

        if dry:
            self.stdout.write(self.style.NOTICE("  [dry-run] nada gravado."))
            return

        with transaction.atomic():
            projeto = self._projeto(proto, reset=reset)
            self._membros(proto, projeto)
            busca_map = self._fontes(proto, projeto)
            n_itens = self._itens(regs, projeto, busca_map)
            self._sorteios(proto, projeto)

        self.stdout.write(self.style.SUCCESS(f"  OK: {n_itens} itens de corpus migrados."))

    def _projeto(self, proto: ProtocoloTriagem, *, reset: bool) -> ProjetoANCO:
        projeto, criado = ProjetoANCO.objects.get_or_create(
            slug=proto.slug,
            defaults={
                "nome": proto.nome or proto.titulo,
                "pergunta_pesquisa": proto.pergunta_pesquisa,
                "estrategia_busca": proto.estrategia_busca,
                "arquivado": proto.arquivado,
            },
        )
        if not criado:
            if not reset:
                raise CommandError(
                    f"Projeto {proto.slug!r} já existe em apps/anco. Use --reset para remigrar."
                )
            # Limpa só os dados ANCO deste projeto (acervo nunca é tocado).
            projeto.itens.all().delete()
            projeto.fontes.all().delete()
            projeto.membros.all().delete()
            projeto.sorteios.all().delete()
            projeto.consensos.all().delete()
            projeto.nome = proto.nome or proto.titulo
            projeto.pergunta_pesquisa = proto.pergunta_pesquisa
            projeto.estrategia_busca = proto.estrategia_busca
            projeto.arquivado = proto.arquivado
            projeto.save()
        return projeto

    def _membros(self, proto: ProtocoloTriagem, projeto: ProjetoANCO) -> None:
        for m in ProjetoMembro.objects.filter(projeto=proto):
            MembroANCO.objects.get_or_create(
                projeto=projeto, usuario_id=m.usuario_id, defaults={"papel": m.papel}
            )

    def _fontes(self, proto: ProtocoloTriagem, projeto: ProjetoANCO) -> dict:
        busca_map: dict[int, FonteImport] = {}
        for b in Busca.objects.filter(protocolo=proto):
            fonte = FonteImport.objects.create(
                projeto=projeto,
                base_consulta_id=b.base_consulta_id,
                outra_base=b.outra_base,
                string_busca=b.string_busca,
                data_busca=b.data_busca,
                formato=b.formato,
                n_lidos=b.n_lidos,
                n_novos=b.n_novos,
                n_duplicados=b.n_duplicados,
                n_ignorados=b.n_ignorados,
                importado_em=b.importado_em,
                criado_por_id=b.criado_por_id,
            )
            busca_map[b.id] = fonte
        return busca_map

    def _itens(self, regs, projeto: ProjetoANCO, busca_map: dict) -> int:
        n = 0
        for r in regs.exclude(status=RegistroTriagem.Status.DUPLICADO):
            removido = r.status == RegistroTriagem.Status.EXCLUIDO
            item, _ = ItemCorpus.objects.get_or_create(
                projeto=projeto,
                identificador=r.identificador,
                defaults={
                    "titulo": r.titulo,
                    "autores": r.autores,
                    "ano": r.ano,
                    "doi": r.doi,
                    "isbn": r.isbn,
                    "resumo": r.resumo,
                    "palavras_chaves": r.palavras_chaves,
                    "titulo_periodico": r.titulo_periodico,
                    "idioma": r.idioma,
                    "link": r.link,
                    "tipo": r.tipo,
                    "artigo_id": r.artigo_id,
                    "removido": removido,
                    "motivo_remocao": (r.motivo_exclusao or "") if removido else "",
                },
            )
            for b in r.origem_buscas.all():
                fonte = busca_map.get(b.id)
                if fonte:
                    item.origem_fontes.add(fonte)
            n += 1
        return n

    def _sorteios(self, proto: ProtocoloTriagem, projeto: ProjetoANCO) -> None:
        sort_map: dict[int, SorteioANCO] = {}
        for s in SorteioAnalise.objects.filter(projeto=proto):
            ns = SorteioANCO.objects.create(
                projeto=projeto,
                modo_revisao=s.modo_revisao,
                cota=s.cota,
                semente=s.semente,
                observacoes=s.observacoes,
                criado_por_id=s.criado_por_id,
            )
            sort_map[s.id] = ns
            for a in s.atribuicoes.all():
                AtribuicaoANCO.objects.create(
                    sorteio=ns, analista_id=a.analista_id, artigo_id=a.artigo_id
                )
        for c in ConsensoAnalise.objects.filter(sorteio__projeto=proto):
            nc = ConsensoANCO.objects.create(
                projeto=projeto,
                artigo_id=c.artigo_id,
                sorteio=sort_map.get(c.sorteio_id),
                analise_final_id=c.analise_final_id,
                conciliado_por_id=c.conciliado_por_id,
                conciliado_em=c.conciliado_em,
            )
            nc.analises.set(c.analises.all())
