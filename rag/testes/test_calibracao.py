"""Testes da calibração do limiar do Estágio 1 (sem carregar modelo)."""
import json
import unittest
from unittest import mock

from rag import calibrar_limiar
from rag.rumo_rag import config


class TestEscolherLimiar(unittest.TestCase):
    def test_separavel_escolhe_ponto_medio(self):
        r = calibrar_limiar.escolher_limiar([0.39, 0.42, 0.55], [0.05, 0.10, 0.20])
        self.assertTrue(r["separavel"])
        self.assertGreater(r["limiar"], 0.20)
        self.assertLessEqual(r["limiar"], 0.39)
        self.assertEqual(r["recall_compostas"], 1.0)
        self.assertEqual(r["especificidade_simples"], 1.0)

    def test_sobreposicao_maximiza_acuracia_balanceada(self):
        r = calibrar_limiar.escolher_limiar([0.30, 0.40, 0.50], [0.10, 0.35, 0.20])
        self.assertFalse(r["separavel"])
        self.assertGreater(r["acuracia_balanceada"], 0.5)

    def test_limiar_padrao_inadequado_e_corrigido(self):
        # Todas as compostas abaixo de 0,50: o limiar calibrado precisa ficar abaixo do padrão.
        r = calibrar_limiar.escolher_limiar([0.35, 0.39, 0.45], [0.02, 0.05])
        self.assertLess(r["limiar"], config.LIMIAR_COMPOSTA)

    def test_exige_as_duas_classes(self):
        with self.assertRaises(ValueError):
            calibrar_limiar.escolher_limiar([], [0.1])
        with self.assertRaises(ValueError):
            calibrar_limiar.escolher_limiar([0.9], [])


class TestConjuntoCalibracao(unittest.TestCase):
    def test_disjunto_do_benchmark_e_balanceado(self):
        calib = calibrar_limiar.carregar_calibracao()
        bench = [json.loads(l) for l in open(config.AVALIACAO / "perguntas_benchmark.jsonl", encoding="utf-8") if l.strip()]
        perguntas_bench = {b["pergunta"].strip().lower() for b in bench}
        for item in calib:
            self.assertNotIn(item["pergunta"].strip().lower(), perguntas_bench)
        self.assertEqual(sum(i["composta"] for i in calib), sum(not i["composta"] for i in calib))
        self.assertEqual(len({i["id"] for i in calib}), len(calib))

    def test_calibrar_usa_probabilidade_bruta_sem_salvar(self):
        with mock.patch("rag.calibrar_limiar.reescrita.probabilidade_multipla",
                        side_effect=lambda q: 0.6 if "?" in q and " e " in q and len(q) > 60 else 0.1):
            r = calibrar_limiar.calibrar(salvar=False)
        self.assertEqual(r["n_compostas"] + r["n_simples"], len(r["itens"]))
        self.assertIn("limiar", r)


if __name__ == "__main__":
    unittest.main()
