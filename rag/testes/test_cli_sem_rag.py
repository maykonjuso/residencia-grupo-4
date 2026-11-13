"""Testes de unidade e integração da flag CLI --sem-rag e da geração pura sem RAG.

Cobre os requisitos das Issues #17 e #28:
- Função geracao.gerar_sem_rag e montagem de mensagens
- Parâmetro sem_rag na função responder de __main__
- Flag CLI --sem-rag e formatação de saída (texto e JSON)
- Garantia de que índice e trechos não são consultados no modo sem RAG
"""
import io
import json
import unittest
from unittest import mock

from rag.rumo_rag import __main__ as cli
from rag.rumo_rag import geracao


class TestGeracaoSemRag(unittest.TestCase):
    def test_montar_mensagens_sem_rag(self):
        msgs = geracao.montar_mensagens_sem_rag("Qual o horário do RU?")
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("assistente acadêmico", msgs[0]["content"])
        self.assertEqual(msgs[1]["role"], "user")
        self.assertEqual(msgs[1]["content"], "Qual o horário do RU?")

    def test_gerar_sem_rag_ollama(self):
        with mock.patch.object(geracao, "_gerar_ollama", return_value="O RU funciona até as 19h.") as m_ollama:
            resp = geracao.gerar_sem_rag("Qual o horário do RU?", backend="ollama")
            self.assertEqual(resp, "O RU funciona até as 19h.")
            m_ollama.assert_called_once()
            msgs_passadas = m_ollama.call_args[0][0]
            self.assertEqual(msgs_passadas[1]["content"], "Qual o horário do RU?")

    def test_gerar_sem_rag_hf(self):
        with mock.patch.object(geracao, "_gerar_hf", return_value="Resposta via HuggingFace.") as m_hf:
            resp = geracao.gerar_sem_rag("Pergunta de teste", backend="hf")
            self.assertEqual(resp, "Resposta via HuggingFace.")
            m_hf.assert_called_once()

    def test_gerar_sem_rag_openai(self):
        with mock.patch.object(geracao, "_gerar_openai", return_value="Resposta via OpenAI.") as m_openai:
            resp = geracao.gerar_sem_rag("Pergunta de teste", backend="openai")
            self.assertEqual(resp, "Resposta via OpenAI.")
            m_openai.assert_called_once()

    def test_gerar_sem_rag_extrativo_retorna_aviso(self):
        resp = geracao.gerar_sem_rag("Pergunta", backend="extrativo")
        self.assertIn("Modo sem RAG requer backend de LLM", resp)

    def test_gerar_sem_rag_auto_usa_backend_padrao(self):
        with mock.patch.object(geracao, "_gerar_hf", return_value="Resp auto") as m_hf, \
             mock.patch.object(geracao.config, "BACKEND", "hf"):
            resp = geracao.gerar_sem_rag("Pergunta", backend="auto")
            self.assertEqual(resp, "Resp auto")
            m_hf.assert_called_once()


class TestCliResponderSemRag(unittest.TestCase):
    def test_responder_sem_rag_nao_consulta_indice_nem_decompoe(self):
        with mock.patch.object(cli.indice, "buscar_com_subperguntas") as m_busca, \
             mock.patch.object(cli.indice, "decompor") as m_decompor, \
             mock.patch.object(cli.geracao, "gerar") as m_gerar, \
             mock.patch.object(cli.geracao, "gerar_sem_rag", return_value="Resposta sem RAG") as m_sem_rag:

            resultado = cli.responder("Quanto custa o almoço?", backend="ollama", sem_rag=True)

            m_busca.assert_not_called()
            m_decompor.assert_not_called()
            m_gerar.assert_not_called()
            m_sem_rag.assert_called_once_with("Quanto custa o almoço?", backend="ollama")

            self.assertEqual(resultado["resposta"], "Resposta sem RAG")
            self.assertEqual(resultado["subperguntas"], [])
            self.assertEqual(resultado["trechos_recuperados"], [])
            self.assertEqual(resultado["fontes_citadas"], [])
            self.assertEqual(resultado["valores_sem_fonte"], [])
            self.assertFalse(resultado["sem_citacao"])
            self.assertEqual(resultado["tempo_busca_s"], 0.0)
            self.assertEqual(resultado["tempo_decomposicao_s"], 0.0)

    def test_responder_com_rag_consulta_indice_e_geracao(self):
        trecho_mock = [{"chunk_id": "c1", "doc_id": "D1", "titulo": "T", "orgao": "O", "pagina": 1, "url": "http://", "texto": "txt"}]
        with mock.patch.object(cli.indice, "buscar_com_subperguntas", return_value=trecho_mock) as m_busca, \
             mock.patch.object(cli.indice, "decompor", return_value=[]) as m_decompor, \
             mock.patch.object(cli.geracao, "gerar", return_value="Resposta com RAG [1].") as m_gerar, \
             mock.patch.object(cli.geracao, "gerar_sem_rag") as m_sem_rag:

            resultado = cli.responder("Quanto custa o almoço?", backend="ollama", sem_rag=False)

            m_busca.assert_called_once()
            m_decompor.assert_called_once()
            m_gerar.assert_called_once()
            m_sem_rag.assert_not_called()
            self.assertEqual(resultado["resposta"], "Resposta com RAG [1].")
            self.assertEqual(len(resultado["trechos_recuperados"]), 1)


