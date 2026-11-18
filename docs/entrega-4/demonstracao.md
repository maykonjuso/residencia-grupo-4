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

O conjunto completo de **12 perguntas múltiplas** (`rag/avaliacao/perguntas/perguntas_roteamento_multiplas.jsonl`, incluindo consultas duplas, triplas e quádruplas) foi executado ponta a ponta na arquitetura atual (busca híbrida + `ollama:qwen2.5:7b` + **Agente Validador** ativo). Os dados brutos e o relatório detalhado estão registrados em `rag/avaliacao/resultados/relatorio_orquestrador_multiplas.md`. A **Tabela 2** apresenta cada consulta avaliada, o desdobramento obtido, os tempos de execução e o desfecho da validação.

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

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Registro inicial dos traces e simulações de falha multiagente | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Renomeação para `demonstracao.md`, remoção de lacunas não observadas e inclusão de `[a preencher]` para `#41`–`#43` | @maykonjuso |
    | 1.2 | 16/11/2026 | @GabrielMacielBR | Substituição de códigos de fontes e símbolos internos por descrições dos documentos reais nas explicações e tabelas | @maykonjuso |
    | 1.3 | 18/11/2026 | @GabrielMacielBR | Atualização do Caso 2 para retentativa com feedback e inclusão do Caso 5 com execução real no Ollama (`qwen2.5:7b`) | — |
    | 1.4 | 18/11/2026 | @GabrielMacielBR | Adição do Caso 6 com os resultados da avaliação fim-a-fim nas 12 perguntas múltiplas (duplas, triplas e quádruplas) | — |
