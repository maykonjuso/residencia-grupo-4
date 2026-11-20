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
import json
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


class _AgenteStub(agentes.Agente):
    def __init__(
        self,
        id_agente: str,
        nome: str,
        atraso_s: float = 0.0,
        erro: Exception | None = None,
        resposta_fixa: str | None = None,
        trechos_fixos: list[dict] | None = None,
    ):
        self.id_agente = id_agente
        self.nome = nome
        self.papel = f"Stub de domínio {id_agente}"
        self.eixo = id_agente
        self._atraso_s = atraso_s
        self._erro = erro
        self._resposta_fixa = resposta_fixa
        self._trechos_fixos = trechos_fixos if trechos_fixos is not None else []
        self.mensagens_recebidas: list[agentes.Mensagem] = []

    def executar(self, mensagem: agentes.Mensagem) -> agentes.Resposta:
        self.mensagens_recebidas.append(mensagem)
        if self._atraso_s:
            time.sleep(self._atraso_s)
        if self._erro:
            raise self._erro
        backend = (mensagem.contexto or {}).get("backend", config.BACKEND)
        trechos = list(self._trechos_fixos)
        if isinstance(mensagem.contexto, dict):
            mensagem.contexto["trechos_recuperados"] = trechos
        resp = self._resposta_fixa or geracao.gerar(mensagem.conteudo, trechos, backend=backend)
        fontes = geracao.citacoes_usadas(resp, trechos)
        return agentes.Resposta(
            conteudo=resp,
            fontes=fontes,
            confianca=1.0 if trechos else 0.0,
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
                "Onde encontro informações sobre atendimento hoje no campus?"
            )
        m_d1.assert_called_once_with(
            "Onde encontro informações sobre atendimento hoje no campus?"
        )
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

    def test_decomposicao_roteamento_e_paralelismo_tres_e_quatro_subperguntas(self):
        agente_ru = _AgenteStub("ru", "Agente RU", atraso_s=0.12, resposta_fixa="Informação do RU [1].", trechos_fixos=[TRECHO_RU])
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", atraso_s=0.12, resposta_fixa="Informação do Fluxo [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        for n_subs, eixos in (
            (3, ["ru", "fluxo", "ru"]),
            (4, ["ru", "ru", "fluxo", "fluxo"]),
        ):
            itens = [
                {"pergunta": f"Subpergunta {i + 1}?", "eixo": eixos[i]}
                for i in range(n_subs)
            ]
            with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.95)), \
                 mock.patch.object(agentes.reescrita, "decompor_com_roteamento", return_value=itens):
                res = orq.executar("Pergunta composta com múltiplas partes?", backend="extrativo")

            self.assertEqual(len(res["subperguntas"]), n_subs)
            self.assertEqual(len(res["partes"]), n_subs)
            self.assertEqual([p["agente"] for p in res["partes"]], eixos)
            self.assertLess(res["tempo_paralelo_s"], res["soma_tempos_individuais_s"])


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
        # Resposta alucinada (R$ 99,90 não existe no TRECHO_RU) aciona retentativa com feedback no mesmo backend
        agente_ru = _AgenteStub(
            "ru",
            "Agente RU",
            resposta_fixa="O almoço custa R$ 99,90 e tem frango grelhado [1].",
            trechos_fixos=[TRECHO_RU],
        )
        orq = agentes.Orquestrador(agente_ru=agente_ru)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)), \
             mock.patch.object(
                 agentes.geracao,
                 "gerar_com_instrucoes",
                 return_value="No almoço será servido frango grelhado [1].",
             ) as m_gerar_instr:
            res = orq.executar("O que tem no almoço?", backend="ollama")

        self.assertEqual(m_gerar_instr.call_count, 1)
        kwargs = m_gerar_instr.call_args.kwargs
        self.assertEqual(kwargs["backend"], "ollama")
        self.assertIn("R$ 99,90", kwargs["instrucoes"])

        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        self.assertFalse(etapa_val["resultados"][0]["aprovado_inicial"])
        self.assertTrue(etapa_val["resultados"][0]["aprovado"])
        devolucoes = etapa_val["devolucoes_ao_sintetizador"]
        self.assertEqual(len(devolucoes), 1)
        self.assertEqual(devolucoes[0]["agente"], "ru")
        self.assertEqual(devolucoes[0]["acao"], "retentativa_com_feedback")
        self.assertIn("R$ 99,90", devolucoes[0]["resposta_anterior"])
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
                     {"pergunta": "Quanto custa o almoço no RU?", "eixo": "ru"},
                     {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                 ],
             ), \
             mock.patch.object(cli.agentes.indice, "_buscar_simples", side_effect=fake_buscar), \
             mock.patch("sys.stdout", buf):
            cli.main([
                "Quanto custa o almoço no RU e quais os pré-requisitos de Testes de Software?",
                "--agentes",
                "--trace",
                "--backend",
                "extrativo",
            ])

        saida = buf.getvalue()
        self.assertIn("[TRACE · Orquestrador Multiagentes]", saida)
        self.assertIn("Subpergunta 1: Quanto custa o almoço no RU?", saida)
        self.assertIn("Subpergunta 2: Quais os pré-requisitos de Testes de Software?", saida)
        self.assertIn("[Agente RU]", saida)
        self.assertIn("[Agente Fluxo]", saida)
        self.assertIn("3. Execução em paralelo:", saida)
        self.assertIn("4. Validador factual:", saida)
        self.assertIn("5. Composição (Sintetizador):", saida)
        self.assertIn("F09", saida)
        self.assertIn("F20", saida)


