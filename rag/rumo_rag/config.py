"""Configuração central do protótipo de RAG do RUmo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # rumo/rag
DADOS = RAIZ / "dados"
ORIGINAIS = DADOS / "originais"     # arquivos baixados (PDF/HTML), fora do git
TEXTO = DADOS / "texto"             # texto extraído e limpo, um .txt por documento
CHUNKS = DADOS / "chunks.jsonl"     # chunks com metadados (também alimenta o BM25)
CATALOGO = RAIZ / "catalogo.yaml"
AVALIACAO = RAIZ / "avaliacao"

# Embeddings: BAAI/bge-m3 (multilíngue, 1024 dimensões) venceu o multilingual-e5-base na avaliação.
# Para usar o E5: RUMO_EMBEDDING=intfloat/multilingual-e5-base (prefixos aplicados automaticamente).
MODELO_EMBEDDING = os.getenv("RUMO_EMBEDDING", "BAAI/bge-m3")
COLECAO = "rumo_fcte"
# um banco por modelo de embedding, para comparar modelos sem misturar vetores
CHROMA = DADOS / ("chroma_" + MODELO_EMBEDDING.split("/")[-1])
PREFIXOS_E5 = "e5" in MODELO_EMBEDDING.lower()  # E5 exige "query: " / "passage: "

# Chunking (em caracteres; ~4 caracteres por token em português)
CHUNK_ALVO = 900        # tamanho desejado
CHUNK_MAX = 1400        # limite duro para um chunk comum
CHUNK_MAX_CARDAPIO = 2200  # cardápios: uma refeição (página) inteira por chunk
SOBREPOSICAO = 150      # caracteres repetidos entre chunks vizinhos

# Busca
TOP_K = 5               # chunks entregues ao LLM
MAX_TRECHOS = 8         # teto quando a pergunta é composta (subperguntas)
CANDIDATOS = 30         # candidatos de cada buscador antes da fusão
RRF_K = 60              # constante da Reciprocal Rank Fusion
PESO_BM25_IDENTIFICADOR = 3.0  # peso do BM25 na fusão quando a pergunta tem data ou código de disciplina

# Geração: hf (transformers local) | ollama | openai (API compatível) | extrativo (sem LLM)
BACKEND = os.getenv("RUMO_LLM_BACKEND", "hf")
MODELO_HF = os.getenv("RUMO_HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
HF_4BIT = os.getenv("RUMO_HF_4BIT", "1") == "1"   # quantização em 4 bits (bitsandbytes)
MODELO_OLLAMA = os.getenv("RUMO_OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENAI_URL = os.getenv("RUMO_OPENAI_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("RUMO_OPENAI_MODEL", "gpt-4o-mini")
