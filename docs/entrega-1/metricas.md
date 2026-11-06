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

| Métrica | Definição | Meta |
|---|---|---|
| Taxa de citação | Respostas com pelo menos uma citação [n] válida, entre as perguntas que têm base | ≥ 0,95 |
| Fidelidade | Afirmações da resposta sustentadas pelo trecho citado (avaliação manual ou por LLM juiz) | ≥ 0,90 |
| Recusa correta | Perguntas sem base respondidas com "não encontrei" | 1,00 |
| Alucinação | Respostas com dado inventado (valor, data, código, prato) | 0 |

<p class="legenda">Tabela 2. Métricas de resposta. A Semana 3 compara essas métricas com e sem RAG.</p>

## Uso (Semana 7)

| Métrica | Definição | Meta |
|---|---|---|
| Utilidade percebida | Nota de 1 a 5 dada por estudantes da FCTE após usar o sistema | ≥ 4 |
| Tempo até a resposta | Tempo para achar a informação com o RUmo × procurando nos sites | Redução ≥ 50% |
