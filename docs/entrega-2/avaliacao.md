# Avaliação da recuperação

O foco da Entrega 2 é a **qualidade da recuperação**. Para medir isso com objetividade, o grupo montou um **conjunto de teste com 32 perguntas** de estudantes e, para cada uma, os documentos que contêm a resposta.

- Perguntas: `rag/avaliacao/perguntas_ouro.jsonl` (11 do RU, 2 de apoio, 19 do fluxo; todas as engenharias e o PPGEB)
- Comando: `python -m rumo_rag avaliar`
- Resultados: `rag/avaliacao/resultado_recuperacao*.json`

## Métricas

A avaliação da recuperação utiliza três métricas complementares, definidas na **Tabela 1**.

| Métrica | O que mede |
|---|---|
| **Hit@1** | O 1º trecho recuperado é de um documento certo? |
| **Hit@5** | Algum dos 5 trechos entregues ao LLM é de um documento certo? |
| **MRR** | Média de 1/posição do primeiro trecho certo (1 = sempre em 1º; 0,5 = em média em 2º) |

<p class="legenda">Tabela 1. Métricas. Acerto medido no nível do documento.</p>

## Resultados

A **Tabela 2** compara o desempenho das cinco configurações testadas frente às metas estipuladas na Entrega 1, e a **Figura 1** destaca a evolução do MRR entre cada abordagem.

| Configuração | Hit@1 | Hit@5 | MRR |
|---|---|---|---|
| BM25 (lexical, pós-normalização) | 0,906 | 0,969 | 0,932 |
| Vetorial · multilingual-e5-base | 0,875 | 1,000 | 0,932 |
| Híbrida · multilingual-e5-base | 0,906 | 1,000 | 0,944 |
| Vetorial · **BAAI/bge-m3** | **0,969** | **1,000** | **0,984** |
| Híbrida · **BAAI/bge-m3** (configuração final) | 0,938 | **1,000** | 0,969 |
| *Meta da Entrega 1* | *≥ 0,80* | *≥ 0,90* | *≥ 0,85* |

<p class="legenda">Tabela 2. Recuperação nas 32 perguntas. Todas as configurações passaram das metas.</p>

!!! note "Fonte dos números desta página"
    Todos os valores das Tabelas 2 e 3 são lidos de `rag/avaliacao/resultado_recuperacao.json`
    e `..._multilingual-e5-base.json`, gerados por `python -m rumo_rag avaliar`. As 32 perguntas
    estão em `rag/avaliacao/perguntas_ouro.jsonl`. Mexeu em chunking, embedding ou fusão? Rode a
    avaliação de novo e atualize estas tabelas no mesmo PR.

```mermaid
xychart-beta
    title "MRR por configuração (32 perguntas)"
    x-axis ["BM25", "e5 vetorial", "e5 híbrida", "bge-m3 vetorial", "bge-m3 híbrida"]
    y-axis "MRR" 0.8 --> 1.0
    bar [0.932, 0.932, 0.944, 0.984, 0.969]
```

<p class="legenda">Figura 1. MRR por configuração.</p>

## Leitura dos resultados

