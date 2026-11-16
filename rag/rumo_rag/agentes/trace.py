from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any

from .mensagem import Mensagem, Resposta


@dataclass
class Interacao:
    mensagem: Mensagem
    resposta: Resposta
    horario: str


class Trace:
    """Registro ordenado das interações entre agentes."""

    def __init__(self) -> None:
        self.interacoes: list[Interacao] = []

    def registrar(
        self,
        mensagem: Mensagem,
        resposta: Resposta,
    ) -> None:
        self.interacoes.append(
            Interacao(
                mensagem=mensagem,
                resposta=resposta,
                horario=datetime.now(timezone.utc).isoformat(),
            )
        )

    def para_dict(self) -> dict[str, Any]:
        return {
            "interacoes": [
                {
                    "mensagem": asdict(interacao.mensagem),
                    "resposta": asdict(interacao.resposta),
                    "horario": interacao.horario,
                }
                for interacao in self.interacoes
            ]
        }

    def para_json(self) -> str:
        return json.dumps(self.para_dict(), ensure_ascii=False, indent=2)