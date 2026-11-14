"""Testes das regras de negócio do RUmo (docs/entrega-1/regras-de-negocio.md).

Cada classe testa uma regra. Nenhum teste carrega LLM nem modelo de embedding: rodam em
segundos, sem GPU e sem internet, para poderem entrar no Definition of Done.

    pytest rag/testes/test_rn.py -v
"""
import inspect
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

RAG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG))

import yaml  # noqa: E402

from rumo_rag import config, geracao  # noqa: E402

with open(config.CATALOGO, encoding="utf-8") as f:
    CATALOGO = yaml.safe_load(f)
DOCS = {d["id"]: d for d in CATALOGO["documentos"]}

# Domínios aceitos como fonte oficial (RN-01): a UnB e órgãos do governo federal.
DOMINIOS_OFICIAIS = ("unb.br", "gov.br")

TRECHOS = [
    {"doc_id": "F04", "titulo": "Valores das refeições e grupos de acesso", "orgao": "UnB · Diretoria do RU",
     "pagina": 1, "secao": "", "url": "https://ru.unb.br/precos-e-grupos/", "chunk_id": "F04-0000",
     "texto": "Estudantes do grupo II pagam R$ 5,20 no almoço."},
    {"doc_id": "F03", "titulo": "Unidades do RU e horários de funcionamento", "orgao": "UnB · Diretoria do RU",
     "pagina": 1, "secao": "RU Gama", "url": "https://ru.unb.br/unidades/", "chunk_id": "F03-0002",
     "texto": "O RU Gama serve almoço das 11h às 14h."},
]


def _tem_indice() -> bool:
    try:
        import chromadb  # noqa: F401
        import rank_bm25  # noqa: F401
        return True
    except ImportError:
        return False


class RN01FonteOficial(unittest.TestCase):
    """RN-01 · Só fonte oficial pública, com URL e data de coleta."""

    def test_todo_documento_tem_id_orgao_e_url(self):
        for id_, d in DOCS.items():
            with self.subTest(doc=id_):
                self.assertRegex(id_, r"^F\d{2}$")
                self.assertTrue(d.get("orgao"), "documento sem órgão emissor")
                self.assertRegex(d["url"], r"^https?://", "documento sem URL")

    def test_todo_documento_vem_de_dominio_oficial(self):
        for id_, d in DOCS.items():
            host = urlparse(d["url"]).hostname or ""
            with self.subTest(doc=id_, host=host):
                self.assertTrue(any(host == dom or host.endswith("." + dom) for dom in DOMINIOS_OFICIAIS),
                                f"{host} não é domínio oficial")

    def test_catalogo_tem_data_de_coleta(self):
        self.assertRegex(str(CATALOGO.get("coleta", "")), r"^\d{4}-\d{2}-\d{2}$")

    def test_todo_chunk_carrega_a_url_do_catalogo(self):
        if not config.CHUNKS.exists():
            self.skipTest("chunks.jsonl ainda não gerado")
        with open(config.CHUNKS, encoding="utf-8") as f:
            for linha in f:
                c = json.loads(linha)
                self.assertIn(c["doc_id"], DOCS, f"{c['chunk_id']} aponta para documento fora do catálogo")
                self.assertEqual(c["url"], DOCS[c["doc_id"]]["url"], c["chunk_id"])


class RN02CitaFonte(unittest.TestCase):
    """RN-02 · Toda afirmação cita documento, página e URL."""

    def test_prompt_exige_citacao_por_afirmacao(self):
        self.assertIn("Depois de cada afirmação, cite o trecho", geracao.INSTRUCOES)
        self.assertIn("SOMENTE as informações dos trechos", geracao.INSTRUCOES)

    def test_contexto_numera_trechos_com_documento_e_pagina(self):
        ctx = geracao.montar_contexto(TRECHOS)
        self.assertIn("[1] Fonte F04", ctx)
        self.assertIn("[2] Fonte F03", ctx)
        self.assertIn("p. 1", ctx)

    def test_citacao_vira_documento_pagina_e_url(self):
        fontes = geracao.citacoes_usadas("Custa R$ 5,20 [1].", TRECHOS)
        self.assertEqual(len(fontes), 1)
        self.assertEqual(fontes[0]["doc_id"], "F04")
        self.assertEqual(fontes[0]["pagina"], 1)
        self.assertEqual(fontes[0]["url"], "https://ru.unb.br/precos-e-grupos/")

    def test_citacao_para_trecho_inexistente_e_ignorada(self):
        self.assertEqual(geracao.citacoes_usadas("Algo [7].", TRECHOS), [])

    def test_resposta_sem_citacao_e_acusada(self):
        self.assertTrue(geracao.resposta_sem_citacao("O almoço custa R$ 5,20.", TRECHOS))
        self.assertTrue(geracao.resposta_sem_citacao("O almoço custa R$ 5,20 [9].", TRECHOS))
        self.assertFalse(geracao.resposta_sem_citacao("O almoço custa R$ 5,20 [1].", TRECHOS))

    def test_recusa_nao_conta_como_falta_de_citacao(self):
        self.assertFalse(geracao.resposta_sem_citacao(geracao.RECUSA, TRECHOS))


