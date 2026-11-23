"""Testes das 4 ferramentas estruturadas dos agentes (#62)."""

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

RAG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG))

from rumo_rag import agentes, config, geracao  # noqa: E402
from rumo_rag.agentes import ferramentas  # noqa: E402
from rumo_rag.coleta import cardapio, scraper  # noqa: E402


class TestCardapioEMontarPrato(unittest.TestCase):
    def setUp(self):
        cardapio.resetar_estado_sincronizacao()
        self._patch_auto = mock.patch.object(config, "CARDAPIO_AUTO_FETCH", False)
        self._patch_auto.start()

    def tearDown(self):
        self._patch_auto.stop()
        cardapio.resetar_estado_sincronizacao()
    def test_cardapio_do_dia_devolve_compartimentos_e_fonte_f09(self):
        res = ferramentas.cardapio_do_dia("2026-11-09", "almoco")
        self.assertTrue(res.sucesso)
        self.assertFalse(res.recusado)
        self.assertEqual(res.dono, "Agente RU")
        self.assertEqual(res.fontes[0]["doc_id"], "F09")
        slots = {c["slot"] for c in res.dados["cardapios"][0]["compartimentos"]}
        self.assertTrue({"salada", "principal", "arroz", "feijao"} <= slots)

    def test_cardapio_do_dia_sem_data_na_base_recusa(self):
        res = ferramentas.cardapio_do_dia("2030-01-01", "almoco")
        self.assertFalse(res.sucesso)
        self.assertTrue(res.recusado)
        self.assertEqual(res.texto_base, geracao.RECUSA)
        self.assertEqual(res.dados["cardapios"], [])

    def test_montar_prato_vegano_com_justificativa_e_fonte(self):
        res = ferramentas.montar_prato("2026-11-09", "almoco", ["vegano"])
        self.assertTrue(res.sucesso)
        self.assertFalse(res.recusado)
        self.assertEqual(res.fontes[0]["doc_id"], "F09")
        prato = res.dados["prato"]
        self.assertTrue(prato)
        principal = next(item for item in prato if item["slot"] == "principal")
        self.assertEqual(principal["trilha"], "vegano")
        self.assertIn("Soja", principal["nome"])
        self.assertIn("justificativa", principal)
        self.assertNotIn("Carne", json.dumps(prato, ensure_ascii=False))
        self.assertIn("[1]", res.texto_base)

    def test_montar_prato_com_calorias_recusa_e_nao_estima(self):
        res = ferramentas.montar_prato("2026-11-09", "almoco", ["menos de 500 calorias"])
        self.assertFalse(res.sucesso)
        self.assertTrue(res.recusado)
        self.assertEqual(res.texto_base, geracao.RECUSA)
        self.assertEqual(res.dados["prato"], [])
        self.assertIn("nutricionais ou calóricos", res.motivo_recusa)

    def test_montar_prato_exclusao_alergeno_sem_anotacao_na_fonte_recusa(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            caminho_json = Path(tmp) / "cardapio_semanal.json"
            caminho_json.write_text(json.dumps({
                "unidade": "gama",
                "semana": {"inicio": "2030-05-06", "fim": "2030-05-12"},
                "refeicoes": [{
                    "unidade": "gama",
                    "data": "2030-05-06",
                    "refeicao": "almoco",
                    "compartimentos": [{
                        "slot": "principal",
                        "titulo": "Prato principal",
                        "max": 1,
                        "opcoes": [{
                            "id": "prato-x",
                            "nome": "Prato X",
                            "trilha": "padrao",
                            "alergenicos": [],
                            "fonte": {"doc_id": "F99", "pagina": 2, "chunk_id": "F99-0001"},
                        }],
                    }],
                    "mesa_apoio": [],
                    "alergenicos": {"disponivel": False, "legenda": [], "observacao": "sem anotações"},
                    "fonte": {"doc_id": "F99", "pagina": 2, "chunk_id": "F99-0001", "url": ""},
                    "avisos": [],
                }],
            }), encoding="utf-8")

            with mock.patch.object(ferramentas.config, "CARDAPIO_SEMANAL_JSON", caminho_json, create=True):
                res = ferramentas.montar_prato("2030-05-06", "almoco", ["sem lactose"])

        self.assertFalse(res.sucesso)
        self.assertTrue(res.recusado)
        self.assertEqual(res.texto_base, geracao.RECUSA)

    def test_montar_prato_exclusao_alergeno_com_cardapio_semanal_anotado(self, ):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            caminho_json = Path(tmp) / "cardapio_semanal.json"
            caminho_json.write_text(json.dumps({
                "unidade": "gama",
                "semana": {"inicio": "2026-11-16", "fim": "2026-11-22"},
                "refeicoes": [{
                    "unidade": "gama",
                    "data": "2026-11-16",
                    "refeicao": "almoco",
                    "compartimentos": [{
                        "slot": "principal",
                        "titulo": "Prato principal",
                        "max": 1,
                        "opcoes": [
                            {
                                "id": "frango-creme",
                                "nome": "Frango com creme de milho",
                                "trilha": "padrao",
                                "alergenicos": ["leite"],
                                "fonte": {"doc_id": "F37", "pagina": 2, "chunk_id": "F37-0002"},
                            },
                            {
                                "id": "tomate-quinoa",
                                "nome": "Tomate recheado com quinoa",
                                "trilha": "vegano",
                                "alergenicos": [],
                                "fonte": {"doc_id": "F37", "pagina": 2, "chunk_id": "F37-0002"},
                            },
                        ],
                    }],
                    "mesa_apoio": ["água"],
                    "alergenicos": {"disponivel": True, "legenda": [], "observacao": ""},
                    "fonte": {"doc_id": "F37", "pagina": 2, "chunk_id": "F37-0002", "url": "https://ru.unb.br/cardapio-gama/"},
                    "avisos": [],
                }],
            }), encoding="utf-8")

            with mock.patch.object(ferramentas.config, "CARDAPIO_SEMANAL_JSON", caminho_json, create=True):
                res = ferramentas.montar_prato("2026-11-16", "almoco", ["sem leite"])

        self.assertTrue(res.sucesso)
        self.assertEqual(res.dados["prato"][0]["nome"], "Tomate recheado com quinoa")

    def test_cardapio_do_dia_auto_fetch_quando_ausente_na_semana_atual(self):
        hoje = date.today()
        inicio = hoje - timedelta(days=hoje.weekday())
        fim = inicio + timedelta(days=6)
        dias_pt = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
        dia_nome = dias_pt[hoje.weekday()]
        texto_coleta = (
            f"[[PAGINA 2]]\n"
            f"## Almoço · {dia_nome} {hoje:%d/%m/%Y}\n"
            f"Cardápio do RU Gama (FCTE) — Almoço de {dia_nome}, {hoje:%d/%m/%Y}:\n"
            f"- Prato principal padrão: Frango assado\n"
            f"- Prato principal vegetariano estrito: Lentilha refogada\n"
            f"- Acompanhamentos: Arroz branco e integral Feijão carioca\n"
            f"- Salada: Alface\n"
        )
        resultado_fake = {
            "semana": scraper.Semana(inicio, fim, "https://ru.unb.br/wp-content/uploads/2026/11/semana.pdf", "semana"),
            "pagina": b"<html></html>",
            "pdf": b"%PDF-1.4",
            "texto": texto_coleta,
            "dias": [],
            "avisos": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            caminho_json = Path(tmp) / "cardapio_semanal.json"
            with (
                mock.patch.object(config, "CARDAPIO_SEMANAL_JSON", caminho_json),
                mock.patch.object(config, "CARDAPIO_AUTO_FETCH", True),
                mock.patch.object(scraper, "coletar", return_value=resultado_fake) as mock_coletar,
            ):
                res = ferramentas.montar_prato("hoje", "almoco", ["vegano"])

            self.assertTrue(res.sucesso)
            self.assertFalse(res.recusado)
            self.assertEqual(mock_coletar.call_count, 1)
            self.assertTrue(caminho_json.exists())
            principal = next(item for item in res.dados["prato"] if item["slot"] == "principal")
            self.assertIn("Lentilha refogada", principal["nome"])

    def test_cardapio_do_dia_recusa_honestamente_quando_unb_nao_publicou(self):
        hoje = date.today()
        sem_antiga = scraper.Semana(
            hoje - timedelta(days=14),
            hoje - timedelta(days=8),
            "https://ru.unb.br/antiga.pdf",
            "antiga",
        )
        with tempfile.TemporaryDirectory() as tmp:
            caminho_json = Path(tmp) / "cardapio_semanal.json"
            with (
                mock.patch.object(config, "CARDAPIO_SEMANAL_JSON", caminho_json),
                mock.patch.object(config, "CARDAPIO_AUTO_FETCH", True),
                mock.patch.object(scraper, "coletar", side_effect=scraper.SemanaNaoPublicada(hoje, sem_antiga)),
            ):
                res = ferramentas.montar_prato("hoje", "almoco", ["vegano"])

        self.assertFalse(res.sucesso)
        self.assertTrue(res.recusado)
        self.assertEqual(res.texto_base, geracao.RECUSA)
        self.assertIn("UnB ainda não publicou", res.motivo_recusa)
        self.assertIn(f"{sem_antiga.inicio:%d/%m/%Y}", res.motivo_recusa)

    def test_cardapio_do_dia_respeita_cooldown_sem_martelar_site(self):
        hoje = date.today()
        with tempfile.TemporaryDirectory() as tmp:
            caminho_json = Path(tmp) / "cardapio_semanal.json"
            with (
                mock.patch.object(config, "CARDAPIO_SEMANAL_JSON", caminho_json),
                mock.patch.object(config, "CARDAPIO_AUTO_FETCH", True),
                mock.patch.object(config, "CARDAPIO_COOLDOWN_SEGUNDOS", 3600),
                mock.patch.object(scraper, "coletar", side_effect=scraper.SemanaNaoPublicada(hoje, None)) as mock_coletar,
            ):
                res1 = ferramentas.cardapio_do_dia("hoje", "almoco")
                res2 = ferramentas.cardapio_do_dia("hoje", "almoco")

        self.assertEqual(mock_coletar.call_count, 1)
        self.assertTrue(res1.recusado)
        self.assertTrue(res2.recusado)
        self.assertEqual(res2.dados["sincronizacao"]["status"], "em_cooldown")
        self.assertIn("UnB ainda não publicou", res2.motivo_recusa)

    def test_cardapio_do_dia_data_historica_nao_dispara_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho_json = Path(tmp) / "cardapio_semanal.json"
            with (
                mock.patch.object(config, "CARDAPIO_SEMANAL_JSON", caminho_json),
                mock.patch.object(config, "CARDAPIO_AUTO_FETCH", True),
                mock.patch.object(scraper, "coletar") as mock_coletar,
            ):
                res = ferramentas.cardapio_do_dia("2020-01-01", "almoco")

        self.assertEqual(mock_coletar.call_count, 0)
        self.assertTrue(res.recusado)
        self.assertEqual(res.texto_base, geracao.RECUSA)


class TestGrafoEMinhaAgenda(unittest.TestCase):
    def test_grafo_fluxo_devolve_dado_estruturado_e_seta_tracejada(self):
        res = ferramentas.grafo_fluxo("Quais os pré-requisitos de Testes de Software?")
        self.assertTrue(res.sucesso)
        self.assertEqual(res.dados["tipo_consulta"], "prerequisitos")
        self.assertEqual(res.dados["confirmados"][0]["codigo"], "FGA0313")
        self.assertEqual(res.dados["incertos"][0]["codigo"], "FGA0312")
        self.assertEqual(res.fontes[0]["doc_id"], "F16")
        self.assertIn("confirme no SIGAA", res.texto_base)

    def test_grafo_fluxo_suporta_curso_vigencia_e_equivalencia(self):
        res_aero = ferramentas.grafo_fluxo(
            "Qual disciplina destrava mais matérias?",
            curso="aeroespacial",
        )
        self.assertTrue(res_aero.sucesso)
        self.assertEqual(res_aero.dados["curriculo_id"], "aeroespacial-2025")
        self.assertEqual(res_aero.fontes[0]["doc_id"], "F17")

        res_eq = ferramentas.grafo_fluxo("Qual a equivalência de FGA0308 em Eletrônica?")
        self.assertTrue(res_eq.sucesso)
        self.assertEqual(res_eq.dados["tipo_consulta"], "equivalencias")
        self.assertEqual(res_eq.dados["equivalencias"][0]["equivalentes"], ["FGA0096"])

        orq = agentes.Orquestrador()
        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res_orq = orq.executar(
                "Quais os pré-requisitos de Cálculo 2?",
                backend="extrativo",
                curso="aeroespacial",
            )
        self.assertEqual(res_orq["fontes_citadas"][0]["doc_id"], "F17")
        self.assertEqual(res_orq["dados_estruturados"][0]["dados"]["curriculo_id"], "aeroespacial-2025")

    def test_minha_agenda_com_perfil_e_sem_perfil(self):
        res_sem = ferramentas.minha_agenda("terça", perfil=None)
        self.assertFalse(res_sem.sucesso)
        self.assertTrue(res_sem.recusado)
        self.assertEqual(res_sem.texto_base, geracao.RECUSA)

        perfil = {
            "aulas": [
                {"dia": "terça-feira", "horario": "14:00", "codigo": "FGA0314", "disciplina": "Testes de Software", "sala": "I10"},
                {"dia": "terça-feira", "horario": "08:00", "codigo": "FGA0312", "disciplina": "MDS", "sala": "S1"},
                {"dia": "quarta-feira", "horario": "10:00", "codigo": "MAT0026", "disciplina": "Cálculo 2", "sala": "MOCAP"},
            ]
        }
        res_com = ferramentas.minha_agenda("terca", perfil=perfil)
        self.assertTrue(res_com.sucesso)
        self.assertEqual([a["codigo"] for a in res_com.dados["aulas"]], ["FGA0312", "FGA0314"])
        self.assertIn("Sala S1", res_com.texto_base)
        self.assertEqual(res_com.fontes[0]["doc_id"], "PERFIL")


class TestOrquestradorComFerramentas(unittest.TestCase):
    def test_orquestrador_montar_prato_vegano_registra_ferramenta_no_trace(self):
        orq = agentes.Orquestrador()
        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("monta um prato vegano pro almoço", backend="extrativo", data="2026-11-09")

        self.assertFalse(res["degradado"])
        self.assertIn("Soja refogada", res["resposta"])
        self.assertEqual(res["fontes_citadas"][0]["doc_id"], "F09")
        self.assertEqual(len(res["ferramentas_usadas"]), 1)
        chamada = res["ferramentas_usadas"][0]
        self.assertEqual(chamada["nome"], "montar_prato")
        self.assertEqual(chamada["argumentos"]["restricoes"], ["vegano"])
        self.assertEqual(chamada["argumentos"]["data"], "2026-11-09")
        self.assertFalse(chamada["recusado"])
        self.assertEqual(len(res["dados_estruturados"]), 1)

        etapa_par = next(p for p in res["trace"] if p["etapa"] == "execucao_paralela")
        self.assertEqual(etapa_par["execucoes"][0]["ferramenta"]["nome"], "montar_prato")
        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        self.assertTrue(etapa_val["resultados"][0]["aprovado"])

    def test_orquestrador_restricao_calorica_recusa_e_nao_alucina(self):
        orq = agentes.Orquestrador()
        with mock.patch.object(agentes.reescrita, "classificar_composta", return_value=(False, 0.05)):
            res = orq.executar("monta um prato com menos de 500 calorias", backend="extrativo", data="2026-11-09")

        self.assertEqual(res["resposta"], geracao.RECUSA)
        self.assertTrue(res["ferramentas_usadas"][0]["recusado"])
        etapa_val = next(p for p in res["trace"] if p["etapa"] == "validacao_factual")
        self.assertTrue(etapa_val["resultados"][0]["aprovado"])


if __name__ == "__main__":
    unittest.main()
