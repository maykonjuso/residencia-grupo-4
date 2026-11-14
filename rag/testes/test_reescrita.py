"""Testes unitários e de integração para o pipeline de reescrita e decomposição de consultas.

Cobre os dois estágios (reescrita.py) e a integração de busca com subperguntas (indice.py):
1. Estágio 1: classificar_composta (System-1 / LiquidAI d1-omni-600M, pré-filtro e conectivos)
2. Estágio 2: decompor (Ollama HTTP, HuggingFace transformers, fallback sintático)
3. Integração: buscar_com_subperguntas (round-robin, deduplicação por chunk_id, teto MAX_TRECHOS)
"""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

RAG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG))

from rumo_rag import config, indice, reescrita


class TestClassificarComposta(unittest.TestCase):
    """Testes unitários do Estágio 1: detecção de perguntas compostas."""

    def test_pergunta_vazia_ou_espacos(self):
        eh_composta, prob = reescrita.classificar_composta("")
        self.assertFalse(eh_composta)
        self.assertEqual(prob, 0.0)

        eh_composta, prob = reescrita.classificar_composta("   ")
        self.assertFalse(eh_composta)
        self.assertEqual(prob, 0.0)

    def test_multiplos_pontos_de_interrogacao_atalho_deterministico(self):
        with mock.patch.object(reescrita, "_carregar_decisor") as mock_decisor:
            eh_composta, prob = reescrita.classificar_composta("Quanto custa o almoço? E que horas abre?")
            self.assertTrue(eh_composta)
            self.assertEqual(prob, 0.95)
            # O atalho determinístico não deve carregar o modelo neural
            mock_decisor.assert_not_called()

    def test_sem_conectivos_classifica_como_simples_sem_llm(self):
        with mock.patch.object(reescrita, "_carregar_decisor") as mock_decisor:
            eh_composta, prob = reescrita.classificar_composta("Qual é o horário do almoço no RU")
            self.assertFalse(eh_composta)
            self.assertEqual(prob, 0.0)
            mock_decisor.assert_not_called()

    def test_com_conectivo_classificada_como_composta_pelo_modelo(self):
        mock_modelo = mock.MagicMock()
        mock_modelo.system_one.return_value = {
            "answers": {
                "query_structure": {
                    "probabilities": {"single": 0.12, "multiple": 0.88}
                }
            }
        }
        with mock.patch.object(reescrita, "_carregar_decisor", return_value=mock_modelo):
            eh_composta, prob = reescrita.classificar_composta("Quanto pago no almoço e até que horas ele funciona")
            self.assertTrue(eh_composta)
            self.assertEqual(prob, 0.88)
            mock_modelo.system_one.assert_called_once()

    def test_com_conectivo_classificada_como_simples_pelo_modelo(self):
        mock_modelo = mock.MagicMock()
        mock_modelo.system_one.return_value = {
            "answers": {
                "query_structure": {
                    "probabilities": {"single": 0.78, "multiple": 0.22}
                }
            }
        }
        with mock.patch.object(reescrita, "_carregar_decisor", return_value=mock_modelo):
            eh_composta, prob = reescrita.classificar_composta("Quero saber se o RU abre para almoço ou jantar")
            self.assertFalse(eh_composta)
            self.assertEqual(prob, 0.22)
            mock_modelo.system_one.assert_called_once()

    def test_falha_do_decisor_retorna_fallback_gracioso(self):
        with mock.patch.object(reescrita, "_carregar_decisor", side_effect=RuntimeError("CUDA out of memory")):
            eh_composta, prob = reescrita.classificar_composta("Quanto pago no almoço e até que horas ele funciona")
            self.assertFalse(eh_composta)
            self.assertEqual(prob, 0.0)


