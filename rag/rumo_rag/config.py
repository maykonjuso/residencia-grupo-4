"""Configuração central do protótipo de RAG do RUmo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # rumo/rag
DADOS = RAIZ / "dados"
ORIGINAIS = DADOS / "originais"     # arquivos baixados (PDF/HTML), fora do git
TEXTO = DADOS / "texto"             # texto extraído e limpo, um .txt por documento
CHUNKS = DADOS / "chunks.jsonl"     # chunks com metadados (também alimenta o BM25)
CARDAPIO_SEMANAL_JSON = DADOS / "cardapio_semanal.json"  # cardápio semanal estruturado (fonte única do Agente RU)
CARDAPIO_SEMANAL_JSON = DADOS / "cardapio_semanal.json"  # cardápio semanal estruturado (fonte única do Agente RU)
CARDAPIO_AUTO_FETCH = os.getenv("RUMO_CARDAPIO_AUTO_FETCH", "1") != "0"
CARDAPIO_COOLDOWN_SEGUNDOS = int(os.getenv("RUMO_CARDAPIO_COOLDOWN_SEGUNDOS", "3600"))
CARDAPIO_VERIFICAR_INTERVALO_SEGUNDOS = int(os.getenv("RUMO_CARDAPIO_INTERVALO_SEGUNDOS", "3600"))
CARDAPIO_FETCH_TIMEOUT = int(os.getenv("RUMO_CARDAPIO_TIMEOUT", "15"))
CALENDARIO_JSON = DADOS / "calendario_academico.json"     # calendário acadêmico estruturado (feriados, recesso, vigência)
CATALOGO = RAIZ / "catalogo.yaml"
AVALIACAO = RAIZ / "avaliacao"
PERGUNTAS_AVALIACAO = AVALIACAO / "perguntas"
RESULTADOS_AVALIACAO = AVALIACAO / "resultados"
SCRIPTS_AVALIACAO = AVALIACAO / "scripts"

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
# Modo da busca na API: hibrido (padrão, precisa do índice no ChromaDB) | bm25 (sem torch nem ChromaDB)
BUSCA = os.getenv("RUMO_BUSCA", "hibrido" if CHROMA.exists() else "bm25")

# Geração: hf (transformers local) | ollama | openai (API compatível) | extrativo (sem LLM)
BACKEND = os.getenv("RUMO_LLM_BACKEND", "hf")
MODELO_HF = os.getenv("RUMO_HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
HF_4BIT = os.getenv("RUMO_HF_4BIT", "1") == "1"   # quantização em 4 bits (bitsandbytes)
MODELO_OLLAMA = os.getenv("RUMO_OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENAI_URL = os.getenv("RUMO_OPENAI_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("RUMO_OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = float(os.getenv("RUMO_OPENAI_TIMEOUT", "180"))

# Reescrita de consultas compostas: Estágio 1 (LiquidAI/d1-omni-600M em GPU) + Estágio 2 (LLM Decomposer)
MODELO_DECISAO = os.getenv("RUMO_DECISION_MODEL", "LiquidAI/d1-omni-600M")
LIMIAR_COMPOSTA = float(os.getenv("RUMO_DECISION_THRESHOLD", "0.39"))
MODELO_DECOMPOSITOR = os.getenv("RUMO_DECOMP_MODEL", MODELO_OLLAMA)
USAR_D1 = os.getenv("RUMO_USAR_D1", "1") != "0"
