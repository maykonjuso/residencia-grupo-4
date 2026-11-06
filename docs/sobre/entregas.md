# Entregas e versões

| Versão | Data | Entrega | Conteúdo |
|---|---|---|---|
| 1.0 | Semana 1 | Entrega 1 · Definições do projeto | Problema, partes interessadas, escopo, riscos, métricas, Essential Question e divisão com o Grupo 09 |
| 2.0 | 09/11/2026 | Entrega 2 · Base de conhecimento + protótipo de RAG | 36 fontes, chunking, embeddings, ChromaDB, busca híbrida, LLM local, demonstração com fontes, avaliação e diagrama animado de integração |

<p class="legenda">Tabela 1. Histórico de versões desta GitPage.</p>

Envio: os artefatos também vão para a pasta da equipe no Teams, canal **Segundo Desafio**, como pede o enunciado.

## Registro de mudanças da Entrega 2

| Mudança | Motivo | Efeito medido |
|---|---|---|
| Qwen2.5-1.5B → Qwen2.5-7B (4 bits) | O 1,5B inventava preços e pratos | Sem alucinação nas perguntas da demonstração |
| Cardápio lido como tabela | Texto corrido misturava os dias | Um registro por refeição e por dia (15 por semana) |
| Subseções unidas à seção-mãe | O chunk de preço não dizia de qual grupo era | O chunk do Grupo II traz o grupo e os valores juntos |
| Datas e códigos como termo único no BM25 + peso 3 | O embedding não separava os dias do cardápio | Almoço de 11/11 passou a vir em 1º |
| multilingual-e5-base → bge-m3 | Comparação no conjunto de teste | Hit@1 (denso): 0,875 → 0,969 |
| Embeddings em fp16 | O bge-m3 em fp32 mais o LLM de 7B estouravam a GPU de 8 GB | Os dois cabem na mesma placa |

<p class="legenda">Tabela 2. Decisões tomadas ao longo da Entrega 2, cada uma com motivo e efeito.</p>
