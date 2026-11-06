# Entrega 2 · Base de conhecimento + protótipo de RAG

**Semana 2 do Challenge 2.** Prazo: segunda-feira, 09/11/2026, às 8h. Foco desta etapa, segundo o enunciado: *qualidade da recuperação de informação, fundamentação das respostas e rastreabilidade das fontes, não a interface*.

## Checklist do que foi pedido

### Artefatos

- [x] **Base de conhecimento curada:** 36 documentos oficiais com catálogo, órgão, data, URL e critérios de curadoria. [Ver base](base-de-conhecimento.md)
- [x] **Mínimo de 20 documentos-fonte:** 36 (11 do RU, 22 do fluxo de disciplinas, 3 de apoio)
- [x] **Descrição da estratégia de chunking:** por estrutura (títulos, artigos, itens), com regras especiais para cardápio e grades. [Ver chunking](chunking.md)
- [x] **Descrição da estratégia de embeddings:** BAAI/bge-m3, escolhido por comparação com multilingual-e5-base. [Ver embeddings](embeddings.md)
- [x] **Implementação de um banco vetorial:** ChromaDB persistente com 1.738 chunks e metadados, mais índice BM25. [Ver banco vetorial](banco-vetorial.md)

### Demonstração

- [x] **Consulta submetida ao sistema:** 8 perguntas reais pela linha de comando
- [x] **Recuperação dos chunks mais relevantes:** top 5 com ID, página e similaridade
- [x] **Resposta fundamentada no conteúdo recuperado:** LLM local responde só com os trechos
- [x] **Evidência das fontes usadas:** cada [n] da resposta vira documento, página e URL. [Ver demonstração](demonstracao.md)

### Documentação

- [x] **Diagrama de arquitetura:** [Ver arquitetura](arquitetura.md) e o [diagrama animado com o Grupo 09](../visao/como-funciona.md)
- [x] **Pipeline de ingestão de dados:** [Ver pipeline](pipeline-ingestao.md)

### Além do pedido

- [x] [Avaliação quantitativa da recuperação](avaliacao.md): 32 perguntas com resposta conhecida, comparando BM25, busca densa e híbrida e dois modelos de embedding
- [x] [Como executar](como-executar.md) tudo com quatro comandos

## Resultado em números

| | |
|---|---|
| Documentos-fonte | 36 |
| Chunks indexados | 1.738 (mediana de 847 caracteres) |
| Modelo de embedding | BAAI/bge-m3 (1.024 dimensões) |
| Banco vetorial | ChromaDB (HNSW, distância de cosseno) |
| Busca | Híbrida: vetorial + BM25, com fusão RRF |
| LLM | Qwen2.5-7B-Instruct, 4 bits, local (RTX 4060, 8 GB) |
| Hit@5 / MRR (32 perguntas) | 1,000 / 0,959 |

<p class="legenda">Tabela 1. Resumo técnico da Entrega 2.</p>
