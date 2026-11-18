"""Testes do Agente Validador ativo (Issue #43 / Épico #37).

Valida com agentes fake (dublês), sem rede, sem GPU e sem consumir cota de LLM:
1. Resposta com número inventado é reprovada e devolvida ao sintetizador.
2. Resposta sem citação [n] (RN-02) é reprovada e devolvida.
3. A retentativa acontece no máximo uma vez.
4. Reprovando duas vezes, a saída é recusa honesta (RECUSA) — nunca a resposta ruim.
5. O trace registra a reprovação, o motivo e a segunda tentativa.
6. Recusa legítima por falta de base é aprovada de primeira sem devolução.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

RAG = Path(__file__).resolve().parents[1]
if str(RAG) not in sys.path:
    sys.path.insert(0, str(RAG))

from rumo_rag import agentes, geracao  # noqa: E402
from rumo_rag.agentes.base import Agente  # noqa: E402
from rumo_rag.agentes.mensagem import Mensagem, Resposta  # noqa: E402
from rumo_rag.agentes.validador import AgenteValidador  # noqa: E402

TRECHO_PRECO_RU = {
    "chunk_id": "F04-0000",
    "doc_id": "F04",
    "titulo": "Valores das refeições e grupos de acesso",
    "orgao": "UnB · Diretoria do RU",
    "pagina": 1,
    "secao": "Grupos e valores",
    "similaridade": 0.91,
    "nota_rrf": 0.033,
    "url": "https://ru.unb.br/precos-e-grupos/",
    "texto": "Estudantes do grupo II pagam R$ 5,20 no almoço do Restaurante Universitário.",
}


class _AgenteFakeSequencia(Agente):
    """Dublê que devolve uma resposta pré-programada por tentativa, sem chamar LLM."""

    nome = "Agente Fake RU"
    papel = "Dublê de testes para validação factual"

    def __init__(self, respostas: list[Resposta], trechos: list[dict] | None = None):
        self._respostas = list(respostas)
        self._trechos = [TRECHO_PRECO_RU] if trechos is None else list(trechos)
        self.chamadas = 0
        self.mensagens: list[Mensagem] = []

    def executar(self, mensagem: Mensagem) -> Resposta:
        self.mensagens.append(mensagem)
        idx = min(self.chamadas, len(self._respostas) - 1)
        self.chamadas += 1
        if isinstance(mensagem.contexto, dict):
            mensagem.contexto["trechos_recuperados"] = list(self._trechos)
        return self._respostas[idx]


class TestAgenteValidadorAtivo(unittest.TestCase):
    def test_agente_validador_contrato_executar_aprova_e_reprova(self):
        validador = AgenteValidador()
        self.assertIsInstance(validador, Agente)

        resp_ok = validador.executar(
            Mensagem(
                remetente="Orquestrador",
                destinatario=validador.nome,
                conteudo="Estudantes do grupo II pagam R$ 5,20 no almoço [1].",
                contexto={"trechos": [TRECHO_PRECO_RU], "fontes": [{"n": 1, "doc_id": "F04"}]},
            )
        )
        self.assertEqual(resp_ok.conteudo, "APROVADO")
        self.assertEqual(resp_ok.alertas, [])

        resp_bad = validador.executar(
            Mensagem(
                remetente="Orquestrador",
                destinatario=validador.nome,
                conteudo="O almoço custa R$ 99,90 [1].",
                contexto={"trechos": [TRECHO_PRECO_RU], "fontes": [{"n": 1, "doc_id": "F04"}]},
            )
        )
        self.assertEqual(resp_bad.conteudo, "REPROVADO")
        self.assertTrue(any("R$ 99,90" in a for a in resp_bad.alertas))

    def test_resposta_com_numero_inventado_e_reprovada_e_devolvida_ao_sintetizador(self):
        agente_fake = _AgenteFakeSequencia(
            respostas=[
                Resposta(
                    conteudo="O almoço custa R$ 99,90 [1].",
                    fontes=[{"n": 1, "doc_id": "F04", "titulo": "Valores", "orgao": "UnB", "pagina": 1, "url": "https://ru.unb.br/precos-e-grupos/", "chunk_id": "F04-0000"}],
                ),
                Resposta(
                    conteudo="Estudantes do grupo II pagam R$ 5,20 no almoço [1].",
                    fontes=[{"n": 1, "doc_id": "F04", "titulo": "Valores", "orgao": "UnB", "pagina": 1, "url": "https://ru.unb.br/precos-e-grupos/", "chunk_id": "F04-0000"}],
                ),
            ]
        )
        orq = agentes.Orquestrador(agente_ru=agente_fake)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("Quanto custa o almoço no RU?", backend="extrativo")

        self.assertEqual(agente_fake.chamadas, 2)
        self.assertIn("R$ 5,20", res["resposta"])
        self.assertNotIn("R$ 99,90", res["resposta"])
        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        self.assertFalse(etapa_val["resultados"][0]["aprovado_inicial"])
        self.assertTrue(etapa_val["resultados"][0]["aprovado"])
        self.assertTrue(etapa_val["devolucoes_ao_sintetizador"][0]["aprovado_apos_devolucao"])

    def test_resposta_sem_citacao_e_reprovada_e_corrigida_na_segunda_tentativa(self):
        agente_fake = _AgenteFakeSequencia(
            respostas=[
                Resposta(conteudo="Estudantes do grupo II pagam R$ 5,20 no almoço.", fontes=[]),
                Resposta(
                    conteudo="Estudantes do grupo II pagam R$ 5,20 no almoço [1].",
                    fontes=[{"n": 1, "doc_id": "F04", "titulo": "Valores", "orgao": "UnB", "pagina": 1, "url": "https://ru.unb.br/precos-e-grupos/", "chunk_id": "F04-0000"}],
                ),
            ]
        )
        orq = agentes.Orquestrador(agente_ru=agente_fake)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("Quanto custa o almoço no RU?", backend="extrativo")

        self.assertEqual(agente_fake.chamadas, 2)
        self.assertIn("R$ 5,20", res["resposta"])
        self.assertIn("[1]", res["resposta"])
        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        self.assertTrue(any("RN-02" in m for m in etapa_val["resultados"][0]["motivos_iniciais"]))
        self.assertTrue(etapa_val["resultados"][0]["aprovado"])

    def test_retentativa_acontece_no_maximo_uma_vez_e_recusa_final_ao_reprovar_duas_vezes(self):
        agente_fake = _AgenteFakeSequencia(
            respostas=[
                Resposta(conteudo="O almoço custa R$ 99,90 [1].", fontes=[]),
                Resposta(conteudo="Na verdade custa R$ 88,80 [1].", fontes=[]),
                Resposta(conteudo="Se chamasse uma terceira vez seria R$ 5,20 [1].", fontes=[]),
            ]
        )
        orq = agentes.Orquestrador(agente_ru=agente_fake)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("Quanto custa o almoço no RU?", backend="ollama")

        # Máximo 1 retentativa: 1 execução inicial + 1 retentativa = 2 chamadas totais
        self.assertEqual(agente_fake.chamadas, 2)
        self.assertEqual(len(agente_fake.mensagens), 2)
        self.assertTrue(agente_fake.mensagens[1].contexto["segunda_tentativa"])
        self.assertEqual(agente_fake.mensagens[1].contexto["tentativa"], 2)

        # Reprovando duas vezes, nunca entrega a resposta ruim: aplica recusa honesta
        self.assertEqual(res["resposta"], geracao.RECUSA)
        self.assertNotIn("R$ 99,90", res["resposta"])
        self.assertNotIn("R$ 88,80", res["resposta"])
        self.assertEqual(res["fontes_citadas"], [])

        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        devolucoes = etapa_val["devolucoes_ao_sintetizador"]
        self.assertEqual(len(devolucoes), 1)
        self.assertEqual(devolucoes[0]["tentativa"], 1)
        self.assertTrue(devolucoes[0]["segunda_tentativa"])
        self.assertTrue(devolucoes[0]["recusa_final"])

    def test_sintetizador_processar_devolucao_bloqueia_segunda_retentativa(self):
        sintetizador = agentes.Sintetizador()
        parte = agentes.RespostaAgente(
            agente="ru",
            nome_agente="Agente RU",
            subpergunta="Quanto custa o almoço?",
            resposta="O almoço custa R$ 88,80 [1].",
            trechos_recuperados=[TRECHO_PRECO_RU],
        )
        val = agentes.ResultadoValidacao(
            aprovado=False,
            valores_sem_fonte=["R$ 88,80"],
            sem_citacao=False,
            eh_recusa=False,
            motivos=["Valores sem respaldo nos trechos: R$ 88,80"],
            acao_recomendada="devolver_ao_sintetizador",
        )
        corrigida, evento = sintetizador.processar_devolucao(
            parte, val, backend="ollama", tentativa=2
        )
        self.assertEqual(corrigida.resposta, geracao.RECUSA)
        self.assertEqual(corrigida.fontes_citadas, [])
        self.assertEqual(evento["acao"], "recusa_apos_retentativa")
        self.assertFalse(evento["segunda_tentativa"])

    def test_trace_registra_reprovacao_motivo_e_segunda_tentativa(self):
        agente_fake = _AgenteFakeSequencia(
            respostas=[
                Resposta(conteudo="O almoço custa R$ 77,70 [1].", fontes=[]),
                Resposta(
                    conteudo="Estudantes do grupo II pagam R$ 5,20 no almoço [1].",
                    fontes=[{"n": 1, "doc_id": "F04", "titulo": "Valores", "orgao": "UnB", "pagina": 1, "url": "https://ru.unb.br/precos-e-grupos/", "chunk_id": "F04-0000"}],
                ),
            ]
        )
        orq = agentes.Orquestrador(agente_ru=agente_fake)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("Quanto custa o almoço no RU?", backend="extrativo")

        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        dev = etapa_val["devolucoes_ao_sintetizador"][0]
        self.assertTrue(any("R$ 77,70" in m for m in dev["motivos_reprovacao"]))
        self.assertEqual(dev["resposta_anterior"], "O almoço custa R$ 77,70 [1].")
        self.assertTrue(dev["segunda_tentativa"])
        self.assertIn("R$ 5,20", dev["resposta_segunda_tentativa"])

        # Trace oficial de interações registra reprovação, devolução, 2ª tentativa e revalidação
        interacoes = res["trace_agentes"]["interacoes"]
        reprovacoes = [
            it for it in interacoes
            if it["mensagem"]["destinatario"] == "Agente Validador"
            and it["resposta"]["conteudo"] == "REPROVADO"
        ]
        segundas_tentativas = [
            it for it in interacoes
            if it["mensagem"]["destinatario"] == "Agente Fake RU"
            and it["mensagem"]["contexto"].get("segunda_tentativa") is True
        ]
        self.assertEqual(len(reprovacoes), 1)
        self.assertTrue(any("R$ 77,70" in a for a in reprovacoes[0]["resposta"]["alertas"]))
        self.assertEqual(len(segundas_tentativas), 1)

    def test_recusa_legitima_por_falta_de_base_e_aprovada_sem_devolucao(self):
        agente_fake = _AgenteFakeSequencia(
            respostas=[Resposta(conteudo=geracao.RECUSA, fontes=[])],
            trechos=[],
        )
        orq = agentes.Orquestrador(agente_ru=agente_fake)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("Qual o preço do jantar hoje?", backend="extrativo")

        self.assertEqual(agente_fake.chamadas, 1)
        self.assertEqual(res["resposta"], geracao.RECUSA)
        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        self.assertEqual(etapa_val["devolucoes_ao_sintetizador"], [])
        self.assertTrue(etapa_val["resultados"][0]["aprovado"])


if __name__ == "__main__":
    unittest.main()
