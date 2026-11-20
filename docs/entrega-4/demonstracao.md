# Demonstração Executada

Esta página registra execuções reais do protótipo multiagente via terminal, comprovando a execução em paralelo entre especialistas, o isolamento das citações por assunto, a correção automática quando o validador reprova um dado, a entrega parcial quando um agente falha e o encaminhamento em linguagem natural.

!!! info "Execuções reproduzíveis e evidência generativa"
    Os Casos 1, 3 e 4 abaixo foram executados no modo extrativo (`--backend extrativo`) com modelos locais offline (`HF_HUB_OFFLINE=1`) para validação determinística do roteamento, paralelismo e degradação. O Caso 2 e o Caso 5 registram o comportamento atual do **Agente Validador ativo** (`#43`) e a execução real com modelo generativo (`qwen2.5:7b` via Ollama) após o fechamento de `#40`–`#43`.

---

## Caso 1 — Pergunta composta executada em paralelo (RU e Fluxo)

Comando executado no terminal dentro da pasta `rag/`:

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo
```

Saída registrada pelo rastreamento passo a passo:

```text
1. Classificação/Decomposição: composta=True (p=0.0, limiar=0.39, 1.915s)
   - Subpergunta 1: O que tem no almoço
   - Subpergunta 2: quais os pré-requisitos de Testes de Software
2. Roteamento (2 execução(ões)):
   - "O que tem no almoço" -> ru
   - "quais os pré-requisitos de Testes de Software" -> fluxo
3. Execução em paralelo: tempo_total=3.683s | soma_individual=7.271s | ganho=3.588s
   - [Agente RU] 3.596s · OK (5 trechos)
   - [Agente Fluxo] 3.675s · OK (5 trechos)
4. Validador factual: ru: APROVADO, fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=False
```

### Evidências observadas na resposta final

A **Tabela 1** traduz as métricas obtidas e identifica os documentos oficiais citados nos dois blocos entregues ao estudante.

| Critério verificado | Resultado observado na execução | O que isso comprova |
|---|---|---|
| **Divisão da pergunta composta** | Separou *"O que tem no almoço"* e *"quais os pré-requisitos de Testes de Software"* em dois atendimentos | Identificou corretamente dois assuntos independentes na mesma consulta |
| **Paralelismo real** | Tempo total de `3,683 s` contra soma individual de `7,271 s` (`3,596 s + 3,675 s`, economia de `3,588 s`) | Os dois especialistas trabalharam ao mesmo tempo, reduzindo quase pela metade o tempo total |
| **Fontes separadas por assunto** | A parte do RU citou os documentos *Cardápio semanal do RU Gama — 02/11 a 08/11/2026* e *09/11 a 15/11/2026*; a parte de Fluxo citou o documento *Fluxograma de Engenharia de Software (235 créditos) — transcrição* | Cada assunto manteve sua própria numeração iniciada em 1 e sua própria lista de fontes, sem misturar referências |
| **Validação factual** | Ambas as partes foram aprovadas pelo Agente Validador | Nenhuma resposta trouxe valores sem respaldo ou deixou de citar a fonte oficial |

<p class="legenda">Tabela 1. Síntese das evidências obtidas no Caso 1 durante execução paralela sem falhas.</p>

---

## Caso 2 — Validador reprova informação sem lastro e devolve ao Sintetizador (máx. 1 retentativa)

O retorno ativo entre o **Agente Validador** e o **Sintetizador** é comprovado pelas suítes automatizadas `rag/testes/test_validador.py` e `rag/testes/test_orquestrador.py` e observado ao vivo na execução generativa do **Caso 5**:

1. Quando o Agente Validador identifica algum valor numérico, código ou data sem respaldo nos trechos recuperados, ou percebe que a resposta omitiu citações `[n]`, ele emite `REPROVADO` com os motivos explícitos e devolve o bloco ao Sintetizador.
2. Ao receber a devolução, o Sintetizador dispara **no máximo 1 retentativa** com feedback dos motivos da reprovação (no mesmo backend configurado ou reexecutando o agente), exigindo citações explícitas e remoção de dados sem lastro.
3. Se a segunda tentativa continuar reprovada (ou não houver trechos suficientes), o sistema **descarta a resposta ruim** e aplica a frase padrão de recusa (`"Não encontrei essa informação nas fontes da base."`), nunca entregando alucinação ao estudante.

---

## Caso 3 — Degradação graciosa diante da queda simulada de um agente

Para testar se a resposta saudável continua sendo entregue quando um especialista falha, o comando abaixo simula uma queda intencional no agente do Restaurante Universitário (`--falhar-agente ru`):

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo --falhar-agente ru
```

