"""Testes da sincronização automática do cardápio semanal no backend."""

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

RAG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAG))

from rumo_rag import api, config  # noqa: E402
from rumo_rag.coleta import cardapio, scraper  # noqa: E402

FIX = RAG / "testes" / "fixtures" / "cardapio_gama"
PAGINA = FIX / "pagina.html"
PDF = FIX / "Gama-Semana-02-31-8-a-6-9.pdf"


def _resultado_fake(ref: date) -> dict:
    inicio = ref - timedelta(days=ref.weekday())
    fim = inicio + timedelta(days=6)
    dias_pt = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
    blocos = []
    for idx in range(5):
        dia = inicio + timedelta(days=idx)
        dname = dias_pt[dia.weekday()]
        blocos.append(
            f"[[PAGINA 2]]\n"
            f"## Almoço · {dname} {dia:%d/%m/%Y}\n"
            f"Cardápio do RU Gama (FCTE) — Almoço de {dname}, {dia:%d/%m/%Y}:\n"
            f"- Prato principal padrão: Bife acebolado\n"
            f"- Prato principal vegetariano estrito: Grão-de-bico ao curry\n"
            f"- Acompanhamentos: Arroz branco e integral Feijão preto\n"
            f"- Salada: Alface e tomate\n"
        )
    return {
        "semana": scraper.Semana(inicio, fim, "https://ru.unb.br/wp-content/uploads/2026/11/semana-atual.pdf", "atual"),
        "pagina": b"<html></html>",
        "pdf": b"%PDF-1.4",
        "texto": "\n".join(blocos),
        "dias": [],
        "avisos": [],
    }


class TestScraperExigirSemana(unittest.TestCase):
    def test_exigir_semana_levanta_semana_nao_publicada_sem_baixar_pdf(self):
        urls = []

        def falso_baixar(url, timeout=scraper.TIMEOUT):
            urls.append(url)
            if url == scraper.PAGINA:
                return PAGINA.read_bytes()
            raise AssertionError(f"Não deveria baixar PDF antigo: {url}")

        with mock.patch.object(scraper, "baixar", side_effect=falso_baixar):
            with self.assertRaises(scraper.SemanaNaoPublicada) as ctx:
                scraper.coletar(date(2030, 5, 6), exigir_semana=True, timeout=7)

        self.assertEqual(urls, [scraper.PAGINA])
        self.assertIsNotNone(ctx.exception.ultima_semana)
        self.assertEqual(ctx.exception.ultima_semana.inicio, date(2026, 9, 7))

    def test_coletar_sem_exigir_semana_preserva_comportamento_legado(self):
        def falso_baixar(url, timeout=scraper.TIMEOUT):
            return PAGINA.read_bytes() if url == scraper.PAGINA else PDF.read_bytes()

        with mock.patch.object(scraper, "baixar", side_effect=falso_baixar):
            res = scraper.coletar(date(2030, 5, 6))

        self.assertEqual(res["semana"].inicio, date(2026, 9, 7))
        self.assertTrue(res["avisos"])


