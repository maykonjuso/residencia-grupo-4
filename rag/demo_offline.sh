#!/usr/bin/env bash
# Demonstração do RUmo rodando 100% local, sem internet.
#
#   ./demo_offline.sh                      # roda as perguntas da demonstração
#   ./demo_offline.sh "sua pergunta"       # roda uma pergunta
#   ./demo_offline.sh --prova "pergunta"   # idem, com a rede externa bloqueada por proxy morto
#
# Dica para a apresentação: desligue o Wi-Fi antes de rodar. Nada aqui sai da máquina.
set -euo pipefail
cd "$(dirname "$0")"

PY=../.venv/bin/python
MODELO_OLLAMA=${RUMO_OLLAMA_MODEL:-qwen2.5:3b}

# Modo offline do Hugging Face: usa o bge-m3 já em cache, sem consultar o Hub.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ANONYMIZED_TELEMETRY=False
export RUMO_LLM_BACKEND=ollama RUMO_OLLAMA_MODEL="$MODELO_OLLAMA"

PROVA=0
if [ "${1:-}" = "--prova" ]; then
  PROVA=1; shift
  # Qualquer chamada externa falha (127.0.0.1:9 não escuta); localhost segue liberado para o Ollama.
  export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9
  export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
fi

echo "════ RUmo · RAG local ════"
echo "Embeddings  : ${RUMO_EMBEDDING:-BAAI/bge-m3} (cache em ~/.cache/huggingface, modo offline)"
echo "Banco vetor.: $($PY -c 'import sys; sys.path.insert(0,"."); from rumo_rag import config; print(config.CHROMA)')"
echo "Base léxica : dados/chunks.jsonl ($(wc -l < dados/chunks.jsonl | tr -d ' ') chunks)"
echo -n "LLM         : $MODELO_OLLAMA via Ollama em ${OLLAMA_URL:-http://localhost:11434} · "
if curl -s -m 5 "${OLLAMA_URL:-http://localhost:11434}/api/tags" >/dev/null; then echo "no ar"; else
  echo "FORA DO AR — rode 'ollama serve'"; exit 1; fi
[ "$PROVA" = 1 ] && echo "Rede externa: BLOQUEADA (proxy inexistente); só localhost responde"
echo "══════════════════════════"
echo

if [ "$#" -eq 0 ]; then
  exec $PY -m rumo_rag demo --backend ollama
else
  exec $PY -m rumo_rag perguntar --backend ollama "$@"
fi
