import json
import sys
from pathlib import Path

_RAG = Path(__file__).resolve().parents[1]
if str(_RAG) not in sys.path:
    sys.path.insert(0, str(_RAG))

from rumo_rag.agentes.base import Agente
from rumo_rag.agentes.mensagem import Mensagem, Resposta
from rumo_rag.agentes.trace import Trace


class AgenteFake(Agente):
    nome = "Agente Fake"
    papel = "Teste"

    def executar(self, mensagem: Mensagem) -> Resposta:
        return Resposta(conteudo=f"Recebi: {mensagem.conteudo}")


def test_agente_fake_e_trace():
    agente = AgenteFake()
    mensagem = Mensagem(
        remetente="Orquestrador",
        destinatario=agente.nome,
        conteudo="Olá",
    )

    resposta = agente.executar(mensagem)

    trace = Trace()
    trace.registrar(mensagem, resposta)
    registro = json.loads(trace.para_json())

    interacao = registro["interacoes"][0]
    assert resposta.conteudo == "Recebi: Olá"
    assert interacao["mensagem"]["remetente"] == "Orquestrador"
    assert interacao["mensagem"]["destinatario"] == "Agente Fake"
    assert interacao["horario"]