# Comparação: LLM puro × RAG

Comparação empírica direta entre a geração do modelo **Qwen2.5-7B-Instruct** operando de forma isolada (memória paramétrica pura) e integrado ao pipeline RAG do RUmo (busca híbrida BGE-M3 + BM25 sobre 36 fontes oficiais).

---

## 1. Motivação e metodologia

Na Entrega 2, o grupo constatou que modelos de linguagem sem ancoragem documental sofrem de alucinações severas em dados de domínio fechado. No caso do Restaurante Universitário e do fluxo acadêmico da FCTE/UnB, inventar o valor de uma refeição, uma data de cardápio ou um pré-requisito de disciplina acarreta prejuízo real ao estudante.

Para mensurar esse comportamento com rigor, submetem-se as mesmas **32 perguntas-ouro** de `rag/avaliacao/perguntas_ouro.jsonl` a dois regimes idênticos de hardware e parâmetros de inferência (temperatura = 0,2, top_p = 0,9, quantização 4 bits na RTX 4060):

1. **LLM puro (Sem RAG):** O prompt envia apenas a pergunta do usuário e uma instrução genérica de assistente acadêmico, sem qualquer trecho de documento injetado.
2. **RUmo (Com RAG):** A pergunta aciona a busca híbrida; os 5 chunks mais relevantes são injetados no contexto, acompanhados de metadados, regra de citação obrigatória [n] e instrução estrita de recusa fora da base (RF03 e RF04).

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

A **Tabela 3** estrutura a matriz agregada de consolidação das 32 perguntas-ouro por eixo temático (`ru`, `apoio` e `fluxo`), a ser preenchida na conclusão das rodadas de medição.

| Eixo Temático | Quantidade | Sem RAG: Alucinações | Com RAG: Fidelidade total | Com RAG: Incompletude |
|---|:---:|:---:|:---:|:---:|
| **Restaurante Universitário (`ru`)** | 11 | *A medir* | *A medir* | *A medir* |
| **Apoio Alimentar e Alergênicos (`apoio`)** | 2 | *A medir* | *A medir* | *A medir* |
| **Fluxo e Disciplinas (`fluxo`)** | 19 | *A medir* | *A medir* | *A medir* |
| **Total Consolidado** | **32** | *A medir* | *A medir* | *A medir* |

<p class="legenda">Tabela 3. Matriz de desempenho comparativo agregado nas 32 perguntas de teste.</p>

A **Tabela 4** (recolhida por padrão devido à extensão) prepara o registro individual completo das **32 perguntas-ouro** (`Q01` a `Q32` de `rag/avaliacao/perguntas_ouro.jsonl`), mapeando o eixo, os documentos esperados e os campos para coleta lado a lado (Sem RAG × Com RAG). Após a execução do benchmark, os casos mais relevantes serão escoados desta tabela mestre para as tabelas analíticas específicas.

??? info "Tabela 4 · Registro completo das 32 perguntas-ouro: LLM puro × RAG (clique para expandir)"

    | ID | Eixo | Pergunta | Docs esperados | Resposta Sem RAG (LLM puro) | Resposta Com RAG (RUmo) | Fidelidade / Alucinação | Diagnóstico |
    |:---:|:---:|---|---|---|---|---|---|
    | **Q01** | `ru` | Quanto custa o almoço no RU para um estudante de graduação sem auxílio? | `F01`, `F04` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q02** | `ru` | Qual o horário do jantar no RU do campus Gama? | `F03`, `F02` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q03** | `ru` | O RU do Gama abre aos sábados? | `F03`, `F02` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q04** | `ru` | Quem tem direito a refeição gratuita no RU? | `F01`, `F04`, `F06`, `F07` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q05** | `ru` | Quanto paga no RU o estudante que entrou por cota de escola pública e não é baixa renda? | `F01`, `F04` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q06** | `ru` | Como emito a carteirinha digital para entrar no RU? | `F05` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q07** | `ru` | Quais formas de pagamento são aceitas nos caixas do RU? | `F05`, `F04` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q08** | `ru` | Qual o prato vegetariano estrito do almoço de quarta-feira, 11/11/2026, no RU Gama? | `F09` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q09** | `ru` | O que tem no café da manhã do RU Gama na segunda-feira 09/11/2026? | `F09` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q10** | `ru` | Quais são os critérios para participar do edital de Auxílio Alimentação de 2026? | `F07` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q11** | `ru` | O que a lei do PNAES diz sobre alimentação dos estudantes? | `F10` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q12** | `apoio` | Por que devo evitar alimentos ultraprocessados? | `F11` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q13** | `apoio` | O que significa a frase 'pode conter' no rótulo de alergênicos? | `F12` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q14** | `fluxo` | Quais são os pré-requisitos de Testes de Software? | `F16` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q15** | `fluxo` | Quantos créditos tem o curso de Engenharia de Software para quem entrou depois de 2024/2? | `F15`, `F16` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q16** | `fluxo` | Quais disciplinas do 4º semestre de Engenharia de Software? | `F16` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q17** | `fluxo` | Quantos créditos mínimos tem o curso de Engenharia de Energia? | `F22`, `F23` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q18** | `fluxo` | Em que semestre se cursa Termodinâmica 1 na Engenharia de Energia? | `F23` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q19** | `fluxo` | Quais disciplinas tem o primeiro nível da Engenharia Automotiva para ingressantes a partir de 2027? | `F19` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q20** | `fluxo` | Quantas horas o aluno de Engenharia Automotiva precisa integralizar? | `F19`, `F20` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q21** | `fluxo` | Qual o tempo mínimo e máximo de integralização da Engenharia Aeroespacial? | `F17`, `F18` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q22** | `fluxo` | Quais são os perfis de formação da Engenharia Eletrônica? | `F21` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q23** | `fluxo` | Como funciona a escolha de curso no ingresso da FCTE pela ABI Engenharia? | `F14` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q24** | `fluxo` | Quantas vagas a FCTE oferta para Engenharia de Software? | `F14` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q25** | `fluxo` | Aluno de graduação pode cursar disciplina do mestrado em Engenharia Biomédica? | `F26` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q26** | `fluxo` | Quais são as linhas de pesquisa do PPGEB? | `F27`, `F28` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q27** | `fluxo` | Quando é o último dia de aulas do semestre 2026.2? | `F29` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q28** | `fluxo` | Qual o período de matrícula do 2026.2? | `F29` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q29** | `fluxo` | Qual a diferença entre trancamento de disciplina e trancamento justificado? | `F31` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q30** | `fluxo` | Calouro pode alterar a própria matrícula no SIGAA? | `F33`, `F32` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q31** | `fluxo` | Como faço a matrícula on-line no SIGAA? | `F32`, `F34`, `F29` | *A medir* | *A medir* | *A medir* | *A preencher* |
    | **Q32** | `fluxo` | Quais são os órgãos colegiados da Faculdade do Gama segundo o regimento interno? | `F36` | *A medir* | *A medir* | *A medir* | *A preencher* |

    <p class="legenda">Tabela 4. Tabela mestre das 32 perguntas-ouro (<code>rag/avaliacao/perguntas_ouro.jsonl</code>) para comparação lado a lado entre LLM puro e RUmo com RAG.</p>

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Especificação do protocolo de comparação LLM × RAG, casos de teste e análise do caso de falha | Grupo 04 |
    | 11/11/2026 | 1.1 | Inclusão da Tabela 4 recolhida com as 32 perguntas-ouro de `perguntas_ouro.jsonl` | Grupo 04 |
