"""Testes de unidade e integração do runner para Google Colab (colab_benchmark.py).

Verifica:
- Detecção de hardware e auto-tune de RUMO_HF_4BIT
- Verificação e indexação da base de dados ChromaDB
- Pré-aquecimento condicional dos modelos neurais
- Execução do benchmark com auditoria estrita de zero latência (R3)
- Geração correta dos artefatos JSON e Markdown
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import colab_benchmark


class TestColabBenchmark(unittest.TestCase):
    def test_token_hf_carregamento(self):
        with mock.patch.dict(os.environ, {"HF_TOKEN": "hf_teste_123"}, clear=False):
            token = colab_benchmark.carregar_token_hf()
            self.assertEqual(token, "hf_teste_123")

    def test_detectar_gpu_e_configurar_vram_com_gpu_potente(self):
        # Simula GPU com 24GB (L4 / A100)
        mock_torch = mock.MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA L4"
        mock_torch.cuda.get_device_properties.return_value.total_memory = 24 * (1024 ** 3)
        mock_torch.cuda.is_bf16_supported.return_value = True

        with mock.patch.dict("sys.modules", {"torch": mock_torch}), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUMO_HF_4BIT", None)
            info = colab_benchmark.detectar_gpu_e_configurar_vram()
            self.assertTrue(info["cuda_disponivel"])
            self.assertEqual(info["vram_gb"], 24.0)
            self.assertEqual(os.environ.get("RUMO_HF_4BIT"), "0")
            self.assertFalse(info["4bit"])

    def test_detectar_gpu_e_configurar_vram_com_gpu_padrao(self):
        # Simula GPU com 15GB (T4)
        mock_torch = mock.MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "Tesla T4"
        mock_torch.cuda.get_device_properties.return_value.total_memory = 15 * (1024 ** 3)
        mock_torch.cuda.is_bf16_supported.return_value = False

        with mock.patch.dict("sys.modules", {"torch": mock_torch}), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUMO_HF_4BIT", None)
            info = colab_benchmark.detectar_gpu_e_configurar_vram()
            self.assertTrue(info["cuda_disponivel"])
            self.assertEqual(info["vram_gb"], 15.0)
            self.assertEqual(os.environ.get("RUMO_HF_4BIT"), "1")
            self.assertTrue(info["4bit"])

    def test_garantir_indexacao_base_dry_run(self):
        res = colab_benchmark.garantir_indexacao_base(dry_run=True)
        self.assertEqual(res, 0)

    def test_garantir_indexacao_base_colecao_ja_preenchida(self):
        with mock.patch("rag.rumo_rag.indice.colecao") as m_col:
            m_col.return_value.count.return_value = 1738
            res = colab_benchmark.garantir_indexacao_base(dry_run=False)
            self.assertEqual(res, 1738)

    def test_pre_aquecer_modelos_dry_run_nao_executa(self):
        with mock.patch("rag.rumo_rag.reescrita._carregar_decisor") as m_dec, \
             mock.patch("rag.rumo_rag.geracao._hf") as m_hf:
            colab_benchmark.pre_aquecer_modelos(backend="hf", dry_run=True)
            m_dec.assert_not_called()
            m_hf.assert_not_called()

    def test_executar_colab_benchmark_dry_run_gera_arquivos_e_audita(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arq_saida = Path(tmpdir) / "subpasta" / "resultado.json"
            dados = colab_benchmark.executar_colab_benchmark(
                backend="hf",
                dry_run=True,
                saida_formato="json",
                arquivo_saida=arq_saida,
            )

            # Verifica integridade dos dados retornados
            self.assertEqual(dados["perguntas_total"], 38)
            self.assertTrue(dados["conformidade_requisito_r3"])
            self.assertIn("sem_rag", dados["metricas_consolidadas"])
            self.assertIn("com_rag", dados["metricas_consolidadas"])

            # Verifica criação do JSON e do MD
            self.assertTrue(arq_saida.exists())
            self.assertTrue(arq_saida.with_suffix(".md").exists())

            # Auditoria de ausência de latência
            conteudo_json = arq_saida.read_text(encoding="utf-8")
            for proibido in ("tempo", "latencia", "latency", "duration", "throughput", "tokens_s"):
                self.assertNotIn(f'"{proibido}"', conteudo_json.lower())

    def test_main_cli_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            saida = Path(tmpdir) / "teste_main.json"
            codigo = colab_benchmark.main(["--dry-run", "--arquivo-saida", str(saida), "--saida", "md"])
            self.assertEqual(codigo, 0)
            self.assertTrue(saida.exists())


if __name__ == "__main__":
    unittest.main()