- **Em 100% das perguntas, o LLM recebeu pelo menos um trecho do documento certo** (Hit@5 = 1,000) em qualquer configuração com vetores. Isso é o que mais importa para a resposta sair fundamentada.
- **O bge-m3 é claramente melhor que o e5-base** em português: errou o 1º lugar em 1 pergunta, contra 4.
- **Por que a configuração final é a híbrida**, se a vetorial pura teve MRR maior: as 32 perguntas quase não têm datas e códigos, e é exatamente nesses identificadores que o vetor falha (ver o [caso do cardápio](embeddings.md#por-que-manter-a-busca-hibrida-se-o-bge-m3-sozinho-foi-melhor-na-media)). O grupo preferiu perder 0,025 de MRR médio a errar o dia do cardápio. Na Semana 3, o conjunto vai ganhar perguntas com datas e códigos, para medir essa troca.

## Onde a busca híbrida não pôs o documento certo em 1º

Das 32 perguntas avaliadas, apenas duas não trouxeram o documento esperado na primeira posição na configuração híbrida final; o diagnóstico de ambas está detalhado na **Tabela 3**.

| Pergunta | Esperado | Veio em 1º | Posição do certo | Causa provável |
|---|---|---|---|---|
| Q01 · "Quanto custa o almoço no RU para um estudante de graduação sem auxílio?" | F01 / F04 (preços) | F06 (Auxílio Alimentação) | 2º | "sem auxílio" puxa os documentos do auxílio; após normalização de sinônimos no BM25 subiu de 5º para 2º no híbrido |
| Q28 · "Qual o período de matrícula do 2026.2?" | F29 (calendário 2026.2) | F30 (calendário 2026.1) | 2º | "2026.2" é quebrado em "2026" e "2", e os dois calendários ficam parecidos |

<p class="legenda">Tabela 3. Falhas de 1º lugar e próximos ajustes: tratar o semestre ("2026.2") como termo único e reescrever a consulta para tirar negações como "sem auxílio". </p>

## Modo BM25 em produção (Render) × Híbrido (Issue #51)

A API publicada no Render (`render.yaml`) roda com `RUMO_BUSCA=bm25` porque o plano gratuito limita a memória a **512 MB** (inviabilizando carregar PyTorch, `BAAI/bge-m3` e ChromaDB em produção).

Antes da correção, perguntas como *"qual o preço da refeição no RU para estudantes de graduação?"* falhavam no `bm25` puro: o chunk `F04-0002` (Grupo II, R$ 4,50) usa *"Valores das refeições"* e *"valores atuais"*, enquanto a consulta usa *"preço"* e *"refeição"* (no singular). Nas 32 perguntas-ouro, 5 casos regrediam no `bm25` em relação ao híbrido, com `Q01` (preço do almoço) e `Q24` (vagas de Engenharia de Software) saindo do top-5.

**Decisão tomada:** aplicar **normalização léxica em `tokenizar` (`rag/rumo_rag/indice.py`)** (`SINONIMOS_BM25`, mapeando *"preço"*, *"custa"*, *"tarifa"*, *"valores"* → *"valor"*, além de *"refeições"* → *"refeição"* e *"estudantes"* → *"estudante"*), sem alterar o texto oficial exibido nem aumentar o uso de RAM:

| Configuração | Hit@1 | Hit@5 | MRR | Caso *"preço da refeição... graduação"* |
|---|---|---|---|---|
| BM25 antes da correção | 0,844 | 0,938 | 0,885 | `F04-0002` fora do top-5 |
| **BM25 após normalização (Render)** | **0,906** | **0,969** | **0,932** | **`F04-0002` em 1º lugar** |
| Híbrida após normalização (local) | 0,938 | 1,000 | 0,969 | `F04-0002` no top-3 |

<p class="legenda">Tabela 4. Impacto da normalização léxica para o modo BM25 em produção (<code>rag/avaliacao/resultado_recuperacao.json</code>).</p>

**Limitação residual documentada:** mesmo após a correção, o `bm25` puro ainda deixa `Q24` (*"Quantas vagas a FCTE oferta para Engenharia de Software?"*) fora do top-5 por ausência de sobreposição léxica direta, mantendo o modo **híbrido** como referência de qualidade sempre que houver memória para embeddings.

## Alergênicos por prato (Issue #55)

A Issue #55 acrescentou ao texto dos cardápios (então `F08` e `F09`, posteriormente substituídos pela coleta semanal estruturada `F56` em `rag/dados/cardapio_semanal.json`) a etiqueta de alergênicos de cada opção de prato, lida dos ícones, e incluiu a `F37`, página "Serviço alimentação" do RU. Na medição original da Entrega 3 sobre as 32 perguntas-ouro, o BM25 ficou **idêntico**: mesmos documentos nas mesmas posições, com Hit@1 0,906, Hit@5 0,969 e MRR 0,932. Fora dos dois cardápios e da `F37`, nenhum chunk havia mudado naquele momento.

As perguntas de prato abaixo (Tabela 5) registram a verificação histórica sobre `F09` em BM25 e Qwen2.5-7B local (Ollama); hoje o atendimento ao cardápio semanal e seus alergênicos ocorre via `cardapio_semanal.json` (`#54`):

| Pergunta | 1º trecho recuperado | Resposta |
|---|---|---|
| *"A lasanha de frango do dia 10/11 tem glúten?"* | `F09-0006` (histórico), com *"Lasanha de frango [Alergênicos: Trigo/Glúten, Leite e derivados]"* | Sim, citando o cardápio. Antes da #55, recusava |
| *"O strogonoff de frango do jantar de 11/11 tem leite?"* | `F09-0012` (histórico), com leite, glúten e cogumelo | Sim, citando o cardápio |
| *"O mix de doces do almoço de 10/11 tem amendoim?"* | `F09-0006` (histórico) | Sim, citando o cardápio |
| *"Quantas calorias tem o almoço do RU?"* | Nenhum trecho com calorias | Recusa |
| *"O RU tem opção para quem tem doença celíaca?"* | Trechos do guia da ANVISA (F12), **sem a F37** | — |
| *"O RU atende dieta para celíaco?"* | F37 em 3º lugar | Recusa |

<p class="legenda">Tabela 5. Perguntas de alergênicos no modo BM25 (medição histórica da Issue #55 sobre F09/F37).</p>

As duas últimas linhas mostram uma limitação de vocabulário. A F37 fala em *"dietas especializadas"*, e não em *celíaca*: a fonte só aparece quando a pergunta usa a palavra "dieta", e mesmo assim o modelo recusa, porque a página não fala de doença celíaca. A busca densa deve aproximar os termos pelo significado, mas isso só pode ser confirmado rodando `python -m rumo_rag avaliar` com o BGE-M3.

**Medição com o BGE-M3 (busca densa e híbrida).** Em 23/11/2026, `python -m rumo_rag avaliar` foi executado no Google Colab (GPU T4) duas vezes na mesma sessão: na `main` imediatamente anterior à #55 e na branch do PR #78, cada uma com o índice ChromaDB montado a partir do próprio `chunks.jsonl` (36 fontes e 1.738 chunks antes; 37 fontes e 1.742 chunks depois), sem baixar as fontes de novo. A reescrita de perguntas compostas foi desligada (`RUMO_DECISION_THRESHOLD=1.01`) para medir só a recuperação; nenhuma das 32 perguntas-ouro tem duas interrogações, então nenhuma é decomposta.

| Configuração | Antes da #55 (Hit@1 / Hit@5 / MRR) | Depois da #55 (Hit@1 / Hit@5 / MRR) |
|---|---|---|
| BM25 | 0,906 / 0,969 / 0,932 | 0,906 / 0,969 / 0,932 |
| Densa · `BAAI/bge-m3` | 0,969 / 1,000 / 0,984 | 0,969 / 1,000 / 0,984 |
| **Híbrida** · `BAAI/bge-m3` | **0,938 / 1,000 / 0,969** | **0,938 / 1,000 / 0,969** |

<p class="legenda">Tabela 6. Recuperação nas 32 perguntas-ouro antes e depois da Issue #55, nas três configurações.</p>

As três configurações ficaram **idênticas**: as etiquetas de alergênicos e a F37 não deslocaram nenhum documento esperado. Esta medição vale para a base do PR #78; a base atual, com 54 fontes, é tratada na seção seguinte (Issue #53).

## Reconciliação do corpus e conjunto-ouro (Issue #53)

Após a remoção dos cardápios semanais antigos (`F08` e `F09`), a separação do cardápio semanal vigente (`F56`) exclusivamente em `rag/dados/cardapio_semanal.json` (`#54`, sem indexação em `chunks.jsonl`) e a inclusão dos documentos de assistência estudantil da DDS/DAC (`F38`–`F55`), o catálogo passou de `37` fontes (`1.742` chunks) para **`54` fontes (`F01`–`F07`, `F10`–`F56`)**, sendo **`53` fontes permanentes indexadas (`1.954` chunks)** em `rag/dados/chunks.jsonl`.

Para manter o conjunto-ouro alinhado a fontes permanentes, `Q08` e `Q09` (que apontavam para o removido `F09`) foram substituídas em `perguntas_ouro.jsonl` e `perguntas_benchmark.jsonl` por duas perguntas permanentes do eixo `ru` ancoradas na `F37` (identificação de alergênicos no RU e funcionamento do Restaurante Executivo).

| Configuração | Corpus | Hit@1 | Hit@5 | MRR | Situação |
|---|---|---|---|---|---|
| BM25 (Entrega 3, referência anterior) | 37 fontes (`1.742` chunks) | 0,906 | 0,969 | 0,932 | Baseline histórico |
| **BM25 (pós-#53, `avaliar --modo bm25`)** | **53 fontes (`1.954` chunks)** | **0,906** | **1,000** | **0,944** | **Sem regressão** (`Q01` `2→0`, `Q24` `fora→4`, `Q10` `0→1`, `Q31` `1`) |
| Vetorial · `BAAI/bge-m3` | 37 fontes (Entrega 3) | 0,969 | 1,000 | 0,984 | Preservado em `resultado_recuperacao.json` (pendente reindexação ChromaDB) |
| Híbrida · `BAAI/bge-m3` | 37 fontes (Entrega 3) | 0,938 | 1,000 | 0,969 | Preservado em `resultado_recuperacao.json` (pendente reindexação ChromaDB) |

<p class="legenda">Tabela 7. Comparativo BM25 pós-reconciliação (#53) frente ao baseline da Entrega 3 e status das medições vetorial/híbrida.</p>

Os modos `denso` e `hibrido` permanecem preservados com a medição da Entrega 3 em `rag/avaliacao/resultados/resultado_recuperacao.json` porque o índice local `rag/dados/chroma_bge-m3` (ignorado no Git) não estava construído neste ambiente; sua reavaliação sobre os `1.954` chunks requer executar `python indexar_chunks.py` seguido de `python -m rumo_rag avaliar --modo todos`.

## Limitações da avaliação

- 32 perguntas é pouco para diferenças pequenas: 1 pergunta vale 0,031 no Hit@1.
- O acerto é por **documento**, não por trecho. Um trecho do documento certo pode não ter a frase exata (por exemplo, Q20 aceita F19 ou F20).
- As perguntas foram escritas pelo grupo. Na Semana 7, entram perguntas reais coletadas com estudantes.
- Esta página mede a **recuperação**. A qualidade da **resposta** (citação e fidelidade) está na [demonstração](demonstracao.md) e será medida em escala na Semana 3 (LLM × RAG).

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 09/11/2026 | 1.0 | Avaliação inicial da recuperação (32 perguntas-ouro) | Grupo 04 |
    | 16/11/2026 | 1.1 | Medição BM25 × híbrido e normalização léxica para preços do RU (Issue #51) | Grupo 04 |
    | 18/11/2026 | 1.2 | Alergênicos por prato: BM25 idêntico nas 32 perguntas-ouro e perguntas novas de alergênicos; medição híbrida pendente (Issue #55) | Grupo 04 |
    | 20/11/2026 | 1.3 | Reconciliação #53: F08/F09 substituídos por F56 em cardapio_semanal.json, Q08/Q09 atualizadas para F37, expansão para 53 fontes indexadas (1.954 chunks) e BM25 em 0,906 / 1,000 / 0,944 (denso/híbrido preservados da Entrega 3) | Grupo 04 |
    | 23/11/2026 | 1.4 | Medição densa e híbrida (BGE-M3, Colab) antes e depois da Issue #55: idênticas nas 32 perguntas-ouro (Tabela 6) | Gabriella Oliveira |
