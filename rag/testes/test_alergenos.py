"""Alergênicos por prato lidos dos ícones do cardápio oficial (Issue #55).

Os valores esperados foram conferidos à mão contra as imagens dos PDFs F08 e F09
(as 6 páginas). Se um destes testes quebrar depois de mexer em `alergenos.py`,
a leitura dos ícones mudou: confira a página renderizada antes de mudar o teste.

Os casos são verificados no JSON de montagem de prato (coleta/cardapio.py, #54),
que é o que a interface e o monta-prato (#63) consomem.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rumo_rag import alergenos, config  # noqa: E402
from rumo_rag.coleta import cardapio  # noqa: E402

IDS = {aid for aid, _ in cardapio.ALERGENICOS_OFICIAIS}


def _alergenicos(data, refeicao, nome):
    for r in cardapio.buscar(data, refeicao):
        for comp in r["compartimentos"]:
            for o in comp["opcoes"]:
                if o["nome"] == nome:
                    return set(o["alergenicos"])
    raise AssertionError(f"opção não encontrada: {data} {refeicao} {nome}")


def _w(texto, x0, top, x1=None, bottom=None):
    return {"text": texto, "x0": x0, "x1": x1 if x1 is not None else x0 + 8 * len(texto),
            "top": top, "bottom": bottom if bottom is not None else top + 10}


class TestFuncoesPuras(unittest.TestCase):
    def test_divide_a_celula_sem_perder_palavra(self):
        casos = {
            "Rosé / Limão": ["Rosé", "Limão"],
            "Leite integral OU Bebida de soja": ["Leite integral", "Bebida de soja"],
            "Pão francês ou Pão careca ou": ["Pão francês", "Pão careca"],
            "Mix de doces OPÇÃO: Frutas": ["Mix de doces", "OPÇÃO: Frutas"],
            "Chipotle /Limão": ["Chipotle", "Limão"],
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                palavras = [_w(t, 10 * i, 100) for i, t in enumerate(texto.split())]
                opcoes, fluxo = alergenos._celula(palavras)
                self.assertEqual([" ".join(w["text"] for w in op) for op in opcoes], esperado)
                itens = [{"opcao": "", "alergenos": [], "conferir": False} for _ in opcoes]
                self.assertEqual(alergenos.anotar(fluxo, itens), texto)   # sem ícone, texto intacto

    def test_etiqueta_vai_logo_depois_de_cada_opcao(self):
        palavras = [_w(t, 10 * i, 100) for i, t in enumerate("Rosé / Limão".split())]
        _, fluxo = alergenos._celula(palavras)
        itens = [{"opcao": "Rosé", "alergenos": ["Leite e derivados", "Ovo"], "conferir": False},
                 {"opcao": "Limão", "alergenos": [], "conferir": False}]
        self.assertEqual(alergenos.anotar(fluxo, itens), "Rosé [Alergênicos: Leite e derivados, Ovo] / Limão")

    def test_etiqueta_e_lida_pelo_parser_do_cardapio(self):
        chunk = {"chunk_id": "F99-0001", "doc_id": "F99", "pagina": 1, "titulo": "RU Gama", "url": "",
                 "secao": "Jantar · segunda-feira 09/11/2026",
                 "texto": "## Jantar · segunda-feira 09/11/2026\n"
                          "- Molho para salada: Rosé [Alergênicos: Leite e derivados, Ovo] / Limão\n"
                          "- Sobremesa: Mix de doces [Alergênicos: Leite e derivados, Amendoim] OPÇÃO: Frutas\n"
                          "- Prato principal padrão: Lasanha [Alergênicos: Trigo/Glúten, Leite e derivados]"}
        r = cardapio.estruturar_chunk(chunk)
        cardapio.validar(r)
        alerg = {o["nome"]: o["alergenicos"] for c in r["compartimentos"] for o in c["opcoes"]}
        self.assertEqual(alerg, {"Rosé": ["leite", "ovo"], "Limão": [], "Mix de doces": ["leite", "amendoim"],
                                 "Frutas": [], "Lasanha": ["gluten", "leite"]})
        self.assertEqual(r["avisos"], [])

    def test_icone_duvidoso_nao_vira_afirmacao(self):
        item = {"opcao": "Prato X", "alergenos": [], "conferir": True}
        self.assertEqual(alergenos.etiqueta(item), "[Alergênicos: a conferir na distribuição]")
        chunk = {"chunk_id": "F99-0002", "doc_id": "F99", "pagina": 1, "titulo": "RU Gama", "url": "",
                 "secao": "Almoço · segunda-feira 09/11/2026",
                 "texto": "## Almoço · segunda-feira 09/11/2026\n- Guarnição: Prato X " + alergenos.etiqueta(item)}
        r = cardapio.estruturar_chunk(chunk)
        self.assertEqual(r["compartimentos"][0]["opcoes"][0]["alergenicos"], [])
        self.assertTrue(any("a conferir" in a for a in r["avisos"]))

    def test_icone_vai_para_a_palavra_da_mesma_linha(self):
        # "Mix de doces [ícone]" na linha de cima, "OPÇÃO: Frutas" embaixo; o ícone encosta nas duas
        mix = [{"text": "doces", "x0": 50, "x1": 80, "top": 100, "bottom": 110}]
        fruta = [{"text": "Frutas", "x0": 60, "x1": 95, "top": 112, "bottom": 122}]
        icone = {"cx": 100, "top": 98, "bottom": 115}
        self.assertEqual(alergenos._dono(icone, [mix, fruta]), 0)

    def test_icone_antes_do_texto(self):
        chipotle = [{"text": "Chipotle", "x0": 60, "x1": 95, "top": 100, "bottom": 110}]
        limao = [{"text": "Limão", "x0": 60, "x1": 90, "top": 115, "bottom": 125}]
        icone = {"cx": 50, "top": 98, "bottom": 112}
        self.assertEqual(alergenos._dono(icone, [chipotle, limao]), 0)


class TestCardapiosConferidos(unittest.TestCase):
    """Itens conferidos contra a imagem do cardápio (F08: 02–06/11, F09: 09–13/11/2026)."""

    def test_pratos_com_alergenicos(self):
        casos = [
            ("2026-11-10", "almoco", "Lasanha de frango", {"gluten", "leite"}),
            ("2026-11-10", "almoco", "Yakissoba", {"amendoim", "soja", "gluten"}),
            ("2026-11-12", "almoco", "Suflê de batata", {"leite", "gluten", "ovo"}),
            ("2026-11-11", "jantar", "Strogonoff de frango", {"leite", "gluten", "cogumelo"}),
            ("2026-11-09", "jantar", "Rosé", {"leite", "ovo"}),
            ("2026-11-09", "cafe", "Bebida de soja", {"soja"}),
            ("2026-11-09", "cafe", "Leite integral", {"leite"}),
            ("2026-11-09", "cafe", "Pão francês", {"gluten"}),
            ("2026-11-06", "almoco", "Feijoada", {"suino", "pimenta"}),
            ("2026-11-03", "jantar", "Frango assado ao molho mostarda e mel", {"gluten", "leite", "mel"}),
            ("2026-11-05", "cafe", "Patê de frango", {"gluten", "ovo", "leite"}),
            ("2026-11-03", "almoco", "Chipotle", {"pimenta"}),
        ]
        for data, refeicao, nome, esperado in casos:
            with self.subTest(opcao=nome, data=data):
                self.assertEqual(_alergenicos(data, refeicao, nome), esperado)

    def test_opcoes_sem_icone_ficam_sem_alergenico(self):
        # o RU não marca ícone nestes: o sistema não pode inventar (Requeijão de ervas é vegetal)
        casos = [
            ("2026-11-09", "cafe", "Requeijão de ervas"),
            ("2026-11-09", "cafe", "creme vegetal"),
            ("2026-11-10", "almoco", "Frutas"),
            ("2026-11-09", "jantar", "Limão"),
            ("2026-11-03", "almoco", "Limão"),
            ("2026-11-04", "jantar", "Filé de peixe ao molho de ervas"),
        ]
        for data, refeicao, nome in casos:
            with self.subTest(opcao=nome, data=data):
                self.assertEqual(_alergenicos(data, refeicao, nome), set())

    def test_sobremesa_recebe_o_icone_e_nao_a_fruta(self):
        self.assertEqual(_alergenicos("2026-11-10", "almoco", "Mix de doces"), {"leite", "amendoim"})
        self.assertEqual(_alergenicos("2026-11-10", "almoco", "Frutas"), set())

    def test_nenhum_valor_inventado(self):
        etiqueta = re.compile(r"\[Alergênicos: ([^\]]*)\]")
        for c in cardapio.carregar_chunks_cardapio():
            for lista in etiqueta.findall(c["texto"]):
                with self.subTest(chunk=c["chunk_id"]):
                    self.assertNotRegex(lista, r"\d")                   # nada de número (calorias etc.)
                    self.assertNotIn(alergenos.A_CONFERIR, lista)       # nenhum ícone duvidoso nestas semanas
            r = cardapio.estruturar_chunk(c)
            for comp in r["compartimentos"]:
                for o in comp["opcoes"]:
                    self.assertTrue(set(o["alergenicos"]) <= IDS, o)


@unittest.skipUnless((config.ORIGINAIS / "F09.pdf").exists(), "PDF original ausente (rode `ingerir`)")
class TestReextracao(unittest.TestCase):
    def test_reler_o_pdf_reproduz_o_texto_da_base(self):
        from rumo_rag import extracao
        doc = next(d for d in extracao.carregar_catalogo() if d["id"] == "F09")
        self.assertEqual(extracao.extrair(doc), (config.TEXTO / "F09.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
