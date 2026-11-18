"""Teste de regressão da recuperação de preços do RU no modo BM25 (Issue #51)."""
import sys
import unittest
from pathlib import Path

RAG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG))

from rumo_rag import indice  # noqa: E402


class TestBm25Precos(unittest.TestCase):
    def test_tokenizar_normaliza_sinonimos_de_preco(self):
        self.assertIn("valor", indice.tokenizar("qual o preço e quanto custa?"))
        self.assertIn("valor", indice.tokenizar("valores atuais"))
        self.assertIn("refeição", indice.tokenizar("Valores das refeições"))
        self.assertIn("estudante", indice.tokenizar("estudantes de graduação"))

    def test_bm25_recupera_grupo_ii_para_preco_graduacao(self):
        trechos = indice.buscar(
            "qual o preço da refeição no RU para estudantes de graduação?",
            modo="bm25",
            decompor_pergunta=False,
        )
        ids = [t["chunk_id"] for t in trechos]
        self.assertIn("F04-0002", ids)


if __name__ == "__main__":
    unittest.main()
