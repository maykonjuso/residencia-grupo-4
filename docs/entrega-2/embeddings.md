# Estratégia de embeddings

**Resumo:** usamos o **BAAI/bge-m3** (multilíngue, 1.024 dimensões, até 8 mil tokens de entrada), com vetores normalizados e similaridade de cosseno. Ele foi escolhido depois de uma **comparação medida** com o `intfloat/multilingual-e5-base`. Os embeddings rodam localmente, na GPU, sem enviar os documentos para fora.

## Requisitos para o modelo

| Requisito | Por quê |
|---|---|
| Bom em português | Toda a base e todas as perguntas são em português |
| Local e gratuito | Sem custo por consulta; nenhum documento sai da máquina |
| Cabe em 8 GB de VRAM junto com o LLM | Hardware disponível no grupo (RTX 4060) |
| Aceita chunks de até ~2 mil caracteres | Cardápios e artigos longos |

<p class="legenda">Tabela 1. Requisitos.</p>

## Comparação feita

Os dois modelos indexaram **os mesmos chunks** (mesma versão da base) e responderam às **mesmas 32 perguntas** com documento esperado.

| Modelo | Dimensões | Busca | Hit@1 | Hit@5 | MRR | Indexação |
|---|---|---|---|---|---|---|
| multilingual-e5-base | 768 | só vetorial | 0,875 | 1,000 | 0,932 | 43 s |
| multilingual-e5-base | 768 | híbrida (+ BM25) | 0,906 | 1,000 | 0,944 | — |
| **BAAI/bge-m3** | **1.024** | **só vetorial** | **0,969** | **1,000** | **0,984** | 100–126 s |
| **BAAI/bge-m3** | **1.024** | **híbrida (+ BM25)** | **0,938** | **1,000** | **0,959** | — |
| (referência) BM25 sozinho | — | lexical | 0,844 | 0,938 | 0,885 | < 1 s |

<p class="legenda">Tabela 2. Recuperação no conjunto de teste (<code>rag/avaliacao/resultado_recuperacao_*.json</code>).</p>

**Decisão:** bge-m3, que errou o 1º trecho em 1 de 32 perguntas, contra 4 do e5-base. O custo é indexar cerca de 2,5 vezes mais devagar, o que não importa, porque a indexação roda uma vez por atualização da base.

## Por que manter a busca híbrida, se o bge-m3 sozinho foi melhor na média

No conjunto de teste, o bge-m3 puro teve MRR um pouco maior que o híbrido. Mesmo assim, mantivemos a fusão com o BM25 por um motivo observado na prática: **embeddings não distinguem identificadores exatos**.

!!! example "Caso real: o cardápio de quarta-feira"
    Na pergunta "Qual é a opção vegetariana estrita do almoço de quarta-feira, 11/11/2026?", o multilingual-e5-base deu praticamente a mesma similaridade (0,887 a 0,889) às refeições de **todos os dias** das duas semanas, e o almoço de 11/11 nem apareceu entre os 10 primeiros. Para ele, "11/11/2026" e "04/11/2026" são quase iguais. O BM25, que trata a data como um termo exato, pôs o chunk certo em 1º lugar. Com a fusão ponderada e o bge-m3, o chunk certo passou a vir em 1º na busca híbrida.

Por isso:

- datas (`11/11/2026`) e códigos de disciplina (`FGA0314`) viram **um único termo** no BM25;
- quando a pergunta tem um desses identificadores, o BM25 recebe **peso 3** na fusão (RRF ponderada).

Na Semana 3, vamos ampliar o conjunto de teste com mais perguntas desse tipo, para medir o ganho com mais precisão.

## Detalhes de uso

- **Normalização:** vetores normalizados (norma 1); cosseno = produto interno.
- **Prefixos:** o E5 exige `query:` e `passage:`; o bge-m3 não usa. O código aplica os prefixos automaticamente conforme o modelo (`config.PREFIXOS_E5`).
- **Texto embedado:** `texto_indexado` = cabeçalho (documento · órgão · seção) + conteúdo do chunk ([chunking](chunking.md#cabecalho-de-contexto)).
- **Troca de modelo:** `RUMO_EMBEDDING=intfloat/multilingual-e5-base python -m rumo_rag ingerir`. Cada modelo tem o próprio diretório de banco (`dados/chroma_<modelo>`), para não misturar vetores de dimensões diferentes.
