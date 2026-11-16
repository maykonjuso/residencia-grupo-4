"""Testes unitários e de integração do Orquestrador multiagentes (Épico #37).

Valida sem exigir GPU ou internet:
1. Classificação, decomposição (via reescrita.py, limiar 0,39) e roteamento por domínio.
2. Execução em paralelo dos agentes de domínio (tempo_paralelo_s < soma_tempos_individuais_s).
3. Composição mantendo os índices [n] e fontes isolados por parte (sem misturar citações).
4. Validador factual detectando erro/ausência de citação e devolvendo ao Sintetizador.
5. Degradação elegante quando um agente falha.
6. Invocação direta pela CLI (`python -m rumo_rag "..." --agentes --trace`).
"""
import io
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

RAG = Path(__file__).resolve().parents[1]
if str(RAG) not in sys.path:
    sys.path.insert(0, str(RAG))

from rumo_rag import __main__ as cli  # noqa: E402
from rumo_rag import agentes, config, geracao  # noqa: E402

TRECHO_RU = {
    "chunk_id": "F09-0001",
    "doc_id": "F09",
    "titulo": "Cardápio semanal do RU Gama",
    "orgao": "UnB · Diretoria do RU",
    "pagina": 2,
    "secao": "Quarta-feira · Almoço",
    "similaridade": 0.82,
    "nota_rrf": 0.032,
    "url": "https://ru.unb.br/wp-content/uploads/2026/11/Gama-Semana-04-09-11-a-15-11.pdf",
    "texto": "No almoço de quarta-feira será servido frango grelhado, arroz, feijão e proteína de soja ao molho.",
}

TRECHO_FLUXO = {
    "chunk_id": "F20-0012",
    "doc_id": "F20",
    "titulo": "Matriz curricular de Engenharia de Software",
    "orgao": "UnB · FCTE",
    "pagina": 4,
    "secao": "Fluxo e pré-requisitos",
    "similaridade": 0.79,
    "nota_rrf": 0.029,
    "url": "https://software.unb.br/matriz-curricular/",
    "texto": "A disciplina Testes de Software (FGA0238) tem como pré-requisito Métodos de Desenvolvimento de Software.",
}


class _AgenteStub(agentes.AgenteBase):
    def __init__(self, id_agente: str, nome: str, atraso_s: float = 0.0, erro: Exception | None = None, resposta_fixa: str | None = None, trechos_fixos: list[dict] | None = None):
        self.id_agente = id_agente
        self.nome = nome
        self.eixo = id_agente
        self._atraso_s = atraso_s
        self._erro = erro
        self._resposta_fixa = resposta_fixa
        self._trechos_fixos = trechos_fixos if trechos_fixos is not None else []

    def responder(self, subpergunta: str, k: int = config.TOP_K, backend: str = config.BACKEND) -> agentes.RespostaAgente:
        t0 = time.monotonic()
        if self._atraso_s:
            time.sleep(self._atraso_s)
        if self._erro:
            raise self._erro
        trechos = list(self._trechos_fixos)
        resp = self._resposta_fixa or geracao.gerar(subpergunta, trechos, backend=backend)
        t1 = time.monotonic()
        return agentes.RespostaAgente(
            agente=self.id_agente,
            nome_agente=self.nome,
            subpergunta=subpergunta,
            resposta=resp,
            trechos_recuperados=trechos,
            fontes_citadas=geracao.citacoes_usadas(resp, trechos),
            tempo_busca_s=0.01,
            tempo_geracao_s=round(t1 - t0, 3),
            tempo_total_s=round(t1 - t0, 3),
        )


