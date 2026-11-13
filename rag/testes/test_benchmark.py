"""Testes automatizados do pipeline de benchmark e métricas de qualidade (Milestone 2).

Valida:
1. Carregamento e integridade do dataset de benchmark (38 perguntas).
2. Cálculo genuíno das métricas de qualidade (ALCE, Fidelidade, Alucinação, Recusa, Completude, ROUGE-L).
3. Conformidade estrita com o Requisito R3 (Zero Latência) em todas as estruturas e saídas.
4. Execução fim a fim no modo determinístico (dry-run) e via CLI.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from rag import benchmark
from rag.rumo_rag import config, geracao


class TestDatasetBenchmark:
    """Validação do dataset de benchmark compilado."""

    def test_total_perguntas_e_distribuicao(self):
        casos = benchmark.carregar_perguntas_benchmark()
        assert len(casos) == 38, f"Esperado exatamente 38 perguntas, encontrado {len(casos)}"

        ouro = [c for c in casos if c.get("tipo") == "simples"]
        compostas = [c for c in casos if c.get("tipo") == "composta"]
        negativas = [c for c in casos if c.get("tipo") == "fora_da_base"]

        assert len(ouro) == 32, f"Esperado 32 perguntas ouro, encontrado {len(ouro)}"
        assert len(compostas) == 5, f"Esperado 5 perguntas compostas C01-C05, encontrado {len(compostas)}"
        assert len(negativas) == 1, f"Esperado 1 pergunta negativa D7, encontrado {len(negativas)}"

    def test_campos_obrigatorios_em_cada_pergunta(self):
        casos = benchmark.carregar_perguntas_benchmark()
        campos_obrigatorios = {"id", "pergunta", "eixo", "tipo", "tem_base", "docs_esperados", "resposta_referencia"}

        for c in casos:
            for campo in campos_obrigatorios:
                assert campo in c, f"Campo obrigatório '{campo}' ausente na pergunta {c.get('id')}"
            assert isinstance(c["pergunta"], str) and len(c["pergunta"].strip()) > 5
            assert isinstance(c["docs_esperados"], list)
            assert isinstance(c["resposta_referencia"], str) and len(c["resposta_referencia"].strip()) > 0

    def test_perguntas_compostas_estrutura(self):
        casos = benchmark.carregar_perguntas_benchmark()
        compostas = [c for c in casos if c.get("tipo") == "composta"]
        ids = {c["id"] for c in compostas}
        assert ids == {"C01", "C02", "C03", "C04", "C05"}

        for c in compostas:
            subs = c.get("subperguntas_esperadas", [])
            assert len(subs) >= 2, f"Pergunta composta {c['id']} deve ter pelo menos 2 subperguntas"
            criterios = c.get("criterios_completude", [])
            assert len(criterios) >= 2, f"Pergunta composta {c['id']} deve ter critérios para cada subpergunta"

    def test_pergunta_negativa_d7(self):
        casos = benchmark.carregar_perguntas_benchmark()
        d7 = next((c for c in casos if c["id"] == "D7"), None)
        assert d7 is not None, "Pergunta D7 ausente no dataset"
        assert d7["tem_base"] is False, "D7 deve possuir tem_base = False"
        assert d7["docs_esperados"] == [], "D7 não deve possuir documentos esperados"
        assert geracao.RECUSA in d7["resposta_referencia"]


class TestMetricasQualidade:
    """Validação matemática e comportamental das métricas de qualidade."""

    def test_calcular_rouge_l(self):
        # Textos idênticos -> F1 = 1.0
        assert benchmark.calcular_rouge_l("O almoço custa R$ 4,50.", "O almoço custa R$ 4,50.") == 1.0

        # Textos completamente disjuntos -> F1 = 0.0
        assert benchmark.calcular_rouge_l("Engenharia de Software", "Restaurante Universitário") == 0.0

        # Sobreposição parcial
        score = benchmark.calcular_rouge_l(
            "O estudante paga R$ 4,50 no almoço do RU.",
            "O estudante de graduação paga R$ 4,50 no almoço do RU da UnB."
        )
        assert 0.70 <= score <= 0.95

        # Strings vazias
        assert benchmark.calcular_rouge_l("", "") == 1.0
        assert benchmark.calcular_rouge_l("Texto", "") == 0.0

    def test_calcular_taxa_citacao_valida(self):
        resultados = [
            {"tem_base": True, "citacao_valida": True},
            {"tem_base": True, "citacao_valida": True},
            {"tem_base": True, "citacao_valida": False},
            {"tem_base": False, "citacao_valida": False},  # Fora da base não entra no denominador
        ]
        # 2 válidas em 3 com base = 2/3 = 0.6667
        taxa = benchmark.calcular_taxa_citacao_valida(resultados)
        assert taxa == pytest.approx(0.6667, rel=1e-3)

    def test_calcular_fidelidade_factual(self):
        resultados = [
            {"total_afirmacoes": 4, "afirmacoes_comprovadas": 3},
            {"total_afirmacoes": 2, "afirmacoes_comprovadas": 2},
        ]
        # (3 + 2) / (4 + 2) = 5/6 = 0.8333
        taxa = benchmark.calcular_fidelidade_factual(resultados)
        assert taxa == pytest.approx(0.8333, rel=1e-3)

    def test_calcular_taxa_alucinacao(self):
        resultados = [
            {"valores_sem_fonte": ["R$ 10,00"]},
            {"valores_sem_fonte": []},
            {"valores_sem_fonte": ["FGA9999", "12h"]},
            {"valores_sem_fonte": []},
        ]
        # 2 respostas com valores sem fonte em 4 = 0.50
        taxa = benchmark.calcular_taxa_alucinacao(resultados)
        assert taxa == 0.50

    def test_calcular_recusa_negativa(self):
        resultados = [
            {"tem_base": True, "eh_recusa": False},
            {"tem_base": False, "eh_recusa": True},   # Recusa correta
            {"tem_base": False, "eh_recusa": False},  # Alucinou sem recusar
        ]
        # 1 recusa em 2 perguntas sem base = 0.50
        taxa = benchmark.calcular_recusa_negativa(resultados)
        assert taxa == 0.50

    def test_calcular_completude_multihop(self):
        resultados = [
            {"tipo": "composta", "total_subperguntas": 2, "subperguntas_atendidas": 2},
            {"tipo": "composta", "total_subperguntas": 2, "subperguntas_atendidas": 1},
            {"tipo": "simples", "total_subperguntas": 1, "subperguntas_atendidas": 1},  # Simples não entra
        ]
        # (2 + 1) / (2 + 2) = 3/4 = 0.75
        taxa = benchmark.calcular_completude_multihop(resultados)
        assert taxa == 0.75

    def test_avaliar_fidelidade_resposta_detecta_alucinacao_numerica(self):
        trecho = [{
            "texto": "O almoço custa R$ 4,50 para estudantes.",
            "secao": "Preços",
        }]
        # Resposta com valor alucinado R$ 10,00 não pode ser considerada comprovada
        resp_alucinada = "O almoço custa R$ 10,00 [1]."
        taxa, comprovadas, total = benchmark.avaliar_fidelidade_resposta(resp_alucinada, trecho, tem_base=True)
        assert comprovadas == 0
        assert taxa == 0.0

        # Resposta correta com valor do trecho
        resp_fiel = "O almoço custa R$ 4,50 para estudantes [1]."
        taxa_ok, comprovadas_ok, total_ok = benchmark.avaliar_fidelidade_resposta(resp_fiel, trecho, tem_base=True)
        assert comprovadas_ok == 1
        assert taxa_ok == 1.0


class TestRequisitoR3ZeroLatencia:
    """Auditoria rigorosa do Requisito R3: estrita exclusão de métricas de latência e tempo."""

    def test_verificar_ausencia_latencia_sucesso_em_estrutura_limpa(self):
        dados_limpos = {
            "metricas": {
                "taxa_citacao_valida": 0.98,
                "fidelidade_factual": 0.95,
                "taxa_alucinacao_numerica": 0.00,
            },
            "itens": [
                {"id": "Q01", "resposta": "texto [1]", "citacoes_usadas": [1]},
                {"id": "Q02", "resposta": "texto [2]", "citacoes_usadas": [2]},
            ],
        }
        # Não deve lançar exceção
        benchmark.verificar_ausencia_latencia(dados_limpos)

    @pytest.mark.parametrize("campo_proibido", [
        "tempo_busca_s",
        "tempo_geracao_s",
        "tempo_decomposicao_s",
        "tempo_total_s",
        "latencia_ms",
        "p50_latency",
        "p95_duration",
        "throughput_tokens",
        "tokens_por_segundo",
        "duracao_segundos",
    ])
    def test_verificar_ausencia_latencia_bloqueia_campos_proibidos(self, campo_proibido):
        dados_com_infracao = {
            "id": "Q01",
            "resposta": "Ok",
            campo_proibido: 1.23,
        }
        with pytest.raises(ValueError, match="Violação do Requisito R3"):
            benchmark.verificar_ausencia_latencia(dados_com_infracao)

    def test_execucao_benchmark_nao_contem_campos_de_latencia(self):
        dados = benchmark.executar_benchmark(dry_run=True)
        # Auditoria recursiva de todo o payload gerado
        benchmark.verificar_ausencia_latencia(dados)

        # Checagem explícita nos resultados individuais
        for item in dados["resultados"]:
            chaves = set(item.keys())
            for chave in chaves:
                for proibido in benchmark.TERMOS_PROIBIDOS_LATENCIA:
                    assert proibido not in chave.lower(), f"Campo proibido '{chave}' encontrado no item {item['id']}"

    def test_tabela_markdown_e_json_sem_latencia(self):
        dados = benchmark.executar_benchmark(dry_run=True)
        md = benchmark.formatar_resultados_markdown(dados)
        json_str = json.dumps(dados)

        # Garante que termos de medição de tempo não constam no corpo das tabelas
        assert "tempo_busca" not in md
        assert "tempo_geracao" not in md
        assert "latencia" not in md.lower()
        assert "tempo_busca" not in json_str
        assert "tempo_geracao" not in json_str


class TestExecucaoBenchmarkEndToEnd:
    """Validação da execução completa ponta a ponta e interfaces CLI."""

    def test_executar_benchmark_dry_run_completo(self):
        dados = benchmark.executar_benchmark(dry_run=True)
        assert dados["perguntas_total"] == 38
        assert dados["modo_dry_run"] is True
        assert dados["conformidade_requisito_r3"] is True

        # Total de resultados: 38 Sem RAG + 38 Com RAG = 76
        assert len(dados["resultados"]) == 76

        metricas = dados["metricas_consolidadas"]
        assert "sem_rag" in metricas
        assert "com_rag" in metricas

        # Verificação das metas do projeto no RUmo RAG
        com_rag = metricas["com_rag"]
        assert com_rag["taxa_citacao_valida"] >= 0.95
        assert com_rag["fidelidade_factual"] >= 0.90
        assert com_rag["taxa_alucinacao_numerica"] == 0.00
        assert com_rag["taxa_recusa_negativa"] == 1.00
        assert com_rag["completude_multihop"] >= 0.85
        assert com_rag["rouge_l"] > 0.60

        # Verificação do contraste qualitativo com LLM puro (Sem RAG)
        sem_rag = metricas["sem_rag"]
        assert sem_rag["taxa_citacao_valida"] == 0.00
        assert sem_rag["taxa_alucinacao_numerica"] > 0.00
        assert sem_rag["taxa_recusa_negativa"] == 0.00
        assert sem_rag["completude_multihop"] < com_rag["completude_multihop"]

    def test_executar_benchmark_apenas_rag(self):
        dados = benchmark.executar_benchmark(dry_run=True, gerar_puro=False, gerar_rag=True)
        assert len(dados["resultados"]) == 38
        assert all(r["regime"] == "com_rag" for r in dados["resultados"])
        assert "com_rag" in dados["metricas_consolidadas"]
        assert "sem_rag" not in dados["metricas_consolidadas"]

    def test_executar_benchmark_apenas_puro(self):
        dados = benchmark.executar_benchmark(dry_run=True, gerar_puro=True, gerar_rag=False)
        assert len(dados["resultados"]) == 38
        assert all(r["regime"] == "sem_rag" for r in dados["resultados"])
        assert "sem_rag" in dados["metricas_consolidadas"]
        assert "com_rag" not in dados["metricas_consolidadas"]

    def test_cli_dry_run_md(self, capsys):
        code = benchmark.main(["--dry-run", "--saida", "md"])
        assert code == 0
        captured = capsys.readouterr()
        assert "Relatório Comparativo de Benchmark: LLM Puro × RUmo RAG" in captured.out
        assert "Taxa de citação válida (ALCE)" in captured.out
        assert "Fidelidade factual (RAGAS)" in captured.out

    def test_cli_dry_run_json(self, capsys):
        code = benchmark.main(["--dry-run", "--saida", "json"])
        assert code == 0
        captured = capsys.readouterr()
        obj = json.loads(captured.out)
        assert obj["perguntas_total"] == 38
        assert obj["conformidade_requisito_r3"] is True

    def test_cli_salvar_arquivo_saida(self, tmp_path):
        arquivo = tmp_path / "saida_benchmark.md"
        code = benchmark.main(["--dry-run", "--saida", "md", "--arquivo-saida", str(arquivo)])
        assert code == 0
        assert arquivo.exists()
        conteudo = arquivo.read_text(encoding="utf-8")
        assert "Relatório Comparativo de Benchmark" in conteudo
        assert "Taxa de citação válida (ALCE)" in conteudo
