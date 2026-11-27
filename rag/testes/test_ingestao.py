"""Testes unitários para o pipeline de ingestão (#53) e salvaguardas de avaliação."""
import argparse
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_RAG = Path(__file__).resolve().parents[1]
if str(_RAG) not in sys.path:
    sys.path.insert(0, str(_RAG))

from rumo_rag import __main__ as cli  # noqa: E402
from rumo_rag import config, extracao, indice  # noqa: E402


class TestIngestaoCardapioETexto(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.dados = self.tmp / "dados"
        self.originais = self.dados / "originais"
        self.texto = self.dados / "texto"
        self.curados = self.dados / "curados"
        self.originais.mkdir(parents=True)
        self.texto.mkdir(parents=True)
        self.curados.mkdir(parents=True)
        self.chunks_path = self.dados / "chunks.jsonl"

        (self.texto / "F04.txt").write_text(
            "## Valores das refeições\nEstudantes do Grupo II pagam R$ 4,50 no almoço.",
            encoding="utf-8",
        )
        (self.curados / "F16_fluxograma.md").write_text(
            "# Fluxograma\nTestes de Software tem pré-requisito Requisitos de Software.",
            encoding="utf-8",
        )
        # Simula PDF semanal em originais/ que NÃO deve entrar na base textual/vetorial
        (self.originais / "F56.pdf").write_bytes(b"%PDF-fake")

        self.catalogo = [
            {
                "id": "F04",
                "titulo": "Valores das refeições",
                "orgao": "UnB · Diretoria do RU",
                "eixo": "ru",
                "tipo": "pagina",
                "data": "2026",
                "url": "https://ru.unb.br/precos-e-grupos/",
                "arquivo": "originais/F04.html",
            },
            {
                "id": "F16",
                "titulo": "Fluxograma de Software",
                "orgao": "UnB · FCTE",
                "eixo": "fluxo",
                "curso": "software",
                "tipo": "matriz",
                "data": "2026-02",
                "url": "https://software.unb.br/fluxograma",
                "arquivo": "curados/F16_fluxograma.md",
            },
            {
                "id": "F56",
                "titulo": "Cardápio semanal do RU Gama",
                "orgao": "UnB · Diretoria do RU",
                "eixo": "ru",
                "tipo": "cardapio",
                "data": "2026-11-16",
                "url": "https://ru.unb.br/cardapio.pdf",
                "arquivo": "originais/F56.pdf",
            },
        ]

    def tearDown(self):
        self._tmp.cleanup()

    def test_ingerir_ignora_cardapio_e_reutiliza_texto_sem_originais(self):
        buf = io.StringIO()
        with mock.patch.object(config, "DADOS", self.dados), \
             mock.patch.object(config, "ORIGINAIS", self.originais), \
             mock.patch.object(config, "TEXTO", self.texto), \
             mock.patch.object(config, "CHUNKS", self.chunks_path), \
             mock.patch.object(extracao, "carregar_catalogo", return_value=self.catalogo), \
             mock.patch.object(extracao.urllib.request, "urlopen") as m_url, \
             mock.patch.object(extracao, "_ler_cardapio", side_effect=AssertionError("não deve ler cardápio na ingestão")), \
             redirect_stdout(buf):
            cli.ingerir(argparse.Namespace(rebaixar=False, somente_chunks=True))

        m_url.assert_not_called()
        saida = buf.getvalue()
        self.assertIn("ignorando 1 cardápio(s) (F56)", saida)
        self.assertFalse((self.texto / "F56.txt").exists())
        self.assertTrue((self.texto / "F16.txt").exists())
        self.assertTrue(self.chunks_path.exists())

        chunks = [json.loads(l) for l in self.chunks_path.read_text(encoding="utf-8").splitlines()]
        doc_ids = {c["doc_id"] for c in chunks}
        self.assertEqual(doc_ids, {"F04", "F16"})
        self.assertFalse(any(c["tipo"] == "cardapio" for c in chunks))

    def test_baixar_com_rebaixar_true_forca_download(self):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"<html>novo</html>"

        with mock.patch.object(config, "DADOS", self.dados), \
             mock.patch.object(config, "ORIGINAIS", self.originais), \
             mock.patch.object(config, "TEXTO", self.texto), \
             mock.patch.object(extracao.urllib.request, "urlopen", return_value=_Resp()) as m_url:
            extracao.baixar([self.catalogo[0]], rebaixar=False)
            m_url.assert_not_called()
            extracao.baixar([self.catalogo[0]], rebaixar=True)
            m_url.assert_called_once()
            self.assertEqual((self.originais / "F04.html").read_bytes(), b"<html>novo</html>")


class TestIndiceEAvaliarSeguros(unittest.TestCase):
    def test_indexar_preserva_chunks_quando_dependencias_vetoriais_faltam(self):
        with tempfile.TemporaryDirectory() as tmp:
            chunks_path = Path(tmp) / "chunks.jsonl"
            conteudo_original = '{"chunk_id": "F01-0000"}\n'
            chunks_path.write_text(conteudo_original, encoding="utf-8")

            with mock.patch.object(config, "CHUNKS", chunks_path), \
                 mock.patch.dict(sys.modules, {"sentence_transformers": None, "chromadb": None}), \
                 mock.patch.object(importlib.util, "find_spec", return_value=None):
                with self.assertRaises(ImportError):
                    indice.indexar([{"chunk_id": "NOVO-0000", "texto": "x", "texto_indexado": "x"}])

            self.assertEqual(chunks_path.read_text(encoding="utf-8"), conteudo_original)

    def test_avaliar_sem_chroma_preserva_denso_e_hibrido_e_desativa_decomposicao(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            perg_dir = tmp_path / "perguntas"
            res_dir = tmp_path / "resultados"
            perg_dir.mkdir()
            res_dir.mkdir()
            (perg_dir / "perguntas_ouro.jsonl").write_text(
                json.dumps({"id": "Q01", "eixo": "ru", "pergunta": "Qual o preço?", "docs_esperados": ["F04"]}) + "\n",
                encoding="utf-8",
            )
            resultado_path = res_dir / "resultado_recuperacao.json"
            resultado_path.write_text(
                json.dumps([
                    {"modo": "bm25", "n": 32, "hit@1": 0.5, "hit@5": 0.5, "mrr": 0.5, "detalhes": []},
                    {"modo": "denso", "n": 32, "hit@1": 0.969, "hit@5": 1.0, "mrr": 0.984, "detalhes": []},
                    {"modo": "hibrido", "n": 32, "hit@1": 0.938, "hit@5": 1.0, "mrr": 0.969, "detalhes": []},
                ]),
                encoding="utf-8",
            )

            chamadas = []

            def fake_buscar(pergunta, k=5, modo="hibrido", decompor_pergunta=True, **_kw):
                chamadas.append((modo, decompor_pergunta))
                return [{"doc_id": "F04"}]

            with mock.patch.object(config, "CHROMA", tmp_path / "chroma_ausente"), \
                 mock.patch.object(config, "PERGUNTAS_AVALIACAO", perg_dir), \
                 mock.patch.object(config, "RESULTADOS_AVALIACAO", res_dir), \
                 mock.patch.object(indice, "buscar", side_effect=fake_buscar), \
                 redirect_stdout(io.StringIO()):
                cli.avaliar(argparse.Namespace(k=5, modo=None))

            self.assertEqual(chamadas, [("bm25", False)])
            salvo = json.loads(resultado_path.read_text(encoding="utf-8"))
            self.assertEqual([x["modo"] for x in salvo], ["bm25", "denso", "hibrido"])
            self.assertEqual(salvo[0]["n"], 1)
            self.assertEqual(salvo[0]["hit@1"], 1.0)
            self.assertEqual(salvo[1]["hit@1"], 0.969)
            self.assertEqual(salvo[2]["hit@1"], 0.938)


if __name__ == "__main__":
    unittest.main()
