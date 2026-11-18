# Comparação de Classificação e Roteamento do Orquestrador (Teste 1 vs. Teste 2)

- **Dataset:** `rag/avaliacao/perguntas/perguntas_roteamento_multiplas.jsonl` (8 perguntas múltiplas, 17 subperguntas esperadas)
- **Baseline:** Regex léxico (`agentes.rotear_subpergunta`)
- **Teste 1 (LLM Conjunto):** `ollama:qwen2.5:7b` (decompõe e rotula `eixo` no mesmo JSON)
- **Teste 2 (System-1):** `LiquidAI/d1-omni-600M` (limiar compostas `0.39`, confiança domínio `0.6`)

## 1. Roteamento por subpergunta (17 subperguntas canônicas)

| Método | Acertos exatos | Acurácia exata | Recall do domínio | Chamadas extras (`ambos`) | Latência média |
|---|---:|---:|---:|---:|---:|
| **Baseline · Regex** | 17/17 | 100.0% | 100.0% | 0 | 0.03 ms |
| **Teste 1 · LLM Conjunto** | 17/17 | 100.0% | 100.0% | 0 | 630.0 ms |
| **Teste 2 · d1-omni-600M** | 17/17 | 100.0% | 100.0% | 0 | 84.6 ms |

## 2. Decomposição e classificação nas 8 perguntas múltiplas

| Etapa / Método | Resultado nas 8 compostas | Observação |
|---|---|---|
| **Estágio 1 (`d1-omni-600M` >= 0.39)** | 7/8 detectadas (87.5%) | Latência média 92.9 ms |
| **Teste 1 (LLM Decomposição + Eixo conjunto)** | 8/8 com nº exato (100.0%) · 8/8 com rota fim-a-fim exata | Latência média 3486.7 ms |
| **Fallback sintático (`_decompor_fallback`)** | 7/8 com nº exato (87.5%) | Regra regex sem LLM |

## 3. Onde os métodos divergiram nas subperguntas

| ID | Subpergunta | Esperado | Regex | Teste 1 (LLM) | Teste 2 (`d1-omni`) |
|---|---|---:|---|---|---|
| — | Todos os métodos concordaram em 100% das subperguntas | — | — | — | — |

## 4. Detalhe da decomposição conjunta (Teste 1)

- **M01** (d1-omni p=0.465): `[ru]` O que tem no almoço de quarta-feira?; `[fluxo]` Quais são os pré-requisitos de Testes de Software?
- **M02** (d1-omni p=0.496): `[ru]` Qual a proteína servida hoje ao meio-dia no bandejão?; `[fluxo]` O que preciso ter aprovado antes de pegar Cálculo 2?
- **M03** (d1-omni p=0.445): `[ru]` Quem tem direito a isenção na refeição?; `[ru]` Até que horas servem o jantar no Gama?
- **M04** (d1-omni p=0.623): `[fluxo]` Quantas horas de estágio são exigidas em Engenharia de Energia?; `[fluxo]` Como um aluno da graduação pede para cursar matéria isolada na pós-graduação?
- **M05** (d1-omni p=0.550): `[ru]` Onde vejo se a comida de hoje tem derivados de leite?; `[fluxo]` Qual é o prazo máximo para desistir de uma turma no semestre sem reprovar?
- **M06** (d1-omni p=0.374): `[fluxo]` Qual a carga horária mínima por período em Software?; `[ru]` Quanto paga quem não recebe bolsa de alimentação?
- **M07** (d1-omni p=0.636): `[ru]` Quanto custa o desjejum para Grupo II?; `[fluxo]` Quantos créditos exige Engenharia Aeroespacial?; `[ru]` Abre aos sábados para comer?
- **M08** (d1-omni p=0.514): `[fluxo]` Em qual etapa escolho minha engenharia específica?; `[ru]` Quais documentos apresento na catraca para comer?