Saída registrada no terminal:

```text
3. Execução em paralelo: tempo_total=1.798s | soma_individual=1.797s | ganho=0.0s
   - [Agente RU] 0.0s · ERRO (RuntimeError: Falha simulada no agente 'ru')
   - [Agente Fluxo] 1.797s · OK (5 trechos)
4. Validador factual: ru: ignorado (agente falhou) ..., fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=True
```

Enquanto a parte sobre *Testes de Software* foi respondida e validada normalmente citando o *Fluxograma de Engenharia de Software (235 créditos) — transcrição*, o bloco do Restaurante Universitário exibiu o aviso claro abaixo:

```text
⚠ Aviso (Agente RU): não foi possível obter esta parte da resposta (RuntimeError: Falha simulada no agente 'ru').
```

---

## Caso 4 — Roteamento em linguagem natural sem palavras-chave óbvias

Quando a pergunta não contém termos literais como *"RU"*, *"almoço"* ou *"jantar"*, as regras léxicas não conseguem decidir sozinhas e o roteador aciona o classificador neural de domínio (`limiar de confiança = 0,60`):

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "Onde vejo se a comida de hoje tem derivados de leite?" \
  --agentes --trace --backend extrativo
```

Saída registrada pelo rastreamento:

```text
2. Roteamento (1 execução(ões)):
   - "Onde vejo se a comida de hoje tem derivados de leite?" -> ru
3. [Agente RU] 3.929s · OK (5 trechos)
4. Validador factual: ru: APROVADO
```

O sistema encaminhou a dúvida corretamente para o **Agente do RU**, recuperou trechos dos documentos de cardápio semanal do campus Gama (*Cardápio semanal do RU Gama — 02/11 a 08/11/2026* e *09/11 a 15/11/2026*) contendo informações sobre bebidas e ingredientes (*`Leite integral ou Bebida de soja`*) e teve a resposta aprovada pelo validador.

---

## Caso 5 — Demonstração generativa ao vivo com reprovação e reparo (`qwen2.5:7b` via Ollama)

Execução real em terminal com o modelo generativo local (`--backend ollama`) e busca híbrida:

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend ollama
```

Saída registrada pelo rastreamento passo a passo:

```text
1. Classificação/Decomposição: composta=True (p=0.5073, limiar=0.39, 8.723s)
   - Subpergunta 1: O que tem no almoço?
   - Subpergunta 2: Quais são os pré-requisitos de Testes de Software?
2. Roteamento (2 execução(ões)):
   - "O que tem no almoço?" -> ru
   - "Quais são os pré-requisitos de Testes de Software?" -> fluxo
3. Execução em paralelo: tempo_total=81.502s | soma_individual=142.795s | ganho=61.293s
   - [Agente RU] 61.296s · OK (5 trechos)
   - [Agente Fluxo] 81.499s · OK (5 trechos)
4. Validador factual:
   - ru: 1ª avaliação=REPROVADO (Resposta afirmativa sem citação [n] (RN-02)) -> pós-reparo=APROVADO
   - fluxo: APROVADO
   -> Devolvido ao Sintetizador (Agente RU, tentativa 1/1): ação=retentativa_com_feedback · pós-reparo=APROVADO
      motivos: Resposta afirmativa sem citação [n] (RN-02)
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=False
6. Interações registradas no Trace (7 Mensagem -> Resposta)
```

Na primeira tentativa, o **Agente do RU** listou o cardápio sem colchetes `[n]`; o **Agente Validador** reprovou por violação da regra RN-02, devolveu ao **Sintetizador**, e a retentativa com feedback no próprio Ollama devolveu as opções de cardápio com as citações `[1]`, `[3]`, `[4]` e `[5]` dos documentos oficiais do RU Gama, aprovada na revalidação.

---

