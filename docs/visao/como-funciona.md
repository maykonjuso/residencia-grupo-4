---
hide:
  - navigation
  - toc
---

# Como o RUmo funciona e conversa com o Grupo 09

Escolha um cenário e clique em **▶ Reproduzir** (ou avance com **▶|**). Cada passo destaca quem está agindo e mostra os dados trocados.

<div class="rm-fluxo" data-fluxo data-cenario="1"></div>

<p class="legenda">Figura 1. Diagrama interativo. Verde: sistema do Grupo 04. Laranja: sistema do Grupo 09 (proposta de contrato; a implementação interna é do Grupo 09). Azul: camada comum aos dois grupos. Use "Tela cheia" para apresentar.</p>

## Visão geral em uma imagem

A mesma arquitetura, sem animação, para leitura rápida ou impressão.

```mermaid
flowchart LR
    E([Estudante]) --> P[Portal único<br/>identidade visual UnB]
    P --> O{{Orquestrador<br/>LLM roteador}}
    subgraph G04 [Grupo 04 · RUmo]
        direction LR
        A4[API /perguntar] --> B4[Busca híbrida<br/>bge-m3 + BM25 · RRF]
        B4 --> C4[(ChromaDB<br/>1.7 mil chunks)]
        C4 --> L4[LLM Qwen2.5-7B<br/>responde só com os trechos]
        L4 --> R4[Resposta + fontes]
        K4[(36 fontes oficiais<br/>RU + fluxo)] -. ingestão offline .-> C4
    end
    subgraph G09 [Grupo 09 · Mapeamento FCTE]
        direction LR
        A9[API /perguntar] --> B9[RAG do Grupo 09] --> R9[Rota + fontes]
        K9[(Plantas da FCTE)] -.-> B9
    end
    O -- "RU, cardápio, disciplinas" --> A4
    O -- "salas, prédios, rotas" --> A9
    R4 -- "grupo = grupo04" --> O
    R9 -- "grupo = grupo09" --> O
    O --> P --> E
    classDef g04 fill:#e6f4ec,stroke:#008137,color:#00381a
    classDef g09 fill:#fff1e3,stroke:#f39325,color:#5a2a00
    classDef comum fill:#e6eef7,stroke:#003f7a,color:#00223f
    class A4,B4,C4,L4,R4,K4 g04
    class A9,B9,R9,K9 g09
    class P,O comum
```

<p class="legenda">Figura 2. Arquitetura dos dois sistemas e da camada comum.</p>

## O que acontece em cada parte

| Parte | Responsável | O que faz |
|---|---|---|
| Portal único | Grupos 04 e 09 | Recebe a pergunta e mostra a resposta com selos de fonte, nas cores e fontes da UnB |
| Orquestrador | Grupos 04 e 09 | Classifica a pergunta, divide quando ela mistura assuntos e chama um ou os dois sistemas |
| API do RUmo | Grupo 04 | `POST /perguntar` no contrato comum ([ver contrato](escopo-grupos.md#contrato-de-api-proposto)) |
| Busca híbrida + ChromaDB | Grupo 04 | Recupera os trechos mais relevantes das 36 fontes ([detalhes](../entrega-2/arquitetura.md)) |
| LLM gerador | Grupo 04 | Escreve a resposta só com os trechos e cita cada um; sem base, recusa |
| API e RAG do Grupo 09 | Grupo 09 | Respondem sobre salas, prédios e rotas no campus |

<p class="legenda">Tabela 1. Responsabilidades por componente.</p>
