"""Coleta no SIGAA público: oferta de turmas (#56) e pré-requisitos (#52).

Os testes não acessam a internet. As páginas vêm de testes/fixtures/sigaa/, cópias da
consulta pública de 26/11/2026 (a de turmas reduzida a oito disciplinas e sem o nome dos
docentes, que o RUmo não guarda).
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

RAG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG))

from rumo_rag import config  # noqa: E402
from rumo_rag.coleta import sigaa  # noqa: E402
from rumo_rag.coleta.__main__ import main  # noqa: E402

FIX = RAG / "testes" / "fixtures" / "sigaa"
TURMAS_HTML = (FIX / "turmas_fcte_2026-2.html").read_text(encoding="utf-8")
FICHA_HTML = (FIX / "ficha_FGA0314.html").read_text(encoding="utf-8")


def rodar(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        codigo = main(list(args))
    return codigo, out.getvalue(), err.getvalue()


def sem_rede(*_a, **_k):
    raise AssertionError("o teste tentou acessar o SIGAA")


def software():
    grafo = json.loads((config.DADOS / "grafo_curricular.json").read_text(encoding="utf-8"))
    return next(c for c in grafo["curriculos"] if c["curriculo_id"] == "software-2024-2")


class TestTurmas(unittest.TestCase):
    def setUp(self):
        self.turmas = sigaa.ler_turmas(TURMAS_HTML)
        self.testes = [t for t in self.turmas if t["codigo"] == "FGA0314"]

    def test_le_disciplina_turma_horario_e_local(self):
        self.assertEqual([t["turma"] for t in self.testes], ["01", "02"])
        t1 = self.testes[0]
        self.assertEqual(t1["nome"], "Testes de Software")
        self.assertEqual(t1["ano_periodo"], "2026.2")
        self.assertEqual(t1["horario_sigaa"], "35M12")
        self.assertEqual(t1["aulas"], [{"dia": "terça", "inicio": "08:00", "fim": "09:50"},
                                       {"dia": "quinta", "inicio": "08:00", "fim": "09:50"}])
        self.assertEqual(t1["local"], "FCTE - I10")
        self.assertEqual(t1["salas"], ["I10"])

    def test_nao_guarda_docente_nem_vagas(self):
        for t in self.turmas:
            self.assertNotIn("docente", t)
            self.assertNotIn("vagas", json.dumps(t))
            self.assertNotIn("DOCENTE", json.dumps(t))

    def test_periodo_letivo_quando_publicado(self):
        com_periodo = [t for t in self.turmas if t["periodo_letivo"]]
        self.assertTrue(com_periodo)
        self.assertEqual(com_periodo[0]["periodo_letivo"], {"inicio": "2026-08-10", "fim": "2026-12-14"})

    def test_salas_de_local_em_texto_livre(self):
        casos = {
            "FCTE - I10": ["I10"],
            "FCTE - S2/I9": ["S2", "I9"],
            "FCTE / S8 / I3 / LAB TERMOFLUIDOS": ["S8", "I3", "LAB TERMOFLUIDOS"],
            "NIT/LDS(segunda)/I1(sexta)": ["NIT", "LDS", "I1"],
            "FCTE - Salas S4 /S4 / S10 / S10 (120 Vagas)": ["S4", "S10"],
            "FCTE - I7/I4/I4": ["I7", "I4"],
        }
        for local, esperado in casos.items():
            self.assertEqual(sigaa._salas(local), esperado, local)

    def test_nome_em_caixa_normal(self):
        self.assertEqual(sigaa.titulo("PROJETO EXTENSIONISTA EM ENGENHARIA ELETRÔNICA 2"),
                         "Projeto Extensionista em Engenharia Eletrônica 2")
        self.assertEqual(sigaa.titulo("CÁLCULO II"), "Cálculo II")

    def test_oferta_valida_pelo_schema(self):
        oferta = sigaa.montar_oferta(self.turmas, 2026, 2, "2026-11-26")
        sigaa.validar_oferta(oferta)
        oferta["turmas"][0]["aulas"][0]["dia"] = "terca"
        with self.assertRaises(Exception):
            sigaa.validar_oferta(oferta)

    def test_texto_curado_responde_que_horas_e_onde(self):
        md = sigaa.gerar_markdown(sigaa.montar_oferta(self.turmas, 2026, 2, "2026-11-26"))
        self.assertIn("FGA0314 Testes de Software — horário das aulas e sala em 2026.2: "
                      "turma 01: terça e quinta, das 08:00 às 09:50, sala I10; "
                      "turma 02: terça e quinta, das 10:00 às 11:50, sala I6. (Horário no SIGAA: 35M12, 35M34.)", md)
        self.assertIn("Coletado em 2026-11-26", md)
        self.assertIn("https://sigaa.unb.br/sigaa/public/turmas/listar.jsf", md)

    def test_texto_curado_nao_repete_fcte_em_cada_linha(self):
        # Q24 ("Quantas vagas a FCTE oferta...") caía para fora do top-5 quando cada linha
        # repetia "FCTE" e o título dizia "Oferta de turmas da FCTE".
        md = sigaa.gerar_markdown(sigaa.montar_oferta(self.turmas, 2026, 2, "2026-11-26"))
        corpo = md.split("## ", 1)[1]
        self.assertNotIn("FCTE -", corpo)
        self.assertNotIn("Oferta", md.splitlines()[0])

    def test_gravar_registra_no_catalogo_uma_vez(self):
        with tempfile.TemporaryDirectory() as tmp:
            dados = Path(tmp)
            catalogo = dados / "catalogo.yaml"
            catalogo.write_text("documentos:\n  - id: F58\n    arquivo: originais/F58.pdf\n", encoding="utf-8")
            oferta = sigaa.montar_oferta(self.turmas, 2026, 2, "2026-11-26")
            with mock.patch.object(config, "DADOS", dados), mock.patch.object(config, "CATALOGO", catalogo), \
                    mock.patch.object(sigaa, "TURMAS", dados / "turmas"), \
                    mock.patch.object(sigaa, "BRUTOS", dados / "brutos"):
                g1 = sigaa.gravar_oferta(oferta, TURMAS_HTML)
                g2 = sigaa.gravar_oferta(oferta, None)
            self.assertEqual((g1["doc_id"], g1["novo"]), ("F59", True))
            self.assertEqual((g2["doc_id"], g2["novo"]), ("F59", False))
            self.assertEqual(g2["avisos"], [])
            texto = catalogo.read_text(encoding="utf-8")
            self.assertEqual(texto.count("id: F59"), 1)
            self.assertIn("arquivo: curados/oferta_turmas_fcte_2026-2.md", texto)
            self.assertIn('coletado_em: "2026-11-26"', texto)
            self.assertTrue((dados / "turmas" / "fcte_2026-2.json").exists())
            self.assertTrue((dados / "curados" / "oferta_turmas_fcte_2026-2.md").exists())

    def test_avisa_quando_fica_oferta_de_outro_semestre(self):
        with tempfile.TemporaryDirectory() as tmp:
            dados = Path(tmp)
            catalogo = dados / "catalogo.yaml"
            catalogo.write_text("documentos:\n  - id: F59\n    arquivo: curados/oferta_turmas_fcte_2026-2.md\n",
                                encoding="utf-8")
            oferta = sigaa.montar_oferta(self.turmas, 2027, 1, "2027-03-01")
            oferta["ano_periodo"] = "2027.1"
            with mock.patch.object(config, "DADOS", dados), mock.patch.object(config, "CATALOGO", catalogo), \
                    mock.patch.object(sigaa, "TURMAS", dados / "turmas"):
                g = sigaa.gravar_oferta(oferta, None)
        self.assertEqual(g["doc_id"], "F60")
        self.assertEqual(len(g["avisos"]), 1)
        self.assertIn("oferta_turmas_fcte_2026-2.md", g["avisos"][0])

    def test_cli_pagina_local_sem_rede(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(TURMAS_HTML)
        with mock.patch.object(sigaa.Sessao, "pedir", sem_rede):
            codigo, out, err = rodar("turmas", "--ano", "2026", "--periodo", "2",
                                     "--pagina-local", f.name, "--dry-run")
        Path(f.name).unlink()
        self.assertEqual(codigo, 0, err)
        self.assertIn("turmas de 8 disciplinas em 2026.2", out)
        self.assertIn("nada foi gravado", err)


class TestComponente(unittest.TestCase):
    def setUp(self):
        self.ficha = sigaa.ler_componente(FICHA_HTML)

    def test_le_requisitos_da_ficha(self):
        f = self.ficha
        self.assertEqual(f["codigo"], "FGA0314")
        self.assertEqual(f["nome"], "Testes de Software")
        self.assertEqual(f["pre_requisitos"]["expressao"], "( FGA0138 OU FGA0313 )")
        self.assertEqual(f["pre_requisitos"]["cnf"], [["FGA0138", "FGA0313"]])
        self.assertEqual(f["co_requisitos"], {"expressao": None, "cnf": []})
        self.assertEqual(f["equivalente_de"], ["FGA0238"])
        self.assertEqual(f["pre_requisito_de"], ["FGA0317", "FGA0321"])

    def test_historico_e_curriculos(self):
        hist = self.ficha["historico_pre_requisitos"]
        self.assertEqual(hist[0], {"expressao": "( FGA0138 OU FGA0313 )", "status": "ATIVO",
                                   "inicio": "22/09/2024", "fim": None})
        self.assertEqual(len(hist), 3)
        self.assertEqual(self.ficha["curriculos"][0]["curriculo"], "6360/2")
        self.assertTrue(self.ficha["curriculos"][0]["obrigatoria"])


class TestExpressao(unittest.TestCase):
    def test_formas(self):
        self.assertEqual(sigaa.cnf(None), [])
        self.assertEqual(sigaa.cnf("-"), [])
        self.assertEqual(sigaa.cnf("( MAT0025 )"), [["MAT0025"]])
        self.assertEqual(sigaa.cnf("( MAT0025 E IFD0171 )"), [["IFD0171"], ["MAT0025"]])
        self.assertEqual(sigaa.cnf("( FGA0138 OU FGA0313 )"), [["FGA0138", "FGA0313"]])
        self.assertEqual(sigaa.cnf("( ( MAT0025 E IFD0171 ) OU FGA0163 )"),
                         [["FGA0163", "IFD0171"], ["FGA0163", "MAT0025"]])
        self.assertEqual(sigaa.cnf("( FCTE0005 OU FGA0003 )"), [["FCTE0005", "FGA0003"]])

    def test_expressao_quebrada(self):
        with self.assertRaises(ValueError):
            sigaa.cnf("( MAT0025 E ")
        with self.assertRaises(ValueError):
            sigaa.cnf("( MAT0025 ) MAT0026")


class TestComparacao(unittest.TestCase):
    def setUp(self):
        self.curriculo = software()
        self.ficha = sigaa.ler_componente(FICHA_HTML)

    def linha(self, componentes, codigo="FGA0314", relacao="pre_requisito"):
        linhas = sigaa.comparar(self.curriculo, componentes)
        return next(l for l in linhas if l["codigo"] == codigo and l["relacao"] == relacao)

    def test_codigo_antigo_vira_vigente_e_bate_com_o_gabarito(self):
        l = self.linha([self.ficha])
        self.assertEqual(l["situacao"], "igual")
        self.assertEqual(l["sigaa"], [["FGA0312", "FGA0313"]])
        self.assertEqual(l["grafo"], [["FGA0312", "FGA0313"]])

    def test_divergencia_aparece(self):
        ficha = json.loads(json.dumps(self.ficha))
        ficha["pre_requisitos"] = {"expressao": "( FGA0313 )", "cnf": [["FGA0313"]]}
        l = self.linha([ficha])
        self.assertEqual(l["situacao"], "diverge")
        self.assertEqual(l["sigaa"], [["FGA0313"]])

    def test_disciplina_sem_ficha(self):
        self.assertEqual(self.linha([], "MAT0026")["situacao"], "sem_ficha")

    def test_cli_recompara_relatorio_sem_rede(self):
        relatorio = sigaa.montar_relatorio_componentes(self.curriculo, [self.ficha], "2026-11-26", [])
        self.assertEqual(relatorio["resumo"]["fichas"], 1)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False)
        with mock.patch.object(sigaa.Sessao, "pedir", sem_rede):
            codigo, out, _ = rodar("prerequisitos", "--local", f.name)
        Path(f.name).unlink()
        self.assertEqual(codigo, 0)
        self.assertIn("software-2024-2: 1 fichas de 47 disciplinas", out)


if __name__ == "__main__":
    unittest.main()