class TestDecompor(unittest.TestCase):
    """Testes unitários do Estágio 2: decomposição contextual e fallbacks."""

    def test_pergunta_simples_retorna_lista_vazia(self):
        with mock.patch.object(reescrita, "classificar_composta", return_value=(False, 0.0)):
            subs = reescrita.decompor("Qual o horário do almoço no RU?")
            self.assertEqual(subs, [])

    def test_decompor_com_mock_ollama(self):
        resposta_ollama = {
            "message": {
                "content": json.dumps({
                    "subperguntas": [
                        "Quanto custa o almoço no RU da FCTE?",
                        "Até que horas funciona o RU no campus Gama?"
                    ]
                })
            }
        }
        resposta_bytes = json.dumps(resposta_ollama).encode("utf-8")
        mock_resp = io.BytesIO(resposta_bytes)

        with mock.patch.object(reescrita, "classificar_composta", return_value=(True, 0.95)), \
                mock.patch("urllib.request.urlopen", return_value=mock_resp):
            reescrita._decompor_llm.cache_clear()
            subs = reescrita.decompor("Quanto pago no almoço do RU e até que horas ele funciona no Gama?", backend="ollama")
            self.assertEqual(len(subs), 2)
            self.assertEqual(subs[0], "Quanto custa o almoço no RU da FCTE?")
            self.assertEqual(subs[1], "Até que horas funciona o RU no campus Gama?")

    def test_decompor_com_mock_hf(self):
        mock_tok = mock.MagicMock()
        mock_modelo = mock.MagicMock()
        mock_modelo.device = "cpu"

        mock_entrada = {"input_ids": mock.MagicMock()}
        mock_entrada["input_ids"].shape = [1, 10]
        mock_tok.apply_chat_template.return_value.to.return_value = mock_entrada

        mock_modelo.generate.return_value = [[0] * 20]
        saida_json = (
            "```json\n"
            '{"subperguntas": ["Qual o preço do almoço no RU?", "Qual o horário do RU?"]}\n'
            "```"
        )
        mock_tok.decode.return_value = saida_json

        with mock.patch.object(reescrita, "classificar_composta", return_value=(True, 0.95)), \
                mock.patch("rumo_rag.geracao._hf", return_value=(mock_tok, mock_modelo)):
            reescrita._decompor_llm.cache_clear()
            subs = reescrita.decompor("Quanto pago no almoço do RU e até que horas ele funciona no Gama?", backend="hf")
            self.assertEqual(len(subs), 2)
            self.assertIn("Qual o preço do almoço no RU?", subs)
            self.assertIn("Qual o horário do RU?", subs)

    def test_decompor_fallback_sintatico_quando_llm_falha(self):
        with mock.patch.object(reescrita, "classificar_composta", return_value=(True, 0.95)), \
                mock.patch.object(reescrita, "_decompor_llm", side_effect=RuntimeError("Serviço LLM indisponível")):
            subs = reescrita.decompor("Quanto pago no almoço do RU e até que horas ele funciona no Gama?")
            self.assertIsInstance(subs, list)
            self.assertEqual(len(subs), 2)
            self.assertIn("Quanto pago no almoço do RU", subs)
            self.assertIn("até que horas ele funciona no Gama", subs)

    def test_decompor_backend_fallback_direto(self):
        with mock.patch.object(reescrita, "classificar_composta", return_value=(True, 0.95)):
            subs = reescrita.decompor("Quanto pago no almoço do RU e até que horas ele funciona no Gama?", backend="fallback")
            self.assertEqual(len(subs), 2)
            self.assertEqual(subs[0], "Quanto pago no almoço do RU")
            self.assertEqual(subs[1], "até que horas ele funciona no Gama")

    def test_extrair_subperguntas_json_variacoes(self):
        # JSON válido comum
        self.assertEqual(
            reescrita._extrair_subperguntas_json('{"subperguntas": ["Pergunta 1?", "Pergunta 2?"]}'),
            ["Pergunta 1?", "Pergunta 2?"]
        )
        # Markdown fence
        self.assertEqual(
            reescrita._extrair_subperguntas_json('Aqui está:\n```json\n{"subperguntas": ["Subpergunta A?", "Subpergunta B?"]}\n```'),
            ["Subpergunta A?", "Subpergunta B?"]
        )
        # String vazia ou inválida
        self.assertEqual(reescrita._extrair_subperguntas_json(""), [])
        self.assertEqual(reescrita._extrair_subperguntas_json("texto sem json"), [])
        # Subperguntas muito curtas (< 5 chars) são filtradas
        self.assertEqual(
            reescrita._extrair_subperguntas_json('{"subperguntas": ["abc", "Subpergunta válida?"]}'),
            ["Subpergunta válida?"]
        )

    def test_extrair_subperguntas_json_com_lista_direta(self):
        # Lista JSON direta emitida pelo LLM
        json_lista = '["Qual o valor do almoço no RU?", "Qual o horário de funcionamento?"]'
        subs = reescrita._extrair_subperguntas_json(json_lista)
        self.assertEqual(subs, ["Qual o valor do almoço no RU?", "Qual o horário de funcionamento?"])

        # Lista JSON envelopada em markdown
        json_md = '```json\n["Quanto custa o almoço?", "Quem tem direito à isenção?"]\n```'
        subs_md = reescrita._extrair_subperguntas_json(json_md)
        self.assertEqual(subs_md, ["Quanto custa o almoço?", "Quem tem direito à isenção?"])

    def test_extrair_subperguntas_json_com_literais_primitivos_nao_lanca_excecao(self):
        # Primitivos JSON válidos não devem lançar AttributeError nem qualquer exceção
        primitivos = ["null", "12345", "true", "false", '"apenas uma string"', "{}", "[]"]
        for p in primitivos:
            self.assertEqual(reescrita._extrair_subperguntas_json(p), [])
        # Tipos não-string ou nulos
        self.assertEqual(reescrita._extrair_subperguntas_json(None), [])
        self.assertEqual(reescrita._extrair_subperguntas_json(123), [])

    def test_decompor_fallback_pergunta_com_estudante_sem_gatilho(self):
        # Pergunta legítima contendo 'estudante' sem gatilho clássico no primeiro segmento
        # não deve ser descartada como contexto
        q = "O estudante de graduação paga taxa? Como solicitar isenção?"
        subs = reescrita._decompor_fallback(q)
        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0], "O estudante de graduação paga taxa")
        self.assertEqual(subs[1], "Como solicitar isenção")


