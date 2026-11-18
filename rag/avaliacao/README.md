# Avaliação do RUmo RAG

Diretório organizado por tipo de artefato:

```text
rag/avaliacao/
├── perguntas/     # Conjuntos de teste e calibração (.jsonl)
├── resultados/    # Saídas gravadas de métricas, benchmark e demonstração (.json / .md)
└── scripts/       # Scripts de avaliação, ablação, calibração e benchmark (.py)
```

## 1. Conjuntos de perguntas (`perguntas/`)

| Arquivo | Quantidade | Finalidade |
|---|---:|---|
| `perguntas_ouro.jsonl` | 32 | Conjunto principal de recuperação (`Hit@1`, `Hit@5`, `MRR`) usado por `rumo_rag avaliar` |
| `perguntas_demo.jsonl` | 8 | Perguntas canônicas da demonstração (`D1`–`D8`, inclui recusa fora da base em `D7`) |
| `perguntas_benchmark.jsonl` | 38 | Benchmark completo da Entrega 3 (32 ouro + 5 compostas `C01`–`C05` + negativa `D7`) |
| `perguntas_calibracao.jsonl` | 24 | Conjunto disjunto do benchmark para calibração do limiar do Estágio 1 (`d1-omni-600M`) |

## 2. Resultados gerados (`resultados/`)

| Arquivo | Origem | Conteúdo |
|---|---|---|
| `resultado_recuperacao.json` | `python -m rumo_rag avaliar` | Último comparativo `bm25` / `denso` / `hibrido` |
| `resultado_recuperacao_bge-m3.json` | `rumo_rag avaliar` (`BAAI/bge-m3`) | Baseline oficial de recuperação da Entrega 2 |
| `resultado_recuperacao_multilingual-e5-base.json` | `rumo_rag avaliar` (`intfloat/multilingual-e5-base`) | Comparativo de embedding da Entrega 2 |
| `demo_respostas.json` | `python -m rumo_rag demo` | Saídas completas da demonstração (alimentam `rag/exportar_demo.py`) |
| `resultado_reescrita.json` | `avaliar_reescrita.py` | Cobertura multi-eixo em `C01`–`C05` com e sem reescrita |
| `resultado_benchmark_colab.json` | `colab_benchmark.py` / `benchmark.py` | Métricas completas Sem RAG × Com RAG (sem campos de latência, R3) |
| `resultado_benchmark_colab.md` | `colab_benchmark.py` / `benchmark.py` | Relatório consolidado em Markdown do benchmark |
| `respostas_comparativas.json` | `colab_benchmark.py` | Respostas pareadas pergunta a pergunta (Sem RAG × Com RAG) |
| `resultado_fidelidade.json` | `colab_benchmark.py` | Métricas consolidadas ALCE, RAGAS, recusa RGB e alucinação |

## 3. Como executar os scripts (`scripts/`)

A partir da raiz do repositório (com `.venv` ativo):

```bash
# Benchmark completo Sem RAG × Com RAG (dry-run ou GPU/Ollama)
python -m rag.avaliacao.scripts.benchmark --dry-run

# Calibração do limiar do Estágio 1 (d1-omni-600M)
python -m rag.avaliacao.scripts.calibrar_limiar

# Avaliação de decomposição/reescrita nos casos compostos C01–C05 (requer Ollama local)
python rag/avaliacao/scripts/avaliar_reescrita.py

# Comparação rápida LLM Pura × RAG Extrativo × RAG Generativo (3 casos canônicos)
python rag/avaliacao/scripts/comparativo_rag.py

# Estudo de ablação das 4 configurações
python rag/avaliacao/scripts/testar_4_configuracoes.py
```

Para os comandos integrados da CLI (`avaliar` e `demo`):

```bash
cd rag
python -m rumo_rag avaliar
python -m rumo_rag demo
python exportar_demo.py
```