class TestSincronizacaoSemanal(unittest.TestCase):
    def setUp(self):
        cardapio.resetar_estado_sincronizacao()

    def tearDown(self):
        cardapio.resetar_estado_sincronizacao()

    def test_cache_hit_nao_chama_scraper(self):
        ref = date(2026, 11, 25)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "cardapio_semanal.json"
            cardapio.salvar_semana_json(_resultado_fake(ref), doc_id="F99", destino=destino)

            with mock.patch.object(scraper, "coletar") as mock_coletar:
                dados, info = cardapio.sincronizar_semana_atual(referencia=ref, caminho=destino)

        self.assertEqual(mock_coletar.call_count, 0)
        self.assertIsNotNone(dados)
        self.assertEqual(info["status"], "atualizado_cache")

    def test_remote_fetch_salva_json_valido_sem_tocar_catalogo(self):
        ref = date(2026, 11, 25)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "cardapio_semanal.json"
            catalogo_fake = Path(tmp) / "catalogo.yaml"
            catalogo_fake.write_text("documentos: []\n", encoding="utf-8")

            with (
                mock.patch.object(config, "CATALOGO", catalogo_fake),
                mock.patch.object(scraper, "coletar", return_value=_resultado_fake(ref)) as mock_coletar,
            ):
                dados, info = cardapio.sincronizar_semana_atual(referencia=ref, caminho=destino)

            self.assertEqual(mock_coletar.call_count, 1)
            self.assertIsNotNone(dados)
            self.assertEqual(info["status"], "atualizado_remoto")
            self.assertTrue(destino.exists())
            for meal in json.loads(destino.read_text(encoding="utf-8"))["refeicoes"]:
                cardapio.validar(meal)
            self.assertEqual(catalogo_fake.read_text(encoding="utf-8"), "documentos: []\n")

    def test_semana_nao_publicada_preserva_json_antigo_e_respeita_cooldown(self):
        semana_antiga = date(2026, 11, 18)
        ref = date(2026, 11, 25)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "cardapio_semanal.json"
            cardapio.salvar_semana_json(_resultado_fake(semana_antiga), doc_id="F99", destino=destino)
            conteudo_antes = destino.read_text(encoding="utf-8")
            sem_pub = scraper.Semana(date(2026, 11, 16), date(2026, 11, 22), "https://ru.unb.br/old.pdf", "old")

            with mock.patch.object(scraper, "coletar", side_effect=scraper.SemanaNaoPublicada(ref, sem_pub)) as mock_coletar:
                dados1, info1 = cardapio.sincronizar_semana_atual(referencia=ref, caminho=destino, cooldown_segundos=3600)
                dados2, info2 = cardapio.sincronizar_semana_atual(referencia=ref, caminho=destino, cooldown_segundos=3600)
                dados3, info3 = cardapio.sincronizar_semana_atual(
                    referencia=ref, caminho=destino, forcar=True, cooldown_segundos=3600
                )

            self.assertIsNone(dados1)
            self.assertIsNone(dados2)
            self.assertIsNone(dados3)
            self.assertEqual(info1["status"], "unb_nao_publicou")
            self.assertEqual(info2["status"], "em_cooldown")
            self.assertEqual(info3["status"], "unb_nao_publicou")
            self.assertEqual(mock_coletar.call_count, 2)
            self.assertEqual(destino.read_text(encoding="utf-8"), conteudo_antes)

    def test_erro_coleta_preserva_json_antigo_e_nao_lanca_excecao(self):
        semana_antiga = date(2026, 11, 18)
        ref = date(2026, 11, 25)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "cardapio_semanal.json"
            cardapio.salvar_semana_json(_resultado_fake(semana_antiga), doc_id="F99", destino=destino)
            conteudo_antes = destino.read_text(encoding="utf-8")

            with mock.patch.object(scraper, "coletar", side_effect=scraper.ErroColeta("sem conexão")):
                dados, info = cardapio.sincronizar_semana_atual(referencia=ref, caminho=destino)

            self.assertIsNone(dados)
            self.assertEqual(info["status"], "erro_coleta")
            self.assertIn("sem conexão", info["motivo"])
            self.assertEqual(destino.read_text(encoding="utf-8"), conteudo_antes)


class TestApiCardapioEndpoints(unittest.TestCase):
    def setUp(self):
        cardapio.resetar_estado_sincronizacao()

    def tearDown(self):
        cardapio.resetar_estado_sincronizacao()

    def test_saude_e_cardapio_e_atualizar_com_token(self):
        hoje = date.today()
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "cardapio_semanal.json"
            cardapio.salvar_semana_json(_resultado_fake(hoje), doc_id="F99", destino=destino)

            with (
                mock.patch.object(config, "CARDAPIO_SEMANAL_JSON", destino),
                mock.patch.object(config, "CARDAPIO_AUTO_FETCH", False),
                mock.patch.object(api, "TOKEN", "segredo-teste"),
                mock.patch.object(scraper, "coletar", return_value=_resultado_fake(hoje)) as mock_coletar,
            ):
                with TestClient(api.app) as client:
                    r_saude = client.get("/saude")
                    self.assertEqual(r_saude.status_code, 200)
                    body_saude = r_saude.json()
                    self.assertIn("cardapio", body_saude)
                    self.assertTrue(body_saude["cardapio"]["atualizado"])

                    r_card = client.get(f"/cardapio?data={hoje.isoformat()}&refeicao=almoco")
                    self.assertEqual(r_card.status_code, 200)
                    body_card = r_card.json()
                    self.assertTrue(body_card["sucesso"])
                    self.assertEqual(body_card["dados"]["data"], hoje.isoformat())

                    r_unauth = client.post("/cardapio/atualizar")
                    self.assertEqual(r_unauth.status_code, 401)

                    r_auth = client.post(
                        "/cardapio/atualizar",
                        headers={"Authorization": "Bearer segredo-teste"},
                    )
                    self.assertEqual(r_auth.status_code, 200)
                    body_upd = r_auth.json()
                    self.assertTrue(body_upd["atualizado"])
                    self.assertEqual(body_upd["status"], "atualizado_remoto")
                    self.assertEqual(mock_coletar.call_count, 1)


if __name__ == "__main__":
    unittest.main()