class TestBuscarComSubperguntas(unittest.TestCase):
    """Testes de integração: recuperação intercalada round-robin e fusão de chunks."""

    def test_subperguntas_vazia_delega_para_buscar_simples(self):
        retorno_esperado = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
        with mock.patch.object(indice, "_buscar_simples", return_value=retorno_esperado) as mock_busca:
            res = indice.buscar_com_subperguntas("Pergunta simples", [], k=5)
            mock_busca.assert_called_once_with("Pergunta simples", k=5, modo="hibrido", eixo=None)
            self.assertEqual(res, retorno_esperado)

    def test_round_robin_interleaving_e_deduplicacao(self):
        # 2 subperguntas -> listas: sub1, sub2, pergunta_original
        # sub1: c1, c2, c3
        # sub2: c2, c4, c5  (c2 duplicado de sub1)
        # orig: c6, c1, c7  (c1 duplicado de sub1)
        respostas = {
            "sub1": [{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}],
            "sub2": [{"chunk_id": "c2"}, {"chunk_id": "c4"}, {"chunk_id": "c5"}],
            "pergunta global": [{"chunk_id": "c6"}, {"chunk_id": "c1"}, {"chunk_id": "c7"}],
        }

        def fake_buscar_simples(q, k, modo="hibrido", eixo=None):
            return respostas[q]

        with mock.patch.object(indice, "_buscar_simples", side_effect=fake_buscar_simples):
            res = indice.buscar_com_subperguntas("pergunta global", ["sub1", "sub2"], k=5)

            # k_final = min(5 + 2, MAX_TRECHOS(8)) = 7
            # Intercalação round-robin esperada sem duplicados:
            # pos 0: c1 (sub1), c2 (sub2), c6 (orig)
            # pos 1: c2 (pula), c4 (sub2), c1 (pula)
            # pos 2: c3 (sub1), c5 (sub2), c7 (orig)
            # Ordem resultante: [c1, c2, c6, c4, c3, c5, c7] (total 7)
            ids = [c["chunk_id"] for c in res]
            self.assertEqual(ids, ["c1", "c2", "c6", "c4", "c3", "c5", "c7"])
            # Garante que não há repetições
            self.assertEqual(len(ids), len(set(ids)))

    def test_limite_k_final_e_teto_max_trechos(self):
        # 6 subperguntas com k=5 -> min(5 + 6, config.MAX_TRECHOS=8) = 8
        subs = [f"sub_{i}" for i in range(6)]

        def fake_buscar_simples(q, k, modo="hibrido", eixo=None):
            # Retorna 10 chunks únicos por consulta
            prefix = q.replace(" ", "_")
            return [{"chunk_id": f"{prefix}_{idx}"} for idx in range(10)]

        with mock.patch.object(indice, "_buscar_simples", side_effect=fake_buscar_simples):
            res = indice.buscar_com_subperguntas("pergunta original", subs, k=5)
            self.assertEqual(len(res), config.MAX_TRECHOS)
            self.assertEqual(len(res), 8)

    def test_buscar_aciona_decomposicao_por_padrao(self):
        with mock.patch.object(indice, "decompor", return_value=["s1", "s2"]) as mock_decomp, \
                mock.patch.object(indice, "buscar_com_subperguntas", return_value=[{"chunk_id": "c1"}]) as mock_fusao:
            res = indice.buscar("pergunta composta", k=5, decompor_pergunta=True)
            mock_decomp.assert_called_once_with("pergunta composta", backend="auto")
            mock_fusao.assert_called_once_with("pergunta composta", ["s1", "s2"], k=5, modo="hibrido", eixo=None)
            self.assertEqual(res, [{"chunk_id": "c1"}])

    def test_buscar_com_decompor_falso_chama_buscar_simples_direto(self):
        with mock.patch.object(indice, "decompor") as mock_decomp, \
                mock.patch.object(indice, "_buscar_simples", return_value=[{"chunk_id": "c1"}]) as mock_simples:
            res = indice.buscar("pergunta qualquer", k=5, decompor_pergunta=False)
            mock_decomp.assert_not_called()
            mock_simples.assert_called_once_with("pergunta qualquer", k=5, modo="hibrido", eixo=None)
            self.assertEqual(res, [{"chunk_id": "c1"}])


if __name__ == "__main__":
    unittest.main()
