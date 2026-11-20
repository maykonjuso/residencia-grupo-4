"""Cardápio estruturado por compartimento — critérios de aceite da issue #54."""
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rumo_rag.coleta import cardapio  # noqa: E402
from rumo_rag.coleta.__main__ import main  # noqa: E402

CHUNKS = cardapio.carregar_chunks_cardapio()
F09 = [c for c in CHUNKS if c["doc_id"] == "F09"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", cardapio._sem_acento(s))


class TestEsquema(unittest.TestCase):
    def test_almoco_09_11_bate_com_exemplo_da_issue(self):
        r = cardapio.buscar("2026-11-09", "almoco")[0]
        cardapio.validar(r)
        self.assertEqual((r["unidade"], r["data"], r["refeicao"]), ("gama", "2026-11-09", "almoco"))
        slots = {c["slot"]: c for c in r["compartimentos"]}
        self.assertEqual(slots["salada"]["max"], 2)
        self.assertEqual([o["nome"] for o in slots["salada"]["opcoes"]], ["Alface roxa", "Caponata de berinjela"])
        trilhas = {o["trilha"]: o["nome"] for o in slots["principal"]["opcoes"]}
        self.assertEqual(trilhas, {"padrao": "Carne ao molho de vinho",
                                   "ovolacto": "Berinjela recheada com quinoa gratinada",
                                   "vegano": "Soja refogada com legumes"})
        self.assertEqual(r["mesa_apoio"], ["água", "farinha", "molho de pimenta", "vinagre", "azeite", "sal"])
        self.assertEqual(r["fonte"]["doc_id"], "F09")
        self.assertEqual(r["fonte"]["pagina"], 2)
        # alergênicos lidos dos ícones do PDF (Issue #55), conferidos contra a imagem da página 2
        self.assertTrue(r["alergenicos"]["disponivel"])
        self.assertEqual(len(r["alergenicos"]["legenda"]), 10)
        self.assertEqual(r["alergenicos"]["observacao"], "")
        alerg = {o["nome"]: o["alergenicos"] for c in r["compartimentos"] for o in c["opcoes"]}
        self.assertEqual(alerg["Caponata de berinjela"], ["cogumelo"])
        self.assertEqual(alerg["Carne ao molho de vinho"], ["soja"])
        self.assertEqual(alerg["Berinjela recheada com quinoa gratinada"], ["leite"])
        self.assertEqual(alerg["Soja refogada com legumes"], ["soja"])
        self.assertEqual(alerg["Alface roxa"], [])

    def test_alergenicos_anotados_no_texto_sao_normalizados(self):
        c = {
            "chunk_id": "F98-0001",
            "doc_id": "F98",
            "pagina": 2,
            "titulo": "RU Gama",
            "url": "https://ru.unb.br/cardapio-gama/",
            "secao": "Almoço · segunda-feira 16/11/2026",
            "texto": (
                "## Almoço · segunda-feira 16/11/2026\n"
                "- Prato principal padrão: Frango com creme de milho [Alergênicos: Leite e derivados, Trigo/Glúten]\n"
                "- Prato principal vegetariano estrito: Soja refogada [Alergênicos: soja]"
            ),
        }
        r = cardapio.estruturar_chunk(c)
        cardapio.validar(r)
        self.assertTrue(r["alergenicos"]["disponivel"])
        self.assertEqual(r["alergenicos"]["observacao"], "")
        opcoes = {o["trilha"]: o for o in r["compartimentos"][0]["opcoes"]}
        self.assertEqual(opcoes["padrao"]["nome"], "Frango com creme de milho")
        self.assertEqual(opcoes["padrao"]["alergenicos"], ["leite", "gluten"])
        self.assertEqual(opcoes["vegano"]["alergenicos"], ["soja"])

    def test_todas_as_refeicoes_da_semana_validam_no_schema(self):
        self.assertTrue(F09)
        for c in F09:
            with self.subTest(chunk=c["chunk_id"]):
                cardapio.validar(cardapio.estruturar_chunk(c))

    def test_cafe_tem_compartimentos_proprios(self):
        r = cardapio.buscar("2026-11-09", "cafe")[0]
        slots = {c["slot"] for c in r["compartimentos"]}
        self.assertTrue({"panificacao", "gordura", "fruta", "complemento", "bebida"} <= slots)
        bebidas = [o["nome"] for c in r["compartimentos"] if c["slot"] == "bebida" for o in c["opcoes"]]
        self.assertEqual(bebidas, ["Leite integral", "Bebida de soja"])   # OU separa


class TestProcedencia(unittest.TestCase):
    def test_cada_opcao_tem_doc_id_e_pagina(self):
        for c in F09:
            r = cardapio.estruturar_chunk(c)
            for comp in r["compartimentos"]:
                for o in comp["opcoes"]:
                    with self.subTest(chunk=c["chunk_id"], opcao=o["id"]):
                        self.assertEqual(o["fonte"]["doc_id"], c["doc_id"])
                        self.assertEqual(o["fonte"]["pagina"], c["pagina"])


class TestFidelidadeAoChunk(unittest.TestCase):
    def test_item_a_item_cada_opcao_aparece_no_texto_do_chunk(self):
        for c in F09:
            texto = _norm(c["texto"])
            for comp in cardapio.estruturar_chunk(c)["compartimentos"]:
                for o in comp["opcoes"]:
                    nome = _norm(o["nome"])
                    if comp["slot"] == "arroz":          # "Arroz branco e integral" -> 2 opções
                        nome = nome.replace("arroz ", "")
                    with self.subTest(chunk=c["chunk_id"], opcao=o["nome"]):
                        self.assertIn(nome, texto)

    def test_nenhuma_linha_do_chunk_fica_de_fora(self):
        for c in F09:
            r = cardapio.estruturar_chunk(c)
            nomes = " | ".join(_norm(o["nome"]) for comp in r["compartimentos"] for o in comp["opcoes"])
            for linha in c["texto"].splitlines():
                m = cardapio.LINHA.match(linha.strip())
                if not m:
                    continue
                # a etiqueta "[Alergênicos: ...]" (#55) não faz parte do nome; o parser também a ignora
                valor = re.sub(r"\s*\[[^\]]*\]", "", m.group("valor"))
                valor = cardapio.SEPARADORES.split(valor)[0]
                primeira = _norm(re.split(r"\s+e\s+", valor)[0])
                with self.subTest(chunk=c["chunk_id"], linha=linha):
                    self.assertIn(primeira.replace("arroz ", ""), nomes)


class TestMalformado(unittest.TestCase):
    def _chunk(self, linhas: str) -> dict:
        return {"chunk_id": "F99-0000", "doc_id": "F99", "pagina": 1, "titulo": "RU Gama", "url": "",
                "secao": "Café da manhã · segunda-feira 09/11/2026",
                "texto": "## Café da manhã · segunda-feira 09/11/2026\n" + linhas}

    def test_ou_solto_no_fim_gera_aviso_e_nao_excecao(self):
        r = cardapio.estruturar_chunk(self._chunk("- Panificação: Pão francês ou Pão careca ou"))
        nomes = [o["nome"] for o in r["compartimentos"][0]["opcoes"]]
        self.assertEqual(nomes, ["Pão francês", "Pão careca"])
        self.assertTrue(any("solto" in a for a in r["avisos"]))

    def test_o_caso_real_do_f09_gera_aviso(self):
        r = cardapio.buscar("2026-11-09", "cafe")[0]
        self.assertTrue(any("Panificação" in a for a in r["avisos"]))

    def test_rotulo_desconhecido_e_celula_vazia_nao_quebram(self):
        r = cardapio.estruturar_chunk(self._chunk("- Coisa nova: Tapioca\n- Fruta: \n- lixo sem dois pontos"))
        cardapio.validar(r)
        self.assertIn("coisa_nova", {c["slot"] for c in r["compartimentos"]})
        self.assertNotIn("fruta", {c["slot"] for c in r["compartimentos"]})
        self.assertGreaterEqual(len(r["avisos"]), 2)

    def test_chunk_sem_nada_reconhecivel(self):
        c = self._chunk("texto qualquer")
        c["secao"] = "???"
        r = cardapio.estruturar_chunk(c)
        self.assertEqual(r["compartimentos"], [])
        self.assertTrue(r["avisos"])


class TestDecisoes(unittest.TestCase):
    def test_acompanhamentos_viram_arroz_e_feijao(self):
        r = cardapio.buscar("2026-11-12", "jantar")[0]          # "Arroz branco e Integral Feijão preto"
        slots = {c["slot"]: [o["nome"] for o in c["opcoes"]] for c in r["compartimentos"]}
        self.assertEqual(slots["arroz"], ["Arroz branco", "Arroz integral"])
        self.assertEqual(slots["feijao"], ["Feijão preto"])

    def test_opcao_e_barra_separam_alternativas(self):
        r = cardapio.buscar("2026-11-10", "almoco")[0]          # "Mix de doces OPÇÃO: Frutas"
        sobremesa = next(c for c in r["compartimentos"] if c["slot"] == "sobremesa")
        self.assertEqual([o["nome"] for o in sobremesa["opcoes"]], ["Mix de doces", "Frutas"])
        r = cardapio.buscar("2026-11-11", "almoco")[0]          # "Manjericão / Limão"
        molho = next(c for c in r["compartimentos"] if c["slot"] == "molho")
        self.assertEqual(len(molho["opcoes"]), 2)

    def test_e_nao_separa(self):
        r = cardapio.buscar("2026-11-11", "jantar")[0]          # "Alho e limão" é um molho só
        molho = next(c for c in r["compartimentos"] if c["slot"] == "molho")
        self.assertEqual([o["nome"] for o in molho["opcoes"]], ["Alho e limão"])


class TestCLI(unittest.TestCase):
    def _rodar(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            codigo = main(list(args))
        return codigo, out.getvalue(), err.getvalue()

    def test_comando_do_criterio_de_aceite(self):
        codigo, out, _ = self._rodar("cardapio", "--estruturado", "--data", "2026-11-09", "--refeicao", "almoco")
        self.assertEqual(codigo, 0)
        cardapio.validar(json.loads(out))

    def test_data_sem_cardapio_recusa(self):
        codigo, out, err = self._rodar("cardapio", "--estruturado", "--data", "2030-01-01", "--refeicao", "almoco")
        self.assertEqual(codigo, 1)
        self.assertIn("Não encontrei", err)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
