---
hide:
  - navigation
  - toc
---

# A esteira do RAG, passo a passo

O RUmo trabalha em duas fases. Na **ingestão**, feita uma vez, os documentos oficiais viram pedaços (chunks), os chunks viram vetores e os vetores vão para o banco. Na **pergunta**, feita a cada consulta, a pergunta vira vetor, busca os trechos mais parecidos e o LLM responde só com eles, citando a fonte.

Clique em **▶ Reproduzir** para ver as duas fases em sequência, ou clique em uma estação para ir direto a ela. As setas do teclado (← →) também avançam e voltam. Na fase 2, escolha um exemplo: os três são **saídas reais do protótipo**.

<div class="rm-est" data-esteira tabindex="0" aria-label="Animação da esteira do RAG do RUmo"></div>

<p class="legenda">Figura 1. Esteira animada do RAG. Verde: RU. Azul: fluxo das engenharias. Laranja: apoio (calendário, assistência). O mapa do banco vetorial é uma projeção ilustrativa em 2D; os números de similaridade e as notas RRF são os reais. Use o botão de tela cheia para apresentar.</p>

## Resumo em texto

=== "Fase 1 · Ingestão (offline)"

    | Passo | O que acontece | Código |
    |---|---|---|
    | 1. Fontes oficiais | 36 documentos da UnB registrados com órgão, data, URL e eixo | `rag/catalogo.yaml` |
    | 2. Extração | PDF/HTML → texto limpo; marca `[[PAGINA n]]` para citar a página | `rag/rumo_rag/extracao.py` |
    | 3. Chunking | Corte por estrutura (títulos, artigos, itens), ~900 caracteres, cabeçalho de contexto | `rag/rumo_rag/chunking.py` |
    | 4. Embeddings | BAAI/bge-m3 transforma cada chunk em 1.024 números | `rag/rumo_rag/indice.py` |
    | 5. Banco vetorial | 1.738 vetores no ChromaDB (HNSW, cosseno) + índice BM25 das palavras | `rag/rumo_rag/indice.py` |

=== "Fase 2 · Pergunta (online)"

    | Passo | O que acontece | Código |
    |---|---|---|
    | 1. Pergunta | O estudante escreve em linguagem natural | `rag/rumo_rag/__main__.py` |
    | 2. Vira vetor | Mesmo modelo bge-m3; em paralelo, palavras-chave para o BM25 | `indice.py · embed_consulta()` |
    | 3. Busca híbrida | 30 candidatos por significado + 30 por palavra exata | `indice.py · buscar()` |
    | 4. Fusão RRF | `peso ÷ (60 + posição)`; datas e códigos dão peso 3 ao BM25; ficam os 5 melhores | `indice.py · buscar()` |
    | 5. Prompt | Regras + trechos numerados `[1]…[5]` + pergunta | `geracao.py · montar_mensagens()` |
    | 6. LLM | Qwen2.5-7B local, 4 bits, sem sorteio; cita `[n]` ou recusa | `geracao.py` |
    | 7. Resposta | Cada `[n]` vira fonte com página e link oficial | `geracao.py` |

<p class="legenda">Tabela 1. As duas fases da esteira. Detalhes em <a href="../../entrega-2/arquitetura/">Diagrama de arquitetura</a>, <a href="../../entrega-2/chunking/">Chunking</a>, <a href="../../entrega-2/embeddings/">Embeddings</a> e <a href="../../entrega-2/banco-vetorial/">Banco vetorial</a>.</p>
