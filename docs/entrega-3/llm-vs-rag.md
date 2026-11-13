# Comparação: LLM puro × RAG

Comparação empírica direta entre a geração do modelo **Qwen2.5-7B-Instruct** operando de forma isolada (memória paramétrica pura) e integrado ao pipeline RAG do RUmo (busca híbrida BGE-M3 + BM25 sobre 36 fontes oficiais).

---

## 1. Motivação e metodologia

Na Entrega 2, o grupo constatou que modelos de linguagem sem ancoragem documental sofrem de alucinações severas em dados de domínio fechado. No caso do Restaurante Universitário e do fluxo acadêmico da FCTE/UnB, inventar o valor de uma refeição, uma data de cardápio ou um pré-requisito de disciplina acarreta prejuízo real ao estudante.

Para mensurar esse comportamento com rigor, submetem-se as mesmas **32 perguntas-ouro** de `rag/avaliacao/perguntas_ouro.jsonl`, mais **3 perguntas fora da base** de `rag/avaliacao/perguntas_fora_da_base.jsonl` (entre elas a D7 da demonstração), a dois regimes com o mesmo modelo, o mesmo hardware e a mesma decodificação (gulosa, `do_sample=False`, quantização 4 bits na RTX 4060):

1. **LLM puro (Sem RAG):** o índice não é consultado. O modelo recebe a mesma persona do RUmo, a mesma frase de recusa e o mesmo limite de 120 palavras, mas nenhum trecho de documento (e, por consequência, nenhuma regra de citação [n]).
2. **RUmo (Com RAG):** a pergunta aciona a busca híbrida; os 5 chunks mais relevantes são injetados no contexto, acompanhados de metadados, regra de citação obrigatória [n] e instrução estrita de recusa fora da base (RF03 e RF04). O prompt é exatamente o da Entrega 2.

Manter a regra de recusa nos dois modos é proposital: assim, se o RUmo recusa e o LLM puro inventa, a diferença vem dos documentos, e não de uma permissão de recusar que só um dos lados recebeu.

Para reproduzir:

```bash
cd rag
python -m rumo_rag comparar            # grava avaliacao/respostas_comparativas.json
python gerar_tabela_comparativa.py     # atualiza as Tabelas 3, 4 e 5 desta página
```

No modo sem RAG, `valores_sem_fonte` lista os preços, datas, horários e códigos da resposta que não aparecem nos trechos que a base devolve para a mesma pergunta, ou seja, valores que a fonte oficial não sustenta.

---

## 2. Casos comparativos representativos

A **Tabela 1** apresenta três casos emblemáticos selecionados do conjunto de avaliação que ilustram as diferenças qualitativas esperadas e os padrões de resposta observados entre as duas abordagens.

| Pergunta | Resposta do LLM Puro (Sem RAG) | Resposta do RUmo (Com RAG) | Diagnóstico da Diferença |
|---|---|---|---|
| **Q01:** *"Quanto custa o almoço no RU para um estudante de graduação sem auxílio?"* | *Tendência a alucinar valor plausível mas incorreto (ex: R$ 5,00 ou R$ 3,50).* | *Recupera os valores oficiais exatos (R$ 6,10 para Grupo III) com citação [1] de F01/F04.* | **Alucinação eliminada:** Ancoragem estrita elimina a invenção de tarifas do RU. |
| **Q14:** *"Quais são os pré-requisitos de Testes de Software?"* | *Tendência a misturar convenções de outros cursos ou universidades (ex: citar POO ou Engenharia de Requisitos).* | *Recupera o pré-requisito formal da matriz da FCTE citando o fluxograma F16.* | **Erro de fluxo corrigido:** Respeito à matriz curricular oficial da FCTE/UnB. |
| **D7 (Fora da base):** *"Qual o wifi da biblioteca da FCTE?"* | *Tendência a inventar nomes de rede genéricos (ex: `UnB-WiFi` ou `FCTE-Visitante`).* | *Responde com recusa expressa: "Não encontrei essa informação nas fontes da base" (RF04).* | **Recusa correta:** Evita inventar credenciais ou configurações sem evidência oficial. |

<p class="legenda">Tabela 1. Casos representativos do protocolo de comparação entre modelo puro e RUmo com RAG.</p>

---

## 3. O caso em que o RAG não ajudou {: #o-caso-em-que-o-rag-nao-ajudou }

Um sistema que relata apenas sucessos mascara fragilidades de engenharia. Em conformidade com o rigor técnico do projeto, documenta-se a seguir um caso real em que **o pipeline RAG clássico falha em produzir a resposta completa**, evidenciando o limite da recuperação textual pura.

### A pergunta de teste

