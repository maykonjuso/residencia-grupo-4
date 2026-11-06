# Como executar

## Requisitos

- Python 3.11 ou mais recente
- GPU NVIDIA com 8 GB para o LLM local (opcional: sem GPU, use `--backend extrativo`, `ollama` ou `openai`)
- Cerca de 12 GB livres em disco (modelos bge-m3 e Qwen2.5-7B)

## Passo a passo

```bash
# 1. ambiente
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. ingestão: baixa as fontes, extrai, divide, gera embeddings e indexa
cd rag
python -m rumo_rag ingerir

# 3. pergunta
python -m rumo_rag perguntar "Quanto um estudante de graduação paga no almoço do RU?"

# 4. avaliação e demonstração
python -m rumo_rag avaliar
python -m rumo_rag demo
python exportar_demo.py           # atualiza os dados da demonstração na GitPage
```

## Opções

| Opção | Exemplo | Efeito |
|---|---|---|
| `--eixo` | `--eixo ru` | Busca só no eixo RU, fluxo ou apoio |
| `-k` | `-k 8` | Número de trechos entregues ao LLM |
| `--backend` | `--backend extrativo` | `hf` (padrão, local), `ollama`, `openai` ou `extrativo` (sem LLM) |
| `RUMO_EMBEDDING` | `RUMO_EMBEDDING=intfloat/multilingual-e5-base` | Troca o modelo de embedding (refaça `ingerir`) |
| `RUMO_HF_MODEL` | `RUMO_HF_MODEL=Qwen/Qwen2.5-3B-Instruct` | Troca o LLM local |
| `RUMO_HF_4BIT` | `RUMO_HF_4BIT=0` | Desliga a quantização |
| `RUMO_OPENAI_URL`, `RUMO_OPENAI_MODEL`, `RUMO_OPENAI_KEY` | | API compatível com OpenAI |
| `OLLAMA_URL`, `RUMO_OLLAMA_MODEL` | `RUMO_OLLAMA_MODEL=qwen2.5:7b` | Ollama local |

<p class="legenda">Tabela 1. Opções da linha de comando e variáveis de ambiente.</p>

## Rodar esta GitPage

```bash
mkdocs serve        # http://127.0.0.1:8000
mkdocs build        # gera site/
```
