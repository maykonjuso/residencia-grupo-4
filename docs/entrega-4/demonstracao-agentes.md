# Demonstração colaborativa dos agentes

Esta página apresenta a execução real do fluxo multiagente via linha de comando (`python -m rumo_rag ... --agentes --trace`), evidenciando a colaboração entre especialistas, o paralelismo, a auditoria factual do `AgenteValidador` com devolução ao `Sintetizador` e a degradação elegante em falha.

---

## 1. Como executar o fluxo multiagente na CLI

Os comandos abaixo reproduzem todos os cenários da Entrega 4 a partir do diretório `rag/`:

```bash
cd rag

# 1. Execução colaborativa completa (com rastreamento --trace)
python -m rumo_rag "O que tem no almoço e quais os pré-requisitos de Testes de Software?" --agentes --trace

# 2. Execução rápida sem GPU / LLM (modo extrativo, apenas índice local + BM25/BGE-M3)
python -m rumo_rag "O que tem no almoço e quais os pré-requisitos de Testes de Software?" --agentes --trace --backend extrativo

# 3. Teste de resiliência (derruba propositalmente um agente especialista)
python -m rumo_rag "O que tem no almoço e quais os pré-requisitos de Testes de Software?" --agentes --trace --backend extrativo --falhar-agente ru
```

---

## 2. Caso 1 · Colaboração paralela em pergunta composta (`RU` + `Fluxo`)

No comando real com `--backend extrativo` (índice híbrido `BM25 + BAAI/bge-m3` no ChromaDB), a pergunta composta é decomposta em duas subconsultas atômicas, roteada para os especialistas `Agente RU` e `Agente Fluxo`, executada em paralelo e aprovada pelo `Agente Validador`:

```text
Pergunta: O que tem no almoço e quais os pré-requisitos de Testes de Software?

=== [TRACE · Orquestrador Multiagentes] ===
1. Classificação/Decomposição: composta=True (p=0.0, limiar=0.39, 1.915s)
   - Subpergunta 1: O que tem no almoço
   - Subpergunta 2: quais os pré-requisitos de Testes de Software
2. Roteamento (2 execução(ões)):
   - "O que tem no almoço" -> ru
   - "quais os pré-requisitos de Testes de Software" -> fluxo
3. Execução em paralelo: tempo_total=3.683s | soma_individual=7.271s | ganho=3.588s
   - [Agente RU] 3.596s · OK (5 trechos)
   - [Agente Fluxo] 3.675s · OK (5 trechos)
4. Validador factual:
   - ru: APROVADO
   - fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=False
===========================================

--- Parte 1 · Agente RU ---
Subpergunta: O que tem no almoço
Trechos recuperados (índices locais):
  [1] F08-0007 · Cardápio semanal do RU Gama — 02/11 a 08/11/2026 · p.2 · sim 0.5987
  [2] F09-0006 · Cardápio semanal do RU Gama — 09/11 a 15/11/2026 · p.2 · sim 0.5952
  [3] F09-0009 · Cardápio semanal do RU Gama — 09/11 a 15/11/2026 · p.2 · sim 0.6007
  [4] F08-0005 · Cardápio semanal do RU Gama — 02/11 a 08/11/2026 · p.2 · sim 0.6029
  [5] F09-0005 · Cardápio semanal do RU Gama — 09/11 a 15/11/2026 · p.2 · sim 0.591

Resposta (extrativo):
- ## Almoço · quarta-feira 04/11/2026 [1]
- Cardápio do RU Gama (FCTE) — Almoço de quarta-feira, 04/11/2026: [1]
- ## Almoço · terça-feira 10/11/2026 [2]
- Cardápio do RU Gama (FCTE) — Almoço de terça-feira, 10/11/2026: [2]

Fontes citadas:
  [1] F08 · Cardápio semanal do RU Gama — 02/11 a 08/11/2026 · p.2 · https://ru.unb.br/wp-content/uploads/2026/10/Gama-Semana-03-02-11-a-08-11-1.pdf
  [2] F09 · Cardápio semanal do RU Gama — 09/11 a 15/11/2026 · p.2 · https://ru.unb.br/wp-content/uploads/2026/11/Gama-Semana-04-09-11-a-15-11.pdf

--- Parte 2 · Agente Fluxo ---
Subpergunta: quais os pré-requisitos de Testes de Software
Trechos recuperados (índices locais):
  [1] F16-0011 · Fluxograma de Engenharia de Software (235 créditos) — transc · p.1 · sim 0.6572
  [2] F16-0012 · Fluxograma de Engenharia de Software (235 créditos) — transc · p.1 · sim 0.6567
  [3] F15-0001 · Engenharia de Software — matriz curricular e créditos (págin · p.1 · sim 0.563
  [4] F16-0013 · Fluxograma de Engenharia de Software (235 créditos) — transc · p.1 · sim 0.6299
  [5] F16-0000 · Fluxograma de Engenharia de Software (235 créditos) — transc · p.1 · sim 0.5373

Resposta (extrativo):
- ## Pré-requisitos de cada disciplina de Engenharia de Software (lidos das setas do fluxograma) [1]
- - Para cursar Testes de Software (FGA0314), é preciso ter cursado antes: Requisitos de Software (FGA0313) (seta cheia); [1]
- - Para cursar Requisitos de Software (FGA0313), é preciso ter cursado antes: Métodos de Desenvolvimento de Software (FGA0312). [1]
- o fluxograma também liga Métodos de Desenvolvimento de Software (FGA0312) a Testes de Software por seta tracejada. [1]

Fontes citadas:
  [1] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição · p.1 · https://software.unb.br/wp-content/uploads/2026/02/grade_curricular_esw.jpg

(paralelo 3.683s vs soma individual 7.271s · decomposição 1.915s)
```

