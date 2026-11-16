# Demonstração Executada

Esta página registra a execução real do protótipo multiagente por linha de comando (`--agentes --trace`), evidenciando o paralelismo entre especialistas, o isolamento contratual dos índices `[n]`, a devolução do validador ao sintetizador, a degradação graciosa em falha simulada e o fallback neural de roteamento.

!!! warning "Execução com backend extrativo (aguardando #41, #42 e #43)"
    As execuções abaixo foram realizadas com `--backend extrativo` e modelos locais (`HF_HUB_OFFLINE=1`) para validar a arquitetura do `Orquestrador`, do `AgenteValidador` e do `Sintetizador` de forma determinística. A demonstração de ponta a ponta com os prompts especializados e geração LLM final depende da conclusão das issues **#41**, **#42** e **#43** (`[a preencher]`).

---

## Caso 1 — Pergunta composta em paralelo (`ru` + `fluxo`)

Comando executado na raiz de `rag/`:

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo
```

Os cinco estágios registrados pelo `--trace` estão reproduzidos abaixo:

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

A **Tabela 1** resume as métricas e fontes verificadas nos dois blocos compostos pelo `Sintetizador`.

| Aspecto verificado | Valor observado | Critério de aceite atendido |
|---|---|---|
| **Decomposição em 2 subperguntas** | `"O que tem no almoço"` + `"quais os pré-requisitos de Testes de Software"` | Separação de dois eixos distintos na mesma consulta |
| **Prova de paralelismo** | `tempo_total = 3.683s` vs. `soma_individual = 7.271s` (`ganho = 3.588s`) | Tempo total significativamente menor que a soma individual (`3.596s + 3.675s`) |
| **Isolamento de citações `[n]`** | Parte 1 (`Agente RU`) citou `[1] F08`, `[2] F09`; Parte 2 (`Agente Fluxo`) citou `[1] F16` (`FGA0314`, `FGA0313`, `FGA0312`) | Ambas as partes preservam contagem independente iniciada em `[1]` |
| **Validação factual** | `ru: APROVADO, fluxo: APROVADO` | Nenhuma parte apresentou valores sem fonte ou ausência de citação |

<p class="legenda">Tabela 1. Métricas e evidências obtidas no Caso 1 (execução paralela sem falhas).</p>

---

## Caso 2 — Validador reprova alucinação e devolve ao Sintetizador

O fluxo de retorno entre `AgenteValidador` e `Sintetizador` é exercitado pelo teste automatizado `test_validador_reprova_valor_inventado_e_devolve_ao_sintetizador` em `rag/testes/test_orquestrador.py`:

1. Quando `AgenteValidador.validar(item)` detecta `geracao.valores_sem_fonte` ou `geracao.resposta_sem_citacao`, ele reprova o item e define `acao_recomendada = "devolver_ao_sintetizador"`.
2. O `Orquestrador` encaminha o item reprovado a `Sintetizador.processar_devolucao(item, validacao, backend)`.
3. Caso o backend original não seja `"extrativo"` e haja trechos recuperados, o sintetizador força uma regeneração segura via `geracao.gerar(..., backend="extrativo")`; na ausência de trechos ou persistindo bloqueio, devolve `RECUSA` ou acrescenta `[Aviso do Agente Validador: ...]`.

!!! info "Trace generativo completo de devolução"
    O registro de trace ao vivo para reprovação em geração LLM com os agentes especializados das issues `#41`–`#43` será anexado nesta seção após a integração dos novos prompts (`[a preencher]`).

---

## Caso 3 — Degradação graciosa com falha simulada (`--falhar-agente ru`)

Comando executado para validar o terceiro critério de aceite (derrubada proposital de um agente):

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo --falhar-agente ru
```

Trace observado:

```text
3. Execução em paralelo: tempo_total=1.798s | soma_individual=1.797s | ganho=0.0s
   - [Agente RU] 0.0s · ERRO (RuntimeError: Falha simulada no agente 'ru')
   - [Agente Fluxo] 1.797s · OK (5 trechos)
4. Validador factual: ru: ignorado (agente falhou) ..., fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=True
```

Trecho de aviso emitido pelo `Sintetizador` na parte indisponível, enquanto o bloco do `Agente Fluxo` foi entregue normalmente com `[1] F16`:

```text
⚠ Aviso (Agente RU): não foi possível obter esta parte da resposta (RuntimeError: Falha simulada no agente 'ru').
```

---

## Caso 4 — Roteamento em linguagem natural via fallback `d1-omni-600M`

Para uma consulta sem palavras-chave léxicas explícitas (*"RU"*, *"almoço"*, *"jantar"*), a cascata ignora a ausência de match no Regex e aciona `classificar_dominio_d1` (`limiar_confianca = 0.60`):

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "Onde vejo se a comida de hoje tem derivados de leite?" \
  --agentes --trace --backend extrativo
```

Resultado observado no trace e na resposta:

```text
2. Roteamento (1 execução(ões)):
   - "Onde vejo se a comida de hoje tem derivados de leite?" -> ru
3. [Agente RU] 3.929s · OK (5 trechos)
4. Validador factual: ru: APROVADO
```

A resposta recuperou os trechos de `F08`/`F09` contendo informações sobre bebidas e ingredientes (*`Leite integral ou Bebida de soja`*).

---

## Caso 5 — Demonstração final com agentes especializados (`#41`, `#42` e `#43`)

| Campo | Conteúdo esperado após `#41`, `#42` e `#43` |
|---|---|
| Comando com backend generativo | `[a preencher]` |
| Resposta final gerada pelos agentes especializados | `[a preencher]` |
| Evidência de validação semântica ampliada (`#43`) | `[a preencher]` |

<p class="legenda">Tabela 2. Campos reservados para a demonstração final após a implementação das issues #41, #42 e #43.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Registro inicial dos traces e simulações de falha multiagente | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Renomeação para `demonstracao.md`, remoção de lacunas não observadas e inclusão de `[a preencher]` para `#41`–`#43` | @maykonjuso |
