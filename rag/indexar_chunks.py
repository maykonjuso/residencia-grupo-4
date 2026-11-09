"""Reindexa o banco vetorial a partir dos chunks já versionados em dados/chunks.jsonl.

Atalho para `python -m rumo_rag ingerir` quando o texto das fontes já está no repositório:
pula o download dos PDFs/HTMLs e a extração, e refaz só os embeddings e o índice Chroma.
Útil em máquina nova, ao trocar de modelo de embedding (RUMO_EMBEDDING) ou quando
dados/chroma_*/ foi apagado (é ignorado pelo git).

  python indexar_chunks.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rumo_rag import config, indice


def main() -> int:
    if not config.CHUNKS.exists():
        print(f"{config.CHUNKS} não existe — rode 'python -m rumo_rag ingerir'", file=sys.stderr)
        return 1
    chunks = [json.loads(linha) for linha in open(config.CHUNKS, encoding="utf-8")]
    print(f"{len(chunks)} chunks · embeddings com {config.MODELO_EMBEDDING}", flush=True)
    t0 = time.time()
    indice.indexar(chunks)
    print(f"concluído em {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