class RN03RecusaForaDaBase(unittest.TestCase):
    """RN-03 · Fora da base, o RUmo recusa com a frase padrão."""

    def test_frase_de_recusa_e_a_combinada(self):
        self.assertEqual(geracao.RECUSA, "Não encontrei essa informação nas fontes da base.")

    def test_prompt_manda_usar_a_frase_exata(self):
        self.assertIn(f'diga exatamente: "{geracao.RECUSA}"', geracao.INSTRUCOES)
        self.assertIn("Não invente valores, datas, códigos ou pré-requisitos", geracao.INSTRUCOES)

    def test_sem_trechos_recusa_sem_chamar_llm(self):
        for backend in ("hf", "ollama", "openai", "extrativo"):
            with self.subTest(backend=backend), \
                    mock.patch.object(geracao, "_gerar_hf", side_effect=AssertionError), \
                    mock.patch.object(geracao, "_gerar_ollama", side_effect=AssertionError), \
                    mock.patch.object(geracao, "_gerar_openai", side_effect=AssertionError):
                self.assertEqual(geracao.gerar("Qual o wifi da biblioteca?", [], backend), geracao.RECUSA)

    def test_extrativo_recusa_quando_nada_casa(self):
        self.assertEqual(geracao.gerar("senha wifi biblioteca", TRECHOS, "extrativo"), geracao.RECUSA)

    def test_valor_inventado_e_detectado(self):
        self.assertEqual(geracao.valores_sem_fonte("Custa R$ 10,50 [1].", TRECHOS), ["R$ 10,50"])
        self.assertEqual(geracao.valores_sem_fonte("Custa R$ 5,20 [1].", TRECHOS), [])


class RN04NadaSaiPorPadrao(unittest.TestCase):
    """RN-04 · Nenhuma pergunta sai para serviço externo por padrão."""

    def _config_sem_variaveis(self, expr: str) -> str:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("RUMO_") and k != "OLLAMA_URL"}
        return subprocess.run([sys.executable, "-c", f"from rumo_rag import config; print({expr})"],
                              cwd=RAG, env=env, capture_output=True, text=True, check=True).stdout.strip()

    def test_backend_padrao_e_local(self):
        self.assertIn(self._config_sem_variaveis("config.BACKEND"), {"hf", "ollama", "extrativo"})

    def test_ollama_padrao_e_localhost(self):
        host = urlparse(self._config_sem_variaveis("config.OLLAMA_URL")).hostname
        self.assertIn(host, {"localhost", "127.0.0.1"})

    def test_api_externa_so_e_chamada_quando_pedida(self):
        with mock.patch.object(geracao, "_gerar_openai", side_effect=AssertionError("saiu para API externa")), \
                mock.patch.object(geracao, "_gerar_hf", return_value="ok [1]"), \
                mock.patch.object(geracao, "_gerar_ollama", return_value="ok [1]"):
            for backend in ("hf", "ollama"):
                geracao.gerar("pergunta", TRECHOS, backend)


class RN05SemDadoPessoal(unittest.TestCase):
    """RN-05 · Não coleta dado pessoal, não pede login, não acessa o SIGAA."""

    def test_geracao_recebe_so_pergunta_e_trechos(self):
        self.assertEqual(list(inspect.signature(geracao.gerar).parameters), ["pergunta", "trechos", "backend"])

    def test_nenhuma_fonte_e_o_proprio_sigaa(self):
        for id_, d in DOCS.items():
            with self.subTest(doc=id_):
                self.assertNotEqual(urlparse(d["url"]).hostname, "sigaa.unb.br")

    def test_codigo_nao_pede_credencial(self):
        proibido = re.compile(r"\b(senha|password|getpass|matr[ií]cula_do_usu|login\()", re.I)
        for arq in (RAG / "rumo_rag").glob("*.py"):
            with self.subTest(arquivo=arq.name):
                self.assertIsNone(proibido.search(arq.read_text(encoding="utf-8")))

    def test_saida_nao_tem_identidade_de_quem_perguntou(self):
        from rumo_rag import __main__ as cli
        with mock.patch.object(cli.indice, "buscar_com_subperguntas", return_value=TRECHOS), \
                mock.patch.object(cli.indice, "decompor", return_value=[]), \
                mock.patch.object(cli.geracao, "gerar", return_value="Custa R$ 5,20 [1]."):
            r = cli.responder("Quanto custa o almoço?", "extrativo")
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
        self.assertEqual(set(r), esperadas, "campo novo na saída: confira se não identifica o estudante")


if __name__ == "__main__":
    unittest.main()
