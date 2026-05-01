#!/usr/bin/env python3
"""
Aplica correções automáticas de DOI no arquivo base_referencial.

Corrige apenas os casos seguros (categoria 'prefixo_doi'):
  - Remove prefixo "DOI: " / "doi:"
  - Extrai DOI de "2-s2.0-XXXXXXX ; 10.XXXX/..."
  - Extrai DOI de URL "https://doi.org/10.XXXX/..."

Uso:
    python tools/corrigir_dois.py                  # dry-run (mostra o que faria)
    python tools/corrigir_dois.py --aplicar        # grava o arquivo corrigido
    python tools/corrigir_dois.py --aplicar --saida arquivo_corrigido.json
"""

import argparse
import json
import sys
from pathlib import Path

# Reutiliza a lógica de classificação do script irmão
sys.path.insert(0, str(Path(__file__).parent))
from verificar_dois import classificar


ARQUIVO_PADRAO = "docs/base_referencial_analise_cognitiva (1).json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("arquivo", nargs="?", default=ARQUIVO_PADRAO)
    parser.add_argument(
        "--aplicar", action="store_true",
        help="Grava as correções (sem esta flag, só exibe o diff)",
    )
    parser.add_argument(
        "--saida", metavar="ARQUIVO.json",
        help="Destino do JSON corrigido (padrão: sobrescreve o original)",
    )
    args = parser.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.exists():
        print(f"Arquivo não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)

    with caminho.open(encoding="utf-8") as f:
        dados = json.load(f)

    correcoes = []
    for registro in dados:
        doi_original = registro.get("Numero_DOI", "") or ""
        categoria, doi_norm, obs = classificar(doi_original)
        if categoria == "prefixo_doi":
            correcoes.append({
                "linha": registro.get("_linha"),
                "titulo": registro.get("Titulo_do_artigo", "")[:60],
                "de": doi_original,
                "para": doi_norm,
                "motivo": obs,
            })

    print(f"Correções automáticas disponíveis: {len(correcoes)}\n")
    for c in correcoes:
        print(f"  linha {c['linha']:>5} | {c['de']!r:<55} → {c['para']!r}")

    if not correcoes:
        print("Nenhuma correção a aplicar.")
        return

    if not args.aplicar:
        print(f"\n[dry-run] Use --aplicar para gravar as {len(correcoes)} correções.")
        return

    # Aplica
    indice = {c["linha"]: c["para"] for c in correcoes}
    for registro in dados:
        linha = registro.get("_linha")
        if linha in indice:
            registro["Numero_DOI"] = indice[linha]

    destino = Path(args.saida) if args.saida else caminho
    with destino.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"\n{len(correcoes)} DOIs corrigidos → {destino}")


if __name__ == "__main__":
    main()
