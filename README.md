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

Integração com o Grupo 09 (mapeamento da FCTE): veja `docs/visao/escopo-grupos.md`.