class TestRoteamentoELimiar(unittest.TestCase):
    def test_limiar_calibrado_em_0_39(self):
        self.assertAlmostEqual(config.LIMIAR_COMPOSTA, 0.39)

    def test_rotear_subpergunta_simples_ru(self):
        self.assertEqual(agentes.rotear_subpergunta("O que tem no almoço do RU hoje?"), ["ru"])

    def test_rotear_subpergunta_simples_fluxo(self):
        self.assertEqual(
            agentes.rotear_subpergunta("Quais os pré-requisitos de Testes de Software?"),
            ["fluxo"],
        )

    def test_rotear_subpergunta_ambigua_aciona_ambos(self):
        self.assertEqual(
            agentes.rotear_subpergunta(
                "Qual o horário de atendimento no campus Gama?",
                usar_d1_fallback=False,
            ),
            ["ru", "fluxo"],
        )

    def test_rotear_subpergunta_aciona_d1_fallback_quando_regex_nao_casa(self):
        # Frase sem palavras-chave óbvias ("RU", "almoço"): aciona Teste 2 (d1-omni-600M)
        with mock.patch.object(
            agentes.reescrita, "classificar_dominio_d1", return_value=["ru"]
        ) as m_d1:
            rotas = agentes.rotear_subpergunta(
                "Onde vejo se a comida de hoje tem derivados de leite?"
            )
        m_d1.assert_called_once_with("Onde vejo se a comida de hoje tem derivados de leite?")
        self.assertEqual(rotas, ["ru"])

    def test_roteamento_aproveita_eixo_do_teste1_sem_depender_de_regex(self):
        agente_ru = _AgenteStub(
            "ru",
            "Agente RU",
            resposta_fixa="Lista de alergênicos no portal [1].",
            trechos_fixos=[TRECHO_RU],
        )
        agente_fluxo = _AgenteStub(
            "fluxo",
            "Agente Fluxo",
            resposta_fixa="Prazo conforme calendário [1].",
            trechos_fixos=[TRECHO_FLUXO],
        )
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.72)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "Onde vejo se a comida de hoje tem derivados de leite?", "eixo": "ru"},
                     {"pergunta": "Qual o prazo máximo para desistir de uma turma?", "eixo": "fluxo"},
                 ],
             ), \
             mock.patch.object(agentes.reescrita, "classificar_dominio_d1") as m_d1:
            res = orq.executar(
                "Onde vejo se a comida de hoje tem derivados de leite e qual o prazo máximo para desistir de uma turma?",
                backend="ollama",
            )

        m_d1.assert_not_called()
        self.assertEqual([p["agente"] for p in res["partes"]], ["ru", "fluxo"])

    def test_decomposicao_e_roteamento_composta(self):
        agente_ru = _AgenteStub("ru", "Agente RU", resposta_fixa="Frango grelhado e soja [1].", trechos_fixos=[TRECHO_RU])
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", resposta_fixa="Pré-requisito: MDS [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.85)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "O que tem no almoço do RU?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ):
            res = orq.executar(
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                backend="extrativo",
            )

        self.assertEqual(len(res["subperguntas"]), 2)
        rotas = [p["agente"] for p in res["partes"]]
        self.assertEqual(rotas, ["ru", "fluxo"])


class TestParalelismoEComposicao(unittest.TestCase):
    def test_execucao_paralela_menor_que_soma_individual(self):
        agente_ru = _AgenteStub("ru", "Agente RU", atraso_s=0.25, resposta_fixa="Frango grelhado [1].", trechos_fixos=[TRECHO_RU])
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", atraso_s=0.25, resposta_fixa="Requisito: MDS [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.90)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "O que tem no almoço?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ):
            res = orq.executar(
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                backend="extrativo",
            )

        self.assertGreaterEqual(res["soma_tempos_individuais_s"], 0.48)
        self.assertLess(res["tempo_paralelo_s"], res["soma_tempos_individuais_s"])
        self.assertGreater(res["ganho_paralelismo_s"], 0.15)

    def test_compoe_sem_misturar_indices_n(self):
        agente_ru = _AgenteStub("ru", "Agente RU", resposta_fixa="Cardápio: frango grelhado [1].", trechos_fixos=[TRECHO_RU])
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", resposta_fixa="Requer Métodos de Desenvolvimento [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.90)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "O que tem no almoço?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ):
            res = orq.executar(
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                backend="extrativo",
            )

        parte_ru, parte_fluxo = res["partes"]
        self.assertIn("[1]", parte_ru["resposta"])
        self.assertEqual(parte_ru["fontes_citadas"][0]["n"], 1)
        self.assertEqual(parte_ru["fontes_citadas"][0]["doc_id"], "F09")

        self.assertIn("[1]", parte_fluxo["resposta"])
        self.assertEqual(parte_fluxo["fontes_citadas"][0]["n"], 1)
        self.assertEqual(parte_fluxo["fontes_citadas"][0]["doc_id"], "F20")

        # Nenhuma parte teve o [1] renumerado para [2]
        self.assertNotIn("[2]", res["resposta"])