### Evidências verificadas no Caso 1

A **Tabela 1** relaciona cada critério de aceite da Entrega 4 à evidência concreta observada na saída acima.

| Critério verificado | Evidência no trace e na saída |
|---|---|
| **Subperguntas decompostas** | `Subpergunta 1: O que tem no almoço` (`-> ru`) e `Subpergunta 2: quais os pré-requisitos de Testes de Software` (`-> fluxo`) |
| **Paralelismo real** | `tempo_total=3.683s` < `soma_individual=7.271s` (**ganho de `3.588s`** sobre os agentes `3.596s` + `3.675s`) |
| **Isolamento contratual de `[n]`** | Parte 1 (`Agente RU`) usa `[1]`/`[2]` para `F08`/`F09`; Parte 2 (`Agente Fluxo`) reinicia `[1]` para `F16` sem misturar índices |
| **Validação factual** | Etapa 4 registra `ru: APROVADO` e `fluxo: APROVADO` |

<p class="legenda">Tabela 1. Critérios verificados no Caso 1.</p>

---

## 3. Caso 2 · Atuação do `Agente Validador` e devolução ao `Sintetizador`

Para assegurar aderência estrita às regras **RN-02** e **RN-03**, o fluxo multiagente prevê um ciclo corretivo automático sempre que um especialista retorna dado sem respaldo documental ou omite citações `[n]`.

No cenário reproduzido na suíte automatizada (`rag/testes/test_orquestrador.py::test_validador_reprova_valor_inventado_e_devolve_ao_sintetizador`):

1. **Resposta inicial reprovada:** o `Agente RU` devolve `"O almoço custa R$ 99,90 e tem frango grelhado [1]."`, onde `R$ 99,90` não consta em nenhum trecho recuperado (`F09-0001`).
2. **Detecção pelo `Agente Validador`:** `AgenteValidador.validar()` identifica `valores_sem_fonte = ["R$ 99,90"]` e emite `ResultadoValidacao(aprovado=False, acao_recomendada="devolver_ao_sintetizador")`.
3. **Devolução e reparo no `Sintetizador`:** `Sintetizador.processar_devolucao()` substitui a geração alucinada por saída determinística extrativa (`acao="fallback_extrativo"`) extraída literalmente dos trechos validados.
4. **Revalidação e registro no trace:** o `Agente Validador` reavalia a resposta reparada (`aprovado_apos_devolucao=True`) antes de incluí-la na composição final, eliminando `"R$ 99,90"` sem intervenção manual.

---

## 4. Caso 3 · Degradação elegante (`--falhar-agente ru`)

Quando um especialista falha por indisponibilidade de serviço, erro de rede ou queda simulada pela flag `--falhar-agente ru`, o `Orquestrador` isola a exceção dentro do *worker* paralelo, mantém a execução dos demais agentes e sinaliza claramente o que faltou ao estudante:

```text
=== [TRACE · Orquestrador Multiagentes] ===
1. Classificação/Decomposição: composta=True (p=0.0, limiar=0.39, 1.885s)
   - Subpergunta 1: O que tem no almoço
   - Subpergunta 2: quais os pré-requisitos de Testes de Software
2. Roteamento (2 execução(ões)):
   - "O que tem no almoço" -> ru
   - "quais os pré-requisitos de Testes de Software" -> fluxo
3. Execução em paralelo: tempo_total=1.798s | soma_individual=1.797s | ganho=0.0s
   - [Agente RU] 0.0s · ERRO (RuntimeError: Falha simulada no agente 'ru')
   - [Agente Fluxo] 1.797s · OK (5 trechos)
4. Validador factual:
   - ru: ignorado (agente falhou) (Agente indisponível: RuntimeError: Falha simulada no agente 'ru')
   - fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=True
===========================================

--- Parte 1 · Agente RU ---
Subpergunta: O que tem no almoço
⚠ Falha no agente: RuntimeError: Falha simulada no agente 'ru'

--- Parte 2 · Agente Fluxo ---
Subpergunta: quais os pré-requisitos de Testes de Software
...
Fontes citadas:
  [1] F16 · Fluxograma de Engenharia de Software (235 créditos) — transcrição · p.1 · https://software.unb.br/wp-content/uploads/2026/02/grade_curricular_esw.jpg

⚠ Aviso (Agente RU): não foi possível obter esta parte da resposta (RuntimeError: Falha simulada no agente 'ru').
(paralelo 1.798s vs soma individual 1.797s · decomposição 1.885s)
```

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 16/11/2026 | 1.0 | Registro das demonstrações reais da Entrega 4 (paralelismo, validador + sintetizador e degradação elegante) | Grupo 04 |
