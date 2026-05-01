"""Tipos compartilhados pelos serviços de lookup (Crossref, ISBN, etc.)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LookupResultado:
    """
    Resultado normalizado de um lookup de identificador externo (DOI, ISBN…).

    Os serviços individuais convertem o JSON da API de origem em `dados`
    com um conjunto consistente de chaves consumidas pelo template de
    preview do cadastro.
    """

    encontrado: bool = False
    erro: str = ""
    dados: dict = field(default_factory=dict)
