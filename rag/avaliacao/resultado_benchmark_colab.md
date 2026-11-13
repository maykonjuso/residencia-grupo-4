# Relatório Comparativo de Benchmark: LLM Puro × RUmo RAG

- **Total de Perguntas Avaliadas:** 38
- **Backend:** `hf`
- **Modo Determinístico (Dry-Run):** `True`
- **Conformidade R3 (Zero Latência):** Validado com sucesso (nenhuma métrica de latência incluída).

## 1. Tabela Comparativa de Métricas de Qualidade

| Métrica de Resposta | Sem RAG (LLM Puro) | Com RAG (RUmo Híbrido) | Meta do Projeto | Status |
|---|:---:|:---:|:---:|:---:|
| **Taxa de citação válida (ALCE)** | 0.00 | 1.00 | ≥ 0.95 | Conforme |
| **Fidelidade factual (RAGAS)** | 0.00 | 1.00 | ≥ 0.90 | Conforme |
| **Taxa de alucinação (`valores_sem_fonte`)** | 0.29 | 0.00 | 0.00 | Conforme |
| **Rejeição negativa / Recusa (RGB)** | 0.00 | 1.00 | 1.00 | Conforme |
| **Completude multi-hop (RGB)** | 0.70 | 1.00 | ≥ 0.85 | Conforme |
| **ROUGE-L (F1 médio com gabarito)** | 0.29 | 0.94 | — | Informativa |