class TestCliMainParserSemRag(unittest.TestCase):
    def test_perguntar_cli_sem_rag_saida_texto(self):
        with mock.patch.object(cli.geracao, "gerar_sem_rag", return_value="O almoço custa R$ 5,00 puro.") as m_sem_rag, \
             mock.patch.object(cli.indice, "buscar_com_subperguntas") as m_busca:
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                cli.main(["perguntar", "Quanto", "custa", "o", "almoco?", "--sem-rag", "--backend", "ollama"])

            m_busca.assert_not_called()
            m_sem_rag.assert_called_once_with("Quanto custa o almoco?", backend="ollama")
            saida = buf.getvalue()
            self.assertIn("Modo: Sem RAG (LLM puro)", saida)
            self.assertIn("O almoço custa R$ 5,00 puro.", saida)
            self.assertNotIn("Trechos recuperados:", saida)

    def test_perguntar_cli_sem_rag_saida_json(self):
        with mock.patch.object(cli.geracao, "gerar_sem_rag", return_value="Resposta em JSON sem RAG.") as m_sem_rag, \
             mock.patch.object(cli.indice, "buscar_com_subperguntas") as m_busca:
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                cli.main(["perguntar", "Como", "faco", "matricula?", "--sem-rag", "--saida", "json", "--backend", "hf"])

            m_busca.assert_not_called()
            m_sem_rag.assert_called_once()
            obj = json.loads(buf.getvalue())
            self.assertEqual(obj["pergunta"], "Como faco matricula?")
            self.assertEqual(obj["resposta"], "Resposta em JSON sem RAG.")
            self.assertTrue(obj["sem_rag"])
            self.assertEqual(obj["trechos_recuperados"], [])

    def test_perguntar_cli_com_rag_saida_json(self):
        trecho_mock = [{"chunk_id": "c1", "doc_id": "D1", "titulo": "T", "orgao": "O", "pagina": 1, "url": "http://", "texto": "txt"}]
        with mock.patch.object(cli.indice, "buscar_com_subperguntas", return_value=trecho_mock), \
             mock.patch.object(cli.indice, "decompor", return_value=[]), \
             mock.patch.object(cli.geracao, "gerar", return_value="Com RAG [1]."):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                cli.main(["perguntar", "Qual", "o", "fluxo?", "--saida", "json", "--backend", "extrativo"])

            obj = json.loads(buf.getvalue())
            self.assertEqual(obj["pergunta"], "Qual o fluxo?")
            self.assertEqual(obj["resposta"], "Com RAG [1].")
            self.assertFalse(obj.get("sem_rag", False))
            self.assertEqual(len(obj["trechos_recuperados"]), 1)

    def test_imprimir_modo_sem_rag(self):
        buf = io.StringIO()
        res = {
            "pergunta": "Pergunta teste",
            "resposta": "Resposta teste puro",
            "backend": "ollama",
            "tempo_geracao_s": 0.42,
            "sem_rag": True,
        }
        with mock.patch("sys.stdout", buf):
            cli.imprimir(res)
        saida = buf.getvalue()
        self.assertIn("Modo: Sem RAG (LLM puro)", saida)
        self.assertIn("Resposta (ollama):", saida)
        self.assertIn("Resposta teste puro", saida)
        self.assertIn("(geração 0.42s)", saida)

    def test_resposta_sem_rag_respeita_chaves_padrao(self):
        with mock.patch.object(cli.geracao, "gerar_sem_rag", return_value="Resp"):
            r = cli.responder("Pergunta", "hf", sem_rag=True)
        esperadas = {
            "pergunta",
            "subperguntas",
            "resposta",
            "fontes_citadas",
            "valores_sem_fonte",
            "sem_citacao",
            "trechos_recuperados",
            "tempo_decomposicao_s",
            "tempo_busca_s",
            "tempo_geracao_s",
            "backend",
        }
        self.assertEqual(set(r), esperadas)


if __name__ == "__main__":
    unittest.main()
