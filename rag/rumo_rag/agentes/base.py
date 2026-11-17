from abc import ABC, abstractmethod

from .mensagem import Mensagem, Resposta


class Agente(ABC):
    """Contrato comum para os agentes do RUmo."""

    nome: str
    papel: str

    @abstractmethod
    def executar(self, mensagem: Mensagem) -> Resposta:
        """Processa uma mensagem e retorna uma resposta."""
        raise NotImplementedError