## Caso 6 — Avaliação fim-a-fim nas 12 perguntas múltiplas (`qwen2.5:7b` via Ollama)

O conjunto completo de **12 perguntas múltiplas** (`rag/avaliacao/perguntas/perguntas_roteamento_multiplas.jsonl`, incluindo consultas duplas, triplas e quádruplas) foi executado ponta a ponta na arquitetura atual (busca híbrida + `ollama:qwen2.5:7b` + **Agente Validador** ativo). Os dados brutos e o relatório detalhado estão registrados em `rag/avaliacao/resultados/relatorio_orquestrador_multiplas.md`. A **Tabela 2** apresenta o desdobramento, os tempos e o desfecho de cada consulta, e a **Tabela 3** logo abaixo expõe todas as respostas completas geradas pela LLM com suas respectivas fontes citadas.

| ID | Pergunta | Subperguntas | Rotas obtidas | Paralelo (s) | Soma individual (s) | Ganho (s) | Validação / Desfecho |
|---|---|---:|---|---:|---:|---:|---|
| **M01** | O que tem no almoço de quarta-feira e quais são os pré-requisitos de Testes de Software? | `2/2` | `ru`, `fluxo` | `23,89` | `37,75` | `13,85` | Aprovado (`2/2` com citação) |
| **M02** | Qual a proteína servida hoje ao meio-dia no bandejão e o que preciso ter aprovado antes de pegar Cálculo 2? | `2/2` | `ru`, `fluxo` | `2,84` | `3,69` | `0,85` | RU recusou (*"hoje"* sem data); Fluxo respondeu com citação |
| **M03** | Quem tem direito a isenção na refeição e até que horas servem o jantar no Gama? | `2/2` | `ru`, `ru` | `4,66` | `7,62` | `2,95` | Aprovado (`2/2` com citação) |
| **M04** | Quantas horas de estágio são exigidas em Engenharia de Energia e como um aluno da graduação pede para cursar matéria isolada na pós? | `2/2` | `fluxo`, `fluxo` | `23,71` | `29,93` | `6,22` | 1 devolução por valor sem fonte (`14 créditos`) → recusa final honesta |
| **M05** | Onde vejo se a comida de hoje tem derivados de leite e qual o prazo máximo para desistir de uma turma no semestre sem reprovar? | `2/2` | `ru`, `fluxo` | `2,07` | `3,19` | `1,12` | Ambos recusaram honestamente por falta de base/data |
| **M06** | Qual a carga horária mínima por período em Software e quanto paga quem não recebe bolsa de alimentação? | `2/2` | `fluxo`, `ru` | `20,00` | `21,12` | `1,12` | Ambos recusaram honestamente sem base exata |
| **M07** | Quanto custa o desjejum para Grupo II, quantos créditos exige Engenharia Aeroespacial e abre aos sábados para comer? | `3/3` | `ru`, `fluxo`, `ru` | `39,23` | `88,53` | `49,30` | Fluxo devolvido (`2510 horas` sem fonte) → corrigido (`251 créditos`); `3/3` aprovadas |
| **M08** | Sou estudante da FCTE: quantos créditos exige Engenharia de Software e quais documentos apresento na catraca para comer? | `2/2` | `fluxo`, `ru` | `25,71` | `41,80` | `16,09` | Aprovado (`2/2` com citação) |
| **M09** | Até que horas servem o almoço no RU Gama? Quais os pré-requisitos de Estruturas de Dados? E quantas horas de estágio exige Engenharia Eletrônica? | `3/3` | `ru`, `fluxo`, `fluxo` | `21,19` | `42,43` | `21,24` | Aprovado (`3/3` com citação) |
| **M10** | Qual o horário do café da manhã no RU, quanto custa o jantar para o Grupo III e quem tem direito à isenção nas refeições? | `3/3` | `ru`, `ru`, `ru` | `17,53` | `34,65` | `17,12` | Aprovado (`3/3` com citação) |
| **M11** | Quanto custa o almoço no RU para Grupo III? O RU Gama abre aos sábados? Quais os pré-requisitos de Cálculo 2? E qual a carga horária mínima por semestre em Engenharia de Software? | `4/4` | `ru`, `ru`, `fluxo`, `fluxo` | `36,14` | `84,75` | `48,61` | 3 partes respondidas com citação; 4ª parte recusou honestamente |
| **M12** | Sou estudante da FCTE: quantas horas de estágio exige Engenharia de Energia, quantos créditos exige Engenharia Automotiva, quais documentos levo na catraca do RU e como comprovo direito ao auxílio alimentação? | `4/4` | `fluxo`, `fluxo`, `ru`, `ru` | `47,53` | `118,68` | `71,15` | Aprovado (`4/4` com citação) |

<p class="legenda">Tabela 2. Resultados ponta a ponta nas 12 perguntas múltiplas (duplas, triplas e quádruplas) com busca híbrida e modelo generativo local (qwen2.5:7b).</p>

- **Decomposição e roteamento:** **`12/12` (`100%`)** das consultas foram quebradas no número exato de subperguntas esperadas (`31/31` subperguntas) e roteadas na ordem e nos domínios corretos.
- **Paralelismo comprovado:** redução total de **`249,63 s`** (`264,50 s` em paralelo contra `514,13 s` individuais, economia média de **`48,6%`** na execução dos agentes, escalando para 3 e 4 *workers* simultâneos).
- **Fidelidade e escopo:** **`31/31`** partes aprovadas no desfecho final pelo **Agente Validador** (`0` erros de execução). Nas 2 reprovações iniciais (`M04` e `M07`), o fluxo ativo devolveu ao **Sintetizador**: em `M07`, a retentativa corrigiu o valor para `251 créditos`; em `M04`, como o valor sem respaldo persistiu na 2ª tentativa, foi aplicada a recusa final honesta.

??? info "Tabela 3 · Respostas completas da LLM (`qwen2.5:7b`) nas 12 perguntas múltiplas — M01 a M12 (clique para expandir)"

    As **31 respostas parciais** abaixo foram extraídas diretamente de `rag/avaliacao/resultados/resultado_orquestrador_multiplas.json` (com `M07` já corrigida após devolução do **Agente Validador** e `M04` parte 1 em recusa final honesta após 2ª reprovação). Na exportação em PDF A4, este bloco é expandido automaticamente.

    | ID | Agente e subpergunta | Resposta da LLM (`qwen2.5:7b`) | Fontes citadas |
    |:---:|---|---|---|
    | **M01** (1/2) | **Agente RU:** O que tem no almoço de quarta-feira? | No almoço de quarta-feira:<br><br>- Salada 1: Mix de folhas [1]<br>- Salada 2: Abóbora ralada [1]<br>- Molho para salada: Salsa [1]<br>- Prato principal padrão: Strogonoff de frango [1]<br>- Prato principal ovolactovegetariano: Iscas de soja ao sugo gratinadas [1]<br>- Prato principal vegetariano estrito: Polpetone de quinoa [1]<br>- Guarnição: Batata sauté [1]<br>- Acompanhamentos: Arroz branco e integral Feijão preto [1]<br>- Sobremesa: Mexerica [1]<br>- Bebida (refresco de): Manga [1] | [1] F08 · Cardápio semanal do RU Gama — 02/11 a 08/11/2026 (p. 2) |
    | **M01** (2/2) | **Agente Fluxo:** Quais são os pré-requisitos de Testes de Software? | Para cursar Testes de Software (FGA0314), é preciso ter cursado antes Requisitos de Software (FGA0313) [2]. A seta tracejada no fluxograma também indica que Métodos de Desenvolvimento de Software (FGA0312) tem uma ligação com Testes de Software, mas não é um pré-requisito direto. [1] | [1] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição (p. 1)<br>[2] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição (p. 1) |
    | **M02** (1/2) | **Agente RU:** Qual a proteína servida hoje ao meio-dia no bandejão? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M02** (2/2) | **Agente Fluxo:** O que preciso ter aprovado antes de pegar Cálculo 2? | Para cursar Cálculo 2 (MAT0026), é necessário ter aprovado Cálculo 1 (MAT0025) [2]. | [2] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição (p. 1) |
    | **M03** (1/2) | **Agente RU:** Quem tem direito a isenção na refeição? | Estudantes do Grupo I têm direito ao subsídio integral das refeições, sendo que o acesso é garantido mediante comprovação de vínculo institucional ativo. [3][6] | [3] F04 · Valores das refeições e grupos de acesso (p. 1) |
    | **M03** (2/2) | **Agente RU:** Até que horas servem o jantar no Gama? | O jantar no RU Gama funciona até às 19h30 de segunda-feira a sexta-feira, exceto feriados. [4] | [4] F03 · Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) (p. 1) |
    | **M04** (1/2) | **Agente Fluxo:** Quanto tempo de estágio é exigido para a formatura em Engenharia de Energia? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M04** (2/2) | **Agente Fluxo:** Como um aluno da graduação pode pedir para cursar uma matéria isolada na pós-graduação? | De acordo com a Instrução Conjunta DEG/DPG no. 01/2020, o aluno de graduação deve seguir os seguintes passos:<br><br>1) Verificar a lista de oferta vigente do curso.<br>2) Verificar o período de matrícula de pós-graduação no calendário de matrícula.<br>3) Solicitar a matrícula da disciplina do PPGEB ao coordenador de seu curso de graduação. A solicitação deve conter: nome completo, número de matrícula, nome, código e turma da disciplina pretendida, nome do curso de graduação que cursa, e modalidade (ELETIVA ou OPTATIVA).<br>4) O coordenador do curso de graduação abrirá processo SEI com o requerimento. Para ELETIVA, pode ser aprovado pelo próprio coordenador; para OPTATIVA, será necessário aprovação do Colegiado do Curso de Graduação e do PPGEB.<br><br>[1] | [1] F26 · PPGEB (Mestrado em Engenharia Biomédica) — como aluno de graduação cursa disciplinas do mestrado (p. 1) |
    | **M05** (1/2) | **Agente RU:** onde vejo se a comida de hoje tem derivados de leite? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M05** (2/2) | **Agente Fluxo:** qual é o prazo máximo para desistir de uma turma no semestre sem reprovar? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M06** (1/2) | **Agente Fluxo:** Qual a carga horária mínima por período em Software? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M06** (2/2) | **Agente RU:** Quanto paga quem não recebe bolsa de alimentação? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M07** (1/3) | **Agente RU:** Quanto custa o desjejum para Grupo II? | O desjejum para Grupo II custa R$ 2,00. [1] | [1] F04 · Valores das refeições e grupos de acesso (p. 1) |
    | **M07** (2/3) | **Agente Fluxo:** Quantos créditos exige Engenharia Aeroespacial? | De acordo com o Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) [1], o curso exige no mínimo 251 créditos. | [1] F17 · Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) (p. 204) |
    | **M07** (3/3) | **Agente RU:** Abre aos sábados para comer no RU? | Não, o Restaurante Universitário do Campus Gama/FCTE não abre aos sábados para refeições. Segundo os horários informados [3], os serviços são oferecidos apenas de segunda à sexta-feira, exceto feriados. | [3] F03 · Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) (p. 1) |
    | **M08** (1/2) | **Agente Fluxo:** Quantos créditos exige Engenharia de Software? | Engenharia de Software exige 235 créditos para os estudantes que ingressaram após 2024/2 [2][3]. | [2] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição (p. 1)<br>[3] F15 · Engenharia de Software — matriz curricular e créditos (página do curso) (p. 1) |
    | **M08** (2/2) | **Agente RU:** Quais documentos apresento na catraca para comer no RU? | Para acessar o RU, você deve posicionar o QR Code da carteirinha estudantil digital sob o leitor da catraca. [1] | [1] F05 · Como acessar o RU (carteirinha digital, créditos e catraca) (p. 1) |
    | **M09** (1/3) | **Agente RU:** Até que horas servem o almoço no RU Gama? | O almoço no RU Gama funciona das 11h às 14h30 de segunda a sexta-feira, exceto feriados. [2][3] | [2] F09 · Cardápio semanal do RU Gama — 09/11 a 15/11/2026 (p. 2)<br>[3] F02 · Resolução DAC nº 002/2024 — Regimento de funcionamento do Restaurante Universitário (p. 4) |
    | **M09** (2/3) | **Agente Fluxo:** Quais os pré-requisitos de Estruturas de Dados? | Os pré-requisitos para Estruturas de Dados 1 (FGA0146) é Algoritmos e Programação de Computadores (CIC0004). [2] | [2] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição (p. 1) |
    | **M09** (3/3) | **Agente Fluxo:** Quantas horas de estágio exige Engenharia Eletrônica? | O estágio supervisionado no curso de Engenharia Eletrônica exige uma carga horária mínima de 210 horas. [1] | [1] F21 · Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) (p. 50) |
    | **M10** (1/3) | **Agente RU:** Qual o horário do café da manhã no RU? | O horário do café da manhã no RU Gama é de 07h00 às 09h30, funcionando todos os dias. [1][4] | [1] F02 · Resolução DAC nº 002/2024 — Regimento de funcionamento do Restaurante Universitário (p. 4)<br>[4] F02 · Resolução DAC nº 002/2024 — Regimento de funcionamento do Restaurante Universitário (p. 4) |
    | **M10** (2/3) | **Agente RU:** Quanto custa o jantar para o Grupo III? | O jantar para o Grupo III custa R$ 15,20. [1] | [1] F04 · Valores das refeições e grupos de acesso (p. 1) |
    | **M10** (3/3) | **Agente RU:** Quem tem direito à isenção nas refeições? | Estudantes do Grupo I têm direito ao subsídio integral das refeições, sendo que o acesso depende de comprovação de vínculo institucional ativo. [3][4] | [3] F04 · Valores das refeições e grupos de acesso (p. 1)<br>[4] F02 · Resolução DAC nº 002/2024 — Regimento de funcionamento do Restaurante Universitário (p. 3) |
    | **M11** (1/4) | **Agente RU:** Quanto custa o almoço no RU para Grupo III? | O almoço no RU para Grupo III custa R$ 15,20. [1] | [1] F04 · Valores das refeições e grupos de acesso (p. 1) |
    | **M11** (2/4) | **Agente RU:** O RU Gama abre aos sábados? | Não, o RU Gama não abre aos sábados. Segundo os trechos [1] e [2], os horários de funcionamento incluem apenas de segunda-feira a sexta-feira, exceto feriados. Não há menção a operação nos finais de semana. | [1] F03 · Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) (p. 1)<br>[2] F03 · Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) (p. 1) |
    | **M11** (3/4) | **Agente Fluxo:** Quais os pré-requisitos de Cálculo 2? | De acordo com o fluxograma [1], o pré-requisito para cursar Cálculo 2 (MAT0026) é ter concluído anteriormente Cálculo 1 (MAT0025). [1] | [1] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição (p. 1) |
    | **M11** (4/4) | **Agente Fluxo:** Qual a carga horária mínima por semestre em Engenharia de Software? | Não encontrei essa informação nas fontes da base. | — *(recusa honesta)* |
    | **M12** (1/4) | **Agente Fluxo:** Quantas horas de estágio exige Engenharia de Energia? | O curso de Engenharia de Energia exige uma carga horária mínima de 210 horas para o estágio obrigatório. [4][5] | [4] F23 · Matriz curricular de Engenharia de Energia (251 créditos) — transcrição (p. 1)<br>[5] F21 · Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) (p. 50) |
    | **M12** (2/4) | **Agente Fluxo:** Quanto crédito exige Engenharia Automotiva? | Engenharia Automotiva exige 215 créditos [1]. | [1] F20 · Engenharia Automotiva — informações gerais do curso (p. 1) |
    | **M12** (3/4) | **Agente RU:** Qual documento levo na catraca do RU? | Para acessar o RU, você deve apresentar o QR Code da carteirinha estudantil digital sob o leitor da catraca. [1] | [1] F05 · Como acessar o RU (carteirinha digital, créditos e catraca) (p. 1) |
    | **M12** (4/4) | **Agente RU:** Como comprovo direito ao auxílio alimentação? | Para comprovar o direito ao auxílio-alimentação, você deve:<br><br>1. Estar regularmente matriculado em um curso presencial de graduação ou pós-graduação stricto sensu na UnB.<br>2. Possuir avaliação socioeconômica analisada e homologada pela COAE/DDS (até 2026.1) ou registro atualizado no Cadastro Único do Governo Federal com faixa de renda até meio salário-mínimo por pessoa do grupo familiar.<br>3. Realizar a inscrição pelo SIGAA entre 03/08/2026 e 15/11/2026, atualizando as informações bancárias e pessoais necessárias.<br><br>[4][5] | [4] F06 · Programa Auxílio Alimentação — regras de uso (p. 1)<br>[5] F07 · Edital nº 24/2026 DDS/DAC — Auxílio Alimentação para estudantes em vulnerabilidade (p. 1) |

---

## Caso 7 — Consulta composta com cardápio semanal estruturado (alergênicos) e Fluxo

Com a integração do cardápio estruturado da semana corrente (`cardapio_semanal.json`, fonte `F56`) ao **Agente do RU** e do catálogo de 54 fontes oficiais, consultas sobre alergênicos passaram a ser respondidas diretamente a partir da semana vigente sem conflito com PDFs antigos no RAG:

```bash
cd rag
RUMO_BUSCA=bm25 RUMO_USAR_D1=0 ../.venv/bin/python -m rumo_rag perguntar \
  "Quais pratos do almoço de quarta-feira têm leite ou lactose e quais são os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo
```

Saída real registrada em terminal (modo leve compatível com deploy em nuvem):

```text
=== [TRACE · Orquestrador Multiagentes] ===
1. Classificação/Decomposição: composta=True (p=0.0, limiar=0.39, 0.0s)
   - Subpergunta 1: Quais pratos do almoço de quarta-feira têm leite ou lactose
   - Subpergunta 2: quais são os pré-requisitos de Testes de Software
2. Roteamento (2 execução(ões)):
   - "Quais pratos do almoço de quarta-feira têm leite ou lactose" -> ru
   - "quais são os pré-requisitos de Testes de Software" -> fluxo
3. Execução em paralelo: tempo_total=0.259s | soma_individual=0.265s | ganho=0.006s
   - [Agente RU] 0.007s · OK (1 trechos)
   - [Agente Fluxo] 0.258s · OK (5 trechos)
4. Validador factual:
   - ru: APROVADO
   - fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=False

--- Parte 1 · Agente RU ---
- Cardápio do RU Gama (FCTE) — Almoço de quarta-feira, 18/11/2026: [1]
- Prato principal (ovolacto): Risoto de ervilha com queijo [Alergênicos: Leite e derivados, Trigo/Glúten] [1]
Fonte: [1] F56 · Cardápio semanal do RU Gama (16/11 a 22/11/2026) · p. 2

--- Parte 2 · Agente Fluxo ---
- Para cursar Testes de Software (FGA0314), é preciso ter cursado antes: Requisitos de Software (FGA0313) (seta cheia); [1]
- Para cursar Requisitos de Software (FGA0313), é preciso ter cursado antes: Métodos de Desenvolvimento de Software (FGA0312). [1]
- o fluxograma também liga Métodos de Desenvolvimento de Software (FGA0312) a Testes de Software por seta tracejada. [1]
Fonte: [1] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição · p. 1
```

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Registro inicial dos traces e simulações de falha multiagente | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Renomeação para `demonstracao.md`, remoção de lacunas não observadas e inclusão de `[a preencher]` para `#41`–`#43` | @maykonjuso |
    | 1.2 | 16/11/2026 | @GabrielMacielBR | Substituição de códigos de fontes e símbolos internos por descrições dos documentos reais nas explicações e tabelas | @maykonjuso |
    | 1.3 | 18/11/2026 | @GabrielMacielBR | Atualização do Caso 2 para retentativa com feedback e inclusão do Caso 5 com execução real no Ollama (`qwen2.5:7b`) | — |
    | 1.4 | 18/11/2026 | @GabrielMacielBR | Adição do Caso 6 com os resultados da avaliação fim-a-fim nas 12 perguntas múltiplas (duplas, triplas e quádruplas) | — |
    | 1.5 | 20/11/2026 | @GabrielMacielBR | Inclusão da resposta final real de `M07` (pós-reparo do validador) e do Caso 7 com cardápio semanal estruturado e alergênicos (`F56`) | — |
    | 1.6 | 20/11/2026 | @GabrielMacielBR | Inclusão da Tabela 3 recolhível com as respostas completas da LLM (`qwen2.5:7b`) e fontes citadas nas 12 perguntas múltiplas (`M01`–`M12`) | — |