class TestContratoAgentesEValidacao(unittest.TestCase):
    def test_agente_ru_cumpre_contrato_e_executa_opcao_a(self):
        agente = agentes.AgenteRU(k=3, modo="bm25")
        self.assertIsInstance(agente, agentes.Agente)

        msg = agentes.Mensagem(
            remetente="Orquestrador",
            destinatario=agente.nome,
            conteudo="Quanto custa o almoço no RU?",
            contexto={"backend": "extrativo"},
        )
        with mock.patch.object(agentes.indice, "buscar", return_value=[TRECHO_RU]) as m_buscar:
            resp = agente.executar(msg)

        m_buscar.assert_called_once_with(
            "Quanto custa o almoço no RU?",
            k=3,
            modo="bm25",
            eixo="ru",
            decompor_pergunta=False,
        )
        self.assertIsInstance(resp, agentes.Resposta)
        self.assertIn("frango grelhado", resp.conteudo.lower())
        self.assertIn("[1]", resp.conteudo)
        self.assertEqual(len(resp.fontes), 1)
        self.assertEqual(resp.fontes[0]["doc_id"], "F09")
        self.assertAlmostEqual(resp.confianca, 0.82)
        self.assertEqual(resp.alertas, [])
        self.assertEqual(msg.contexto["trechos_recuperados"], [TRECHO_RU])

    def test_orquestrador_comunica_por_mensagem_resposta_e_trace_oficial(self):
        class _AgenteFakePuro(agentes.Agente):
            def __init__(self, nome: str, papel: str, resposta: str, fontes: list[dict]):
                self.nome = nome
                self.papel = papel
                self.recebidas: list[agentes.Mensagem] = []
                self._resposta = resposta
                self._fontes = fontes

            def executar(self, mensagem: agentes.Mensagem) -> agentes.Resposta:
                self.recebidas.append(mensagem)
                return agentes.Resposta(conteudo=self._resposta, fontes=self._fontes, confianca=0.95)

        fake_ru = _AgenteFakePuro(
            nome="Agente RU Fake",
            papel="RU",
            resposta="O almoço custa R$ 6,10 [1].",
            fontes=[{
                "doc_id": "F01",
                "titulo": "Valores das refeições",
                "orgao": "UnB",
                "pagina": 1,
                "url": "https://ru.unb.br",
                "chunk_id": "F01-0001",
                "texto": "Estudantes de graduação pagam R$ 6,10 pelo almoço.",
            }],
        )
        fake_fluxo = _AgenteFakePuro(
            nome="Agente Fluxo Fake",
            papel="Fluxo",
            resposta="Requer Métodos de Desenvolvimento de Software [1].",
            fontes=[{
                "doc_id": "F20",
                "titulo": "Matriz curricular",
                "orgao": "UnB",
                "pagina": 4,
                "url": "https://software.unb.br",
                "chunk_id": "F20-0012",
            }],
        )
        orq = agentes.Orquestrador(agente_ru=fake_ru, agente_fluxo=fake_fluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.91)), \
             mock.patch.object(
                 agentes.reescrita,
                 "decompor_com_roteamento",
                 return_value=[
                     {"pergunta": "Quanto custa o almoço no RU?", "eixo": "ru"},
                     {"pergunta": "Qual o pré-requisito de Testes de Software?", "eixo": "fluxo"},
                 ],
             ):
            res = orq.executar(
                "Quanto custa o almoço no RU e qual o pré-requisito de Testes de Software?",
                backend="extrativo",
            )

        # Verifica envio real de objetos Mensagem
        self.assertEqual(len(fake_ru.recebidas), 1)
        self.assertEqual(fake_ru.recebidas[0].remetente, "Orquestrador")
        self.assertEqual(fake_ru.recebidas[0].destinatario, "Agente RU Fake")
        self.assertEqual(len(fake_fluxo.recebidas), 1)

        # Trace oficial serializável em JSON com trocas de Mensagem -> Resposta
        json_dump = json.dumps(res, ensure_ascii=False)
        self.assertIn("interacoes", json_dump)
        interacoes = res["trace_agentes"]["interacoes"]
        destinatarios = [it["mensagem"]["destinatario"] for it in interacoes]
        self.assertIn("Agente RU Fake", destinatarios)
        self.assertIn("Agente Fluxo Fake", destinatarios)
        self.assertIn("Agente Validador", destinatarios)
        self.assertIn("Sintetizador", destinatarios)
        self.assertTrue(all(it["horario"] for it in interacoes))

    def test_agente_fluxo_cumpre_contrato_e_executa_opcao_a(self):
        agente = agentes.AgenteFluxo(k=3, modo="bm25")
        self.assertIsInstance(agente, agentes.Agente)

        msg = agentes.Mensagem(
            remetente="Orquestrador",
            destinatario=agente.nome,
            conteudo="Quais os pré-requisitos de Testes de Software?",
            contexto={"backend": "extrativo"},
        )
        with mock.patch.object(agentes.indice, "buscar", return_value=[TRECHO_FLUXO]) as m_buscar:
            resp = agente.executar(msg)

        m_buscar.assert_called_once_with(
            "Quais os pré-requisitos de Testes de Software?",
            k=3,
            modo="bm25",
            eixo="fluxo",
            decompor_pergunta=False,
        )
        self.assertIsInstance(resp, agentes.Resposta)
        self.assertIn("testes de software", resp.conteudo.lower())
        self.assertIn("[1]", resp.conteudo)
        self.assertEqual(len(resp.fontes), 1)
        self.assertEqual(resp.fontes[0]["doc_id"], "F20")
        self.assertAlmostEqual(resp.confianca, 0.79)
        self.assertEqual(resp.alertas, [])
        self.assertEqual(msg.contexto["trechos_recuperados"], [TRECHO_FLUXO])

    def test_orquestrador_padrao_instancia_agente_ru_e_agente_fluxo(self):
        orq = agentes.Orquestrador()
        self.assertIsInstance(orq.agentes["ru"], agentes.AgenteRU)
        self.assertIsInstance(orq.agentes["fluxo"], agentes.AgenteFluxo)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)), \
             mock.patch.object(agentes.indice, "buscar", return_value=[TRECHO_RU]):
            res = orq.executar("Quanto custa o almoço no RU?", backend="extrativo")

        self.assertFalse(res["degradado"])
        self.assertIn("frango grelhado", res["resposta"].lower())
        self.assertEqual(res["fontes_citadas"][0]["doc_id"], "F09")

    def test_validador_executar_via_contrato_mensagem_resposta(self):
        validador = agentes.AgenteValidador()
        self.assertIsInstance(validador, agentes.Agente)

        msg_ok = agentes.Mensagem(
            remetente="Orquestrador",
            destinatario=validador.nome,
            conteudo="No almoço terá frango grelhado [1].",
            contexto={"trechos": [TRECHO_RU], "fontes": [{"n": 1, "doc_id": "F09"}]},
        )
        resp_ok = validador.executar(msg_ok)
        self.assertEqual(resp_ok.conteudo, "APROVADO")
        self.assertEqual(resp_ok.confianca, 1.0)
        self.assertEqual(resp_ok.alertas, [])

        msg_err = agentes.Mensagem(
            remetente="Orquestrador",
            destinatario=validador.nome,
            conteudo="O almoço custa R$ 99,90 sem fonte.",
            contexto={"trechos": [TRECHO_RU], "fontes": []},
        )
        resp_err = validador.executar(msg_err)
        self.assertEqual(resp_err.conteudo, "REPROVADO")
        self.assertEqual(resp_err.confianca, 0.0)
        self.assertTrue(any("R$ 99,90" in a for a in resp_err.alertas))
        self.assertTrue(any("RN-02" in a for a in resp_err.alertas))

    def test_validador_limite_de_uma_retentativa_e_recusa_final(self):
        agente_ru = _AgenteStub(
            "ru",
            "Agente RU",
            resposta_fixa="O almoço custa R$ 99,90 [1].",
            trechos_fixos=[TRECHO_RU],
        )
        orq = agentes.Orquestrador(agente_ru=agente_ru)

        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)), \
             mock.patch.object(
                 agentes.geracao,
                 "gerar_com_instrucoes",
                 return_value="Ainda com preço inventado R$ 88,80 [1].",
             ) as m_gerar:
            res = orq.executar("Qual o preço do almoço?", backend="hf")

        # Só pode tentar reparar 1 vez (1 chamada ao mesmo backend com feedback)
        self.assertEqual(m_gerar.call_count, 1)
        self.assertEqual(m_gerar.call_args.kwargs["backend"], "hf")
        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        devolucoes = etapa_val["devolucoes_ao_sintetizador"]
        self.assertEqual(len(devolucoes), 1)
        self.assertEqual(devolucoes[0]["acao"], "retentativa_com_feedback")
        self.assertEqual(devolucoes[0]["tentativa"], 1)
        self.assertTrue(devolucoes[0]["recusa_final"])
        self.assertTrue(devolucoes[0]["aprovado_apos_devolucao"])
        self.assertEqual(res["resposta"], geracao.RECUSA)

    def test_cada_agente_possui_e_utiliza_prompt_proprio(self):
        ag_ru = agentes.AgenteRU(modo="bm25")
        ag_fluxo = agentes.AgenteFluxo(modo="bm25")

        # Prompts distintos entre si e diferentes do prompt genérico
        self.assertNotEqual(ag_ru.instrucoes, ag_fluxo.instrucoes)
        self.assertNotEqual(ag_ru.instrucoes, geracao.INSTRUCOES)
        self.assertNotEqual(ag_fluxo.instrucoes, geracao.INSTRUCOES)

        # Ambos mantêm RN-02 e RN-03
        for instr in (ag_ru.instrucoes, ag_fluxo.instrucoes):
            self.assertIn("[1]", instr)
            self.assertIn(f'diga exatamente: "{geracao.RECUSA}"', instr)

        prompts_capturados = []

        def fake_ollama(msgs):
            prompts_capturados.append(msgs[0]["content"])
            return "Resposta fundamentada [1]."

        with mock.patch.object(agentes.geracao, "_gerar_ollama", side_effect=fake_ollama):
            with mock.patch.object(agentes.indice, "buscar", return_value=[TRECHO_RU]):
                ag_ru.executar(
                    agentes.Mensagem(
                        remetente="Orquestrador",
                        destinatario=ag_ru.nome,
                        conteudo="Quanto custa o almoço no RU?",
                        contexto={"backend": "ollama"},
                    )
                )
            with mock.patch.object(agentes.indice, "buscar", return_value=[TRECHO_FLUXO]):
                ag_fluxo.executar(
                    agentes.Mensagem(
                        remetente="Orquestrador",
                        destinatario=ag_fluxo.nome,
                        conteudo="Quais os pré-requisitos?",
                        contexto={"backend": "ollama"},
                    )
                )

        self.assertEqual(prompts_capturados, [ag_ru.instrucoes, ag_fluxo.instrucoes])
        self.assertEqual(ag_ru.montar_mensagens("Q?", [TRECHO_RU])[0]["content"], ag_ru.instrucoes)
        self.assertEqual(ag_fluxo.montar_mensagens("Q?", [TRECHO_FLUXO])[0]["content"], ag_fluxo.instrucoes)

    def test_decomposicao_acionada_em_cruzamento_ru_fluxo_mesmo_abaixo_do_limiar_d1(self):
        agente_ru = _AgenteStub("ru", "Agente RU", resposta_fixa="O RU abre às 11h [1].", trechos_fixos=[TRECHO_RU])
        agente_fluxo = _AgenteStub("fluxo", "Agente Fluxo", resposta_fixa="Requer FGA0313 [1].", trechos_fixos=[TRECHO_FLUXO])
        orq = agentes.Orquestrador(agente_ru=agente_ru, agente_fluxo=agente_fluxo)

        pergunta = "Quais os pré-requisitos de Testes de Software e que horas abre o RU?"
        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.3503)):
            res = orq.executar(pergunta, backend="extrativo")

        self.assertEqual(len(res["subperguntas"]), 2)
        self.assertEqual([p["agente"] for p in res["partes"]], ["fluxo", "ru"])
        self.assertEqual(len(agente_fluxo.mensagens_recebidas), 1)
        self.assertEqual(len(agente_ru.mensagens_recebidas), 1)
        self.assertIn("pré-requisitos", agente_fluxo.mensagens_recebidas[0].conteudo.lower())
        self.assertIn("ru", agente_ru.mensagens_recebidas[0].conteudo.lower())

    def test_agentes_recusam_perguntas_fora_do_seu_dominio(self):
        ag_ru = agentes.AgenteRU(modo="bm25")
        ag_fluxo = agentes.AgenteFluxo(modo="bm25")

        with mock.patch.object(agentes.indice, "buscar", side_effect=AssertionError("Não devia buscar fora do domínio")):
            resp_ru = ag_ru.executar(
                agentes.Mensagem(
                    remetente="Orquestrador",
                    destinatario=ag_ru.nome,
                    conteudo="Quais os pré-requisitos de Testes de Software?",
                    contexto={"backend": "extrativo"},
                )
            )
            resp_fluxo = ag_fluxo.executar(
                agentes.Mensagem(
                    remetente="Orquestrador",
                    destinatario=ag_fluxo.nome,
                    conteudo="Qual o cardápio do almoço no RU?",
                    contexto={"backend": "extrativo"},
                )
            )

        self.assertEqual(resp_ru.conteudo, geracao.RECUSA)
        self.assertEqual(resp_ru.fontes, [])
        self.assertEqual(resp_ru.confianca, 0.0)
        self.assertTrue(any("fora do domínio" in a.lower() for a in resp_ru.alertas))

        self.assertEqual(resp_fluxo.conteudo, geracao.RECUSA)
        self.assertEqual(resp_fluxo.fontes, [])
        self.assertEqual(resp_fluxo.confianca, 0.0)
        self.assertTrue(any("fora do domínio" in a.lower() for a in resp_fluxo.alertas))

    def test_recusa_do_llm_nao_carrega_citacoes_espurias(self):
        ag_ru = agentes.AgenteRU(modo="bm25")
        resposta_suja = (
            f"{geracao.RECUSA} [1][2] Sugiro consultar a Diretoria do RU sobre créditos."
        )
        msg = agentes.Mensagem(
            remetente="Orquestrador",
            destinatario=ag_ru.nome,
            conteudo="Que horas abre o RU?",
            contexto={"backend": "ollama"},
        )
        with mock.patch.object(agentes.indice, "buscar", return_value=[TRECHO_RU]), \
             mock.patch.object(agentes.geracao, "_gerar_ollama", return_value=resposta_suja):
            resp = ag_ru.executar(msg)

        self.assertEqual(resp.conteudo, geracao.RECUSA)
        self.assertEqual(resp.fontes, [])
        self.assertEqual(resp.confianca, 0.0)

    def test_orquestrador_usa_backend_openai_na_decomposicao_e_nos_agentes(self):
        agentes.reescrita._decompor_llm_com_eixo.cache_clear()
        orq = agentes.Orquestrador()
        requisicoes = []

        def fake_urlopen(req, timeout=180):
            body = json.loads(req.data.decode("utf-8"))
            requisicoes.append((req.full_url, dict(req.header_items()), body))
            system_msg = body["messages"][0]["content"]
            if "módulo de reescrita e decomposição" in system_msg:
                conteudo = json.dumps({
                    "subperguntas": [
                        {"pergunta": "Quanto custa o almoço no RU?", "eixo": "ru"},
                        {"pergunta": "Quais os pré-requisitos de Testes de Software?", "eixo": "fluxo"},
                    ]
                })
            elif "Agente RU" in system_msg:
                conteudo = "No almoço será servido frango grelhado [1]."
            else:
                conteudo = "Requer Métodos de Desenvolvimento de Software [1]."
            payload = json.dumps({"choices": [{"message": {"content": conteudo}}]}).encode("utf-8")
            resp_http = io.BytesIO(payload)
            resp_http.__enter__ = lambda s: s
            resp_http.__exit__ = lambda s, *a: False
            return resp_http

        def fake_buscar(pergunta, k=config.TOP_K, modo="hibrido", eixo=None, decompor_pergunta=False):
            return [TRECHO_RU] if eixo == "ru" else [TRECHO_FLUXO]

        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-teste"}, clear=False), \
             mock.patch.object(agentes.config, "OPENAI_URL", "https://openrouter.ai/api/v1/"), \
             mock.patch.object(agentes.config, "OPENAI_MODEL", "qwen/qwen-2.5-72b-instruct"), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(True, 0.88)), \
             mock.patch.object(agentes.indice, "buscar", side_effect=fake_buscar), \
             mock.patch.object(agentes.reescrita, "_decompor_ollama_bruto", side_effect=AssertionError), \
             mock.patch.object(agentes.reescrita, "_decompor_hf_bruto", side_effect=AssertionError), \
             mock.patch.object(agentes.geracao, "_gerar_ollama", side_effect=AssertionError), \
             mock.patch.object(agentes.geracao, "_gerar_hf", side_effect=AssertionError):
            res = orq.executar(
                "O que tem no almoço e quais os pré-requisitos de Testes de Software?",
                backend="openai",
            )

        self.assertEqual(len(requisicoes), 3)  # 1 decomposição + 2 agentes
        for url, headers, body in requisicoes:
            self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(headers.get("Authorization"), "Bearer sk-or-teste")
            self.assertEqual(headers.get("User-agent"), "RUmo-UnB/1.0")
            self.assertEqual(body["model"], "qwen/qwen-2.5-72b-instruct")
        self.assertEqual([p["agente"] for p in res["partes"]], ["ru", "fluxo"])
        self.assertIn("frango grelhado [1]", res["resposta"])
        self.assertIn("Métodos de Desenvolvimento de Software [1]", res["resposta"])
        self.assertFalse(res["degradado"])


if __name__ == "__main__":
    unittest.main()
