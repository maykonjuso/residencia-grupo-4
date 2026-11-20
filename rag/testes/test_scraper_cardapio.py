"""Scraper do cardápio semanal do RU Gama — critérios de aceite da issue #50.

Os testes não acessam a internet: a página e o PDF vêm de testes/fixtures/cardapio_gama/,
que imitam a fonte real (estrutura da página, layout da tabela, datas "1º/9/2026").
"""
import io
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

RAG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG))

import yaml  # noqa: E402

from rumo_rag import api, chunking, config, extracao  # noqa: E402
from rumo_rag.coleta import scraper  # noqa: E402
from rumo_rag.coleta.__main__ import main  # noqa: E402

FIX = RAG / "testes" / "fixtures" / "cardapio_gama"
PAGINA = FIX / "pagina.html"
PDF = FIX / "Gama-Semana-02-31-8-a-6-9.pdf"


def rodar(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        codigo = main(list(args))
    return codigo, out.getvalue(), err.getvalue()


def sem_rede(*_a, **_k):
    raise urllib.error.URLError("[Errno 8] nodename nor servname provided")


class AmbienteIsolado(unittest.TestCase):
    """Redireciona catálogo, originais/ e brutos/ para uma pasta temporária."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.catalogo = self.tmp / "catalogo.yaml"
        self.catalogo.write_text(config.CATALOGO.read_text(encoding="utf-8"), encoding="utf-8")
        self.patches = [mock.patch.object(config, "CATALOGO", self.catalogo),
                        mock.patch.object(config, "ORIGINAIS", self.tmp / "originais"),
                        mock.patch.object(scraper, "BRUTOS", self.tmp / "brutos")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def arquivos(self):
        return sorted(str(p.relative_to(self.tmp)) for p in self.tmp.rglob("*") if p.is_file())


class TestDryRun(AmbienteIsolado):
    def _dry(self):
        def falso_baixar(url, timeout=scraper.TIMEOUT):
            self.urls.append(url)
            return PAGINA.read_bytes() if url == scraper.PAGINA else PDF.read_bytes()
        self.urls = []
        with mock.patch.object(scraper, "baixar", side_effect=falso_baixar):
            return rodar("cardapio", "--dry-run", "--semana", "2026-09-02")

    def test_imprime_os_dias_da_semana_com_as_refeicoes(self):
        codigo, out, err = self._dry()
        self.assertEqual(codigo, 0, err)
        for dia in ("segunda-feira 31/08/2026", "terça-feira 01/09/2026", "quarta-feira 02/09/2026",
                    "quinta-feira 03/09/2026", "sexta-feira 04/09/2026"):
            self.assertIn(dia, out)
        for refeicao in ("Café da manhã", "Almoço", "Jantar"):
            self.assertEqual(out.count(f"  {refeicao}\n"), 5, refeicao)
        self.assertIn("Prato principal padrão: Frango a pizzaiolo", out)
        self.assertIn("fonte: https://ru.unb.br/wp-content/uploads/2026/08/Gama-Semana-02-31-8-a-6-9.pdf", out)
        self.assertIn("alergenicos (legenda oficial):", out)
        self.assertIn("Leite e derivados", out)
        self.assertIn("Trigo/Glúten", out)
        self.assertIn("alergenicos (observacao):", out)

    def test_dry_run_nao_grava_nada(self):
        antes = self.catalogo.read_text(encoding="utf-8")
        self._dry()
        self.assertEqual(self.arquivos(), ["catalogo.yaml"])
        self.assertEqual(self.catalogo.read_text(encoding="utf-8"), antes)

    def test_educado_uma_requisicao_por_recurso_em_sequencia(self):
        self._dry()
        self.assertEqual(self.urls, [scraper.PAGINA,
                                     "https://ru.unb.br/wp-content/uploads/2026/08/Gama-Semana-02-31-8-a-6-9.pdf"])

    def test_user_agent_identifica_o_projeto(self):
        visto = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def urlopen(req, timeout):
            visto["ua"] = req.get_header("User-agent")
            visto["timeout"] = timeout
            return Resp(b"ok")
        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            scraper.baixar(scraper.PAGINA)
        self.assertIn("RUmo", visto["ua"])
        self.assertIn("residencia-grupo-4", visto["ua"])
        self.assertEqual(visto["timeout"], scraper.TIMEOUT)


class TestSemRede(AmbienteIsolado):
    def test_sem_rede_falha_com_mensagem_clara_e_nao_grava(self):
        with mock.patch("urllib.request.urlopen", side_effect=sem_rede):
            codigo, out, err = rodar("cardapio")          # modo que grava
        self.assertEqual(codigo, 3)
        self.assertIn("não consegui acessar https://ru.unb.br/cardapio-gama/", err)
        self.assertIn("Nada foi gravado", err)
        self.assertEqual(out, "")
        self.assertEqual(self.arquivos(), ["catalogo.yaml"])

    def test_rede_cai_no_meio_pagina_ok_pdf_falha_nao_grava(self):
        respostas = iter([PAGINA.read_bytes()])

        def baixar(url, timeout=scraper.TIMEOUT):
            try:
                return next(respostas)
            except StopIteration:
                raise scraper.ErroColeta(f"não consegui acessar {url} (timed out). Sem conexão com a internet?")
        with mock.patch.object(scraper, "baixar", side_effect=baixar):
            codigo, _, err = rodar("cardapio", "--semana", "2026-09-02")
        self.assertEqual(codigo, 3)
        self.assertEqual(self.arquivos(), ["catalogo.yaml"])  # nem o HTML bruto fica pela metade

    def test_resposta_que_nao_e_pdf_nao_grava(self):
        with mock.patch.object(scraper, "baixar", side_effect=[PAGINA.read_bytes(), b"<html>imagem</html>"]):
            codigo, _, err = rodar("cardapio", "--semana", "2026-09-02")
        self.assertEqual(codigo, 3)
        self.assertIn("não devolveu um PDF", err)
        self.assertEqual(self.arquivos(), ["catalogo.yaml"])


# o coletor usa o próximo número livre do catálogo; calculado aqui para o teste não depender de
# quantas fontes a base tem hoje
PROXIMO = f"F{max(int(d['id'][1:]) for d in extracao.carregar_catalogo()) + 1:02d}"


class TestGravacao(AmbienteIsolado):
    def _coletar(self):
        with mock.patch.object(scraper, "baixar", side_effect=[PAGINA.read_bytes(), PDF.read_bytes()]):
            return rodar("cardapio", "--semana", "2026-09-02")

    def test_grava_html_bruto_pdf_e_registra_no_catalogo(self):
        codigo, _, err = self._coletar()
        self.assertEqual(codigo, 0, err)
        arquivos = self.arquivos()
        self.assertTrue(any(a.startswith("brutos/") and a.endswith(".html") for a in arquivos), arquivos)
        self.assertIn(f"originais/{PROXIMO}.pdf", arquivos)
        docs = yaml.safe_load(self.catalogo.read_text(encoding="utf-8"))["documentos"]
        novo = docs[-1]
        self.assertEqual(novo["id"], PROXIMO)
        self.assertEqual(novo["tipo"], "cardapio")
        self.assertEqual(novo["orgao"], "UnB · Diretoria do RU")
        self.assertEqual(novo["data"], "2026-08-31")
        self.assertEqual(novo["url"], "https://ru.unb.br/wp-content/uploads/2026/08/Gama-Semana-02-31-8-a-6-9.pdf")
        self.assertFalse(any(p.name.endswith(".tmp") for p in self.tmp.rglob("*")))

    def test_rodar_de_novo_nao_duplica_a_semana(self):
        self._coletar()
        codigo, _, err = self._coletar()
        self.assertEqual(codigo, 0, err)
        self.assertIn(f"já estava no catálogo como {PROXIMO}", err)
        docs = yaml.safe_load(self.catalogo.read_text(encoding="utf-8"))["documentos"]
        self.assertEqual(sum(1 for d in docs if d["id"] == PROXIMO), 1)

    def test_comentarios_do_catalogo_sao_preservados(self):
        self._coletar()
        self.assertTrue(self.catalogo.read_text(encoding="utf-8").startswith("# Catálogo da base de conhecimento"))


class TestFonteNoCatalogo(unittest.TestCase):
    def test_pagina_registrada_com_orgao_url_e_data(self):
        cat = yaml.safe_load(config.CATALOGO.read_text(encoding="utf-8"))
        fonte = next(f for f in cat["fontes_de_coleta"] if f["id"] == "cardapio-gama")
        self.assertEqual(fonte["url"], scraper.PAGINA)
        self.assertEqual(fonte["orgao"], scraper.ORGAO)
        self.assertRegex(str(fonte["data"]), r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(len(extracao.carregar_catalogo()), len(cat["documentos"]))  # não vira documento


class TestPagina(unittest.TestCase):
    def setUp(self):
        self.semanas, self.avisos = scraper.listar_semanas(PAGINA.read_text(encoding="utf-8"))

    def test_datas_vem_do_texto_do_link_ou_do_nome_do_arquivo(self):
        self.assertEqual([(s.inicio, s.fim) for s in self.semanas],
                         [(date(2026, 8, 24), date(2026, 8, 30)), (date(2026, 8, 31), date(2026, 9, 6)),
                          (date(2026, 9, 7), date(2026, 9, 13))])
        self.assertTrue(self.semanas[2].url.startswith("https://ru.unb.br/wp-content/"))  # href relativo resolvido

    def test_link_sem_data_vira_aviso(self):
        self.assertEqual(len(self.avisos), 1)
        self.assertIn("Aviso de funcionamento", self.avisos[0])

    def test_escolhe_a_semana_da_data_ou_a_mais_recente(self):
        self.assertEqual(scraper.escolher_semana(self.semanas, date(2026, 9, 2))[0].inicio, date(2026, 8, 31))
        semana, aviso = scraper.escolher_semana(self.semanas, date(2026, 12, 1))
        self.assertEqual(semana.inicio, date(2026, 9, 7))
        self.assertIn("mais recente", aviso)

    def test_pagina_sem_links_falha_com_mensagem(self):
        with self.assertRaises(scraper.ErroColeta) as e:
            scraper.escolher_semana(scraper.listar_semanas("<html><p>em manutenção</p></html>")[0], date.today())
        self.assertIn("layout pode ter mudado", str(e.exception))

    def test_semana_que_atravessa_o_ano(self):
        s, _ = scraper.listar_semanas('<a href="/wp-content/uploads/2026/12/Gama-Semana-05-28-12-a-3-1.pdf">x</a>')
        self.assertEqual((s[0].inicio, s[0].fim), (date(2026, 12, 28), date(2027, 1, 3)))


class TestNormalizacao(unittest.TestCase):
    def test_datas_sem_zero_e_com_ordinal(self):
        self.assertEqual([extracao.data_cardapio(t) for t in ("31/8/2026", "1º/9/2026", "09/11/2026", "2ª FEIRA")],
                         ["31/08/2026", "01/09/2026", "09/11/2026", ""])

    def test_formato_que_o_chunking_e_a_api_esperam(self):
        texto, _ = scraper.ler_pdf(PDF.read_bytes(), scraper.listar_semanas(PAGINA.read_text())[0][1])
        doc = {"id": "F99", "titulo": "Cardápio", "orgao": "RU", "eixo": "ru", "tipo": "cardapio",
               "url": "u", "data": "2026-08-31", "arquivo": "x"}
        chunks = chunking.dividir(doc, texto)
        self.assertEqual(len(chunks), 15)                    # 3 refeições × 5 dias
        self.assertIn("Almoço · terça-feira 01/09/2026", [c["secao"] for c in chunks])
        pergunta = api.com_data("almoço de hoje", api.Contexto(data=date(2026, 9, 1)))
        self.assertIn("01/09/2026", pergunta)
        self.assertTrue(any("01/09/2026" in c["secao"] for c in chunks))

    def test_secao_sem_data_recebe_a_data_pelo_dia_da_semana(self):
        texto, avisos = scraper.completar_datas(
            "## Almoço · quarta-feira\nCardápio do RU Gama (FCTE) — Almoço de quarta-feira, :\n- Sopa: X",
            date(2026, 8, 31))
        self.assertIn("## Almoço · quarta-feira 02/09/2026", texto)
        self.assertIn("Almoço de quarta-feira, 02/09/2026:", texto)
        self.assertTrue(avisos)


if __name__ == "__main__":
    unittest.main()
