from dataclasses import dataclass, field
from typing import Any


@dataclass
class Mensagem:
    remetente: str
    destinatario: str
    conteudo: str
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass
class Resposta:
    conteudo: str
    fontes: list[dict[str, Any]] = field(default_factory=list)
    confianca: float | None = None
    alertas: list[str] = field(default_factory=list)