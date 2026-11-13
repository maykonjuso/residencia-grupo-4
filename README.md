# RUmo · Grupo 04 · Challenge 2 (Residência em IA · UnB/FCTE)

Assistente com RAG para o **Restaurante Universitário** e o **fluxo de disciplinas** das engenharias do campus Gama.
Responde só com documentos oficiais da UnB, cita cada fonte e recusa o que não está na base.

- Site: https://maykonjuso.github.io/residencia-grupo-4/
- `docs/` · GitPage (MkDocs Material) com as Entregas 1 e 2
- `rag/` · protótipo: catálogo de 36 fontes, ingestão, ChromaDB, busca híbrida, LLM local, avaliação

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd rag && python -m rumo_rag ingerir
python -m rumo_rag perguntar "Quanto um estudante de graduação paga no almoço do RU?"
cd .. && mkdocs serve
```

## API (integração com o Grupo 09)

`rag/rumo_rag/api.py` implementa o contrato combinado (`POST /perguntar`, `GET /saude`). O chat do portal do Grupo 09 (FcteMapping) e o OpenClaw chamam essa rota.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-api.txt   # leve: sem torch nem ChromaDB
cd rag
# geração por um modelo gratuito do OpenRouter (o backend "openai" aceita qualquer API compatível)
RUMO_LLM_BACKEND=openai RUMO_OPENAI_URL=https://openrouter.ai/api/v1 \
RUMO_OPENAI_MODEL='<modelo>:free' RUMO_OPENAI_KEY='<chave>' \
../.venv/bin/uvicorn rumo_rag.api:app --port 8001
```

- Sem o índice vetorial (`chroma_*`), a busca usa só BM25 (`RUMO_BUSCA=bm25`). Com o índice, o padrão é a busca híbrida.
- `contexto.data` resolve "hoje" e "amanhã" para a data do cardápio.
- Se o LLM falhar (cota ou rede), a resposta cai para o modo extrativo, com as frases das fontes.

Integração com o Grupo 09 (mapeamento da FCTE): veja `docs/visao/escopo-grupos.md`.