class TestValidadorEDegradacao(unittest.TestCase):
    def test_validador_reprova_valor_inventado_e_devolve_ao_sintetizador(self):
        # Resposta alucinada (R$ 99,90 não existe no TRECHO_RU) aciona devolução ao Sintetizador
        agente_ru = _AgenteStub(
            "ru",
            "Agente RU",
            resposta_fixa="O almoço custa R$ 99,90 e tem frango grelhado [1].",
            trechos_fixos=[TRECHO_RU],
        )
        orq = agentes.Orquestrador(agente_ru=agente_ru)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("O que tem no almoço?", backend="hf")

        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        devolucoes = etapa_val["devolucoes_ao_sintetizador"]
        self.assertEqual(len(devolucoes), 1)
        self.assertEqual(devolucoes[0]["agente"], "ru")
        self.assertEqual(devolucoes[0]["acao"], "fallback_extrativo")
        self.assertTrue(devolucoes[0]["aprovado_apos_devolucao"])
        self.assertNotIn("R$ 99,90", res["resposta"])

    def test_validador_detecta_ausencia_de_citacao(self):
        val = agentes.AgenteValidador()
        item = agentes.RespostaAgente(
            agente="ru",
            nome_agente="Agente RU",
            subpergunta="O que tem no almoço?",
            resposta="Hoje tem frango grelhado.",
            trechos_recuperados=[TRECHO_RU],
        )
        parecer = val.validar(item)
        self.assertFalse(parecer.aprovado)
        self.assertTrue(parecer.sem_citacao)
        self.assertEqual(parecer.acao_recomendada, "devolver_ao_sintetizador")

    def test_degradacao_elegante_quando_um_agente_falha(self):
        agente_ru = _AgenteStub("ru", "Agente RU", erro=RuntimeError("Banco indisponível"))
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", resposta_fixa="Requer Métodos de Desenvolvimento [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.90)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "O que tem no almoço?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ):
            res = orq.executar(
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                backend="extrativo",
            )

        self.assertTrue(res["degradado"])
        self.assertEqual(len(res["avisos"]), 1)
        self.assertIn("Agente RU", res["avisos"][0])
        self.assertIn("Requer Métodos de Desenvolvimento [1].", res["resposta"])
        self.assertEqual(res["fontes_citadas"][0]["doc_id"], "F20")

    def test_degradacao_por_parametro_falhar_agente(self):
        agente_ru = _AgenteStub("ru", "Agente RU", resposta_fixa="Frango grelhado [1].", trechos_fixos=[TRECHO_RU])
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", resposta_fixa="Requer MDS [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.90)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "O que tem no almoço?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ):
            res = orq.executar(
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                backend="extrativo",
                falhar_agente="fluxo",
            )

        self.assertTrue(res["degradado"])
        self.assertIn("Agente Fluxo", res["avisos"][0])
        self.assertIn("Frango grelhado [1].", res["resposta"])


class TestCliAgentesTrace(unittest.TestCase):
    def test_cli_direta_com_agentes_e_trace(self):
        def fake_buscar(pergunta, k=config.TOP_K, modo="hibrido", eixo=None):
            if eixo == "ru":
                return [TRECHO_RU]
            return [TRECHO_FLUXO]

        buf = io.StringIO()
        with mock.patch.object(cli.agentes.reescrita, "classificar_composta", return_value=(True, 0.87)), \
             mock.patch.object(
                 cli.agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "O que tem no almoço?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ), \
             mock.patch.object(cli.agentes.indice, "_buscar_simples", side_effect=fake_buscar), \
             mock.patch("sys.stdout", buf):
            cli.main([
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                "--agentes",
                "--trace",
                "--backend",
                "extrativo",
            ])

        saida = buf.getvalue()
        self.assertIn("[TRACE · Orquestrador Multiagentes]", saida)
        self.assertIn("Subpergunta 1: O que tem no almoço?", saida)
        self.assertIn("Subpergunta 2: Quais os pré-requisitos de Testes de Software?", saida)
        self.assertIn("[Agente RU]", saida)
        self.assertIn("[Agente Fluxo]", saida)
        self.assertIn("3. Execução em paralelo:", saida)
        self.assertIn("4. Validador factual:", saida)
        self.assertIn("5. Composição (Sintetizador):", saida)
        self.assertIn("F09", saida)
        self.assertIn("F20", saida)


if __name__ == "__main__":
    unittest.main()
