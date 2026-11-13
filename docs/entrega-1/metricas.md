# Métricas de sucesso

As métricas foram definidas na Semana 1 e já são medidas a partir da Entrega 2. Cada uma tem meta e forma de cálculo.

## Recuperação (Entrega 2)

| Métrica | Definição | Meta | Resultado na Entrega 2 |
|---|---|---|---|
| Hit@1 | Fração das perguntas de teste em que o 1º trecho vem de um documento correto | ≥ 0,80 | **0,938** (híbrido) · 0,969 (denso) |
| Hit@5 | Fração em que algum dos 5 primeiros trechos vem de um documento correto | ≥ 0,90 | **1,000** |
| MRR | Média de 1/posição do primeiro trecho correto | ≥ 0,85 | **0,959** |
| Latência da busca | Tempo da busca híbrida por pergunta | < 1 s | ≈ 0,05 s (GPU) |

<p class="legenda">Tabela 1. Métricas de recuperação. Conjunto de 32 perguntas com documento esperado (<code>rag/avaliacao/perguntas_ouro.jsonl</code>). Detalhes em <a href="../../entrega-2/avaliacao/">Avaliação da recuperação</a>.</p>

## Fundamentação e rastreabilidade (Entregas 2 e 3)

| Métrica | Definição | Meta | Sem RAG (LLM Puro) | Com RAG (RUmo Híbrido) | Status (Entrega 3) |
|---|---|:---:|:---:|:---:|:---:|
| **Taxa de citação válida (ALCE)** | Respostas com pelo menos uma citação `[n]` válida apontando para fonte do contexto | ≥ 0,95 | 0,00 | **1,00** | Conforme |
| **Fidelidade factual (RAGAS)** | Afirmações da resposta sustentadas pelos trechos recuperados | ≥ 0,90 | 0,00 | **1,00** | Conforme |
| **Recusa correta (RGB)** | Perguntas sem base respondidas com recusa expressa ("não encontrei") | 1,00 | 0,00 | **1,00** | Conforme |
| **Taxa de alucinação (`valores_sem_fonte`)** | Respostas contendo dado inventado (preço, data, horário, código, prato) | 0,00 | 0,29 | **0,00** | Conforme |
| **Completude multi-hop (RGB)** | Proporção de subperguntas respondidas em consultas compostas | ≥ 0,85 | 0,70 | **1,00** | Conforme |
| **Sobreposição léxica (ROUGE-L)** | F1 médio da maior subsequência comum com o gabarito oficial | — | 0,29 | **0,94** | Informativa |

<p class="legenda">Tabela 2. Matriz de métricas de fundamentação e fidelidade comparativa com e sem RAG aferidas na Entrega 3 (validação determinística preliminar). Detalhes em <a href="../../entrega-3/fidelidade-e-alucinacao/">Fidelidade e Alucinação</a>.</p>

## Uso (Semana 7)

| Métrica | Definição | Meta |
|---|---|---|
| Utilidade percebida | Nota de 1 a 5 dada por estudantes da FCTE após usar o sistema | ≥ 4 |
| Tempo até a resposta | Tempo para achar a informação com o RUmo × procurando nos sites | Redução ≥ 50% |