> *"Se um estudante for reprovado em Cálculo 1 no 1º semestre de Engenharia de Software, quais disciplinas ele fica impossibilitado de cursar até o 3º semestre?"*

### O que acontece na execução

A **Tabela 2** detalha o diagnóstico da resposta gerada pelo sistema frente ao gabarito curricular oficial da matriz de Engenharia de Software.

| Dimensão | Conteúdo observado |
|---|---|
| **Documentos recuperados** | Chunks do documento F16 (*Fluxograma de Engenharia de Software FCTE*, páginas 1 e 2) e trechos do regulamento de matrícula. |
| **Comportamento do RAG** | O sistema recupera perfeitamente os chunks que contêm a lista de disciplinas e seus pré-requisitos imediatos. O modelo identifica com sucesso que Cálculo 1 tranca Cálculo 2 no 2º semestre. Contudo, **omite as dependências de 2ª ordem no 3º semestre** (disciplinas que exigem Cálculo 2 ou Física 1 em cascata). |
| **Gabarito curricular esperado** | O estudante fica impedido de cursar **Cálculo 2** (2º semestre) e, por transitividade de pré-requisito em cascata, as disciplinas subsequentes do 3º semestre que exigem Cálculo 2. |
| **Diagnóstico da falha** | **Incompletude por falha de encadeamento transitivo.** O RAG recuperou os chunks corretos, mas a resposta final falhou na dedução em cascata. |

<p class="legenda">Tabela 2. Diagnóstico da limitação do RAG em cadeia de pré-requisitos transitivos.</p>

### Causa-raiz da limitação

1. **RAG não é motor de inferência em grafo:** O chunk do fluxograma contém a tabela de relações de pré-requisitos imediatos. Mapear dependências em cascata (onde A tranca B, que tranca C) exige busca recursiva em grafo direcionado acíclico (DAG). O LLM de 7B, mesmo com o texto correto no contexto, tem dificuldade de computar caminhos transitivos longos a partir de listas de texto semiestruturadas.
2. **Dispersão de atenção em contexto denso:** O chunk de fluxograma contém dezenas de disciplinas dispostas em tabela. O modelo sofre de perda de foco nas relações secundárias distantes no prompt (*lost in the middle*).

### Lição aprendida e encaminhamento de engenharia

Esse resultado comprova que **RAG puramente textual é insuficiente para raciocínio sobre fluxogramas acadêmicos complexos**. Esse achado fundamenta a arquitetura da próxima etapa:

- **Evolução na Entrega 4 (Multiagentes):** Criação de uma ferramenta determinística especializada (*tool calling*) para o **Agente Fluxo**, capaz de consultar a estrutura de dados de disciplinas em grafo estruturado (JSON/NetworkX), em vez de pedir ao LLM que deduza caminhos de pré-requisitos a partir de texto corrido.

---

## 4. Matriz consolidada e registro das 32 perguntas-ouro

As **Tabelas 3 e 5** consolidam a rodada por eixo temático (`ru`, `apoio`, `fluxo` e `fora`) e por categoria de pergunta. As colunas de valores sem fonte e de recusas são automáticas; as de alucinação, fidelidade e incompletude vêm do julgamento humano registrado em `rag/avaliacao/diagnosticos_comparativos.json`.

--8<-- "includes/llm_vs_rag_resumo.md"

A **Tabela 4** (recolhida por padrão devido à extensão) registra individualmente as **32 perguntas-ouro** (`Q01` a `Q32`) e as **3 perguntas fora da base** (`X01` a `X03`), mapeando o eixo, a categoria, os documentos esperados e os campos para coleta lado a lado (Sem RAG × Com RAG). Após a execução do benchmark, os casos mais relevantes serão escoados desta tabela mestre para as tabelas analíticas específicas.

??? info "Tabela 4 · Registro completo das 32 perguntas-ouro e 3 fora da base: LLM puro × RAG (clique para expandir)"

    --8<-- "includes/llm_vs_rag_tabela4.md"

    <p class="legenda">Tabela 4. Tabela mestre das 32 perguntas-ouro e das 3 fora da base, gerada por <code>rag/gerar_tabela_comparativa.py</code>, para comparação lado a lado entre LLM puro e RUmo com RAG.</p>

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Especificação do protocolo de comparação LLM × RAG, casos de teste e análise do caso de falha | Grupo 04 |
    | 11/11/2026 | 1.1 | Inclusão da Tabela 4 recolhida com as 32 perguntas-ouro de `perguntas_ouro.jsonl` | Grupo 04 |
    | 13/11/2026 | 1.2 | Modo sem RAG (`--sem-rag`, `comparar`), perguntas fora da base, Tabelas 3, 4 e 5 geradas a partir de `respostas_comparativas.json` e metodologia alinhada ao código (#17, #28) | Kyara |
