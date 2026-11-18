"""Lado do servidor da issue #66: tabela de preços por grupo e rotas de dados sem perfil."""
import json
import subprocess
import shutil
import sys
import unittest
from pathlib import Path

RAG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG))

from rumo_rag.coleta import precos  # noqa: E402


class TestTabelaDePrecos(unittest.TestCase):
    def setUp(self):
        self.tabela = precos.carregar()

    def test_grupo_ii_almoco_e_4_50_com_fonte(self):
        almoco = self.tabela["grupos"]["II"]["almoco"]
        self.assertEqual(almoco["valor"], 4.5)
        self.assertEqual(almoco["fonte"]["doc_id"], "F04")
        self.assertTrue(almoco["fonte"]["pagina"])

    def test_os_quatro_grupos_tem_as_tres_refeicoes(self):
        self.assertEqual(self.tabela["avisos"], [])
        for g in precos.GRUPOS:
            for r in precos.REFEICOES:
                with self.subTest(grupo=g, refeicao=r):
                    self.assertIn("valor", self.tabela["grupos"][g][r])

    def test_valores_conferem_com_o_texto_da_fonte(self):
        with open(RAG / "dados" / "chunks.jsonl", encoding="utf-8") as f:
            texto = "\n".join(c["texto"] for c in map(json.loads, f) if c["doc_id"] == "F04")
        for g, refs in self.tabela["grupos"].items():
            for r, item in refs.items():
                if item["valor"]:
                    with self.subTest(grupo=g, refeicao=r):
                        self.assertIn(f"R$ {item['valor']:.2f}".replace(".", ","), texto)

    def test_grupo_i_gratuito(self):
        self.assertEqual({r: v["valor"] for r, v in self.tabela["grupos"]["I"].items()},
                         {"cafe": 0.0, "almoco": 0.0, "jantar": 0.0})


try:
    from fastapi.testclient import TestClient
    from rumo_rag import api
except (ImportError, RuntimeError):  # sem fastapi/httpx: os testes de rota são pulados
    api = None


@unittest.skipIf(api is None, "fastapi/httpx não instalados")
class TestRotas(unittest.TestCase):
    def setUp(self):
        self.cliente = TestClient(api.app)

    def test_precos_e_publico_e_igual_para_todos(self):
        r = self.cliente.get("/precos")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["grupos"]["II"]["almoco"]["valor"], 4.5)

    def test_cardapio_estruturado(self):
        r = self.cliente.get("/cardapio", params={"data": "2026-11-09", "refeicao": "almoco"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["fonte"]["doc_id"], "F09")

    def test_cardapio_sem_base_recusa(self):
        r = self.cliente.get("/cardapio", params={"data": "2030-01-01", "refeicao": "almoco"})
        self.assertEqual(r.status_code, 404)
        self.assertIn("Não encontrei", r.json()["detail"])

    def test_pagina_de_demonstracao_e_modulo_sao_servidos(self):
        self.assertEqual(self.cliente.get("/web/rumo-perfil.js").status_code, 200)
        self.assertEqual(self.cliente.get("/web/demo-perfil.html").status_code, 200)


@unittest.skipIf(shutil.which("node") is None, "node não instalado")
class TestModuloDoNavegador(unittest.TestCase):
    def test_criterios_de_aceite_no_navegador(self):
        r = subprocess.run(["node", "--test", "web/rumo-perfil.test.mjs"], cwd=RAG, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
