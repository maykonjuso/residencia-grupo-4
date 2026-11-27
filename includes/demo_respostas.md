
### D1 · Preço do almoço

```text
$ python -m rumo_rag perguntar "Quanto um estudante de graduação paga no almoço do RU?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F04-0002` | Valores das refeições e grupos de acesso | 1 | Valores das refeições e grupos > Grupo II | 0.700 |
| 2 | `F04-0004` | Valores das refeições e grupos de acesso | 1 | Valores das refeições e grupos > Grupo IV | 0.698 |
| 3 | `F03-0004` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Planaltina (FUP) | 0.587 |
| 4 | `F04-0005` | Valores das refeições e grupos de acesso | 1 | Valores das refeições e grupos > Restaurante Executivo | 0.654 |
| 5 | `F03-0002` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Ceilândia (FCTS) | 0.582 |

!!! quote "Resposta gerada (ollama)"
    [1] Estudantes de Graduação pague R$ 4,50 por almoço.

**Fontes citadas na resposta:**

- [1] **F04** · [Valores das refeições e grupos de acesso](https://ru.unb.br/precos-e-grupos/) · p. 1 · chunk `F04-0002`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 3.76 s · geração 2.38 s.</p>


### D2 · Cardápio do dia

```text
$ python -m rumo_rag perguntar "Qual é a opção vegetariana estrita do almoço de quarta-feira, 11/11/2026, no RU Gama?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F09-0007` | Cardápio semanal do RU Gama — 09/11 a 15/11/2026 | 2 | Almoço · quarta-feira 11/11/2026 | 0.711 |
| 2 | `F09-0002` | Cardápio semanal do RU Gama — 09/11 a 15/11/2026 | 1 | Café da manhã · quarta-feira 11/11/2026 | 0.706 |
| 3 | `F09-0012` | Cardápio semanal do RU Gama — 09/11 a 15/11/2026 | 3 | Jantar · quarta-feira 11/11/2026 | 0.697 |
| 4 | `F08-0007` | Cardápio semanal do RU Gama — 02/11 a 08/11/2026 | 2 | Almoço · quarta-feira 04/11/2026 | 0.681 |
| 5 | `F09-0006` | Cardápio semanal do RU Gama — 09/11 a 15/11/2026 | 2 | Almoço · terça-feira 10/11/2026 | 0.682 |

!!! quote "Resposta gerada (ollama)"
    [3] O prato principal vegetariano estrito para o almoço de quarta-feira, 11/11/2026 é Strogonoff vegetariano. [3]

**Fontes citadas na resposta:**

- [3] **F09** · [Cardápio semanal do RU Gama — 09/11 a 15/11/2026](https://ru.unb.br/wp-content/uploads/2026/11/Gama-Semana-04-09-11-a-15-11.pdf) · p. 3 · chunk `F09-0012`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.09 s · geração 1.18 s.</p>


### D3 · Gratuidade

```text
$ python -m rumo_rag perguntar "Quem tem direito a comer de graça no RU da UnB?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F01-0004` | Resolução do CAD nº 0037/2025 — grupos de usuários e valores das refeições do RU | 2 |  | 0.642 |
| 2 | `F01-0000` | Resolução do CAD nº 0037/2025 — grupos de usuários e valores das refeições do RU | 1 |  | 0.627 |
| 3 | `F01-0005` | Resolução do CAD nº 0037/2025 — grupos de usuários e valores das refeições do RU | 2 |  | 0.639 |
| 4 | `F05-0000` | Como acessar o RU (carteirinha digital, créditos e catraca) | 1 | Você é discente? Confira como acessar o RU UnB: | 0.595 |
| 5 | `F06-0000` | Programa Auxílio Alimentação — regras de uso | 1 | Programa Auxílio Alimentação | 0.689 |

!!! quote "Resposta gerada (ollama)"
    Estudantes de graduação e pós-graduação (stricto sensu) presenciais em situação de vulnerabilidade socioeconômica têm direito a comer de graça no RU da UnB. [5]

**Fontes citadas na resposta:**

- [5] **F06** · [Programa Auxílio Alimentação — regras de uso](https://ru.unb.br/programa-auxilio-alimentacao/) · p. 1 · chunk `F06-0000`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.11 s · geração 1.29 s.</p>


### D4 · Pré-requisitos

```text
$ python -m rumo_rag perguntar "Quais disciplinas preciso ter feito antes de cursar Testes de Software?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F16-0012` | Fluxograma de Engenharia de Software (235 créditos) — transcrição | 1 | itos de cada disciplina de Engenharia de Software (lidos das | 0.678 |
| 2 | `F16-0011` | Fluxograma de Engenharia de Software (235 créditos) — transcrição | 1 | itos de cada disciplina de Engenharia de Software (lidos das | 0.667 |
| 3 | `F16-0013` | Fluxograma de Engenharia de Software (235 créditos) — transcrição | 1 | itos de cada disciplina de Engenharia de Software (lidos das | 0.659 |
| 4 | `F15-0000` | Engenharia de Software — matriz curricular e créditos (página do curso) | 1 |  | 0.609 |
| 5 | `F15-0001` | Engenharia de Software — matriz curricular e créditos (página do curso) | 1 |  | 0.601 |

!!! quote "Resposta gerada (ollama)"
    Registro histórico da execução de 16/11/2026, anterior ao PR #88: a resposta tratou Métodos de Desenvolvimento de Software como obrigatório. A regra atual do grafo é o pré-requisito alternativo MDS (FGA0312) ou Requisitos de Software (FGA0313). Resposta original: Para cursar Testes de Software, é necessário ter cursado Métodos de Desenvolvimento de Software. [2]

**Fontes citadas na resposta:**

- [2] **F16** · [Fluxograma de Engenharia de Software (235 créditos) — transcrição](https://software.unb.br/wp-content/uploads/2026/02/grade_curricular_esw.jpg) · p. 1 · chunk `F16-0011`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.09 s · geração 0.8 s.</p>


### D5 · Grade de Energia

```text
$ python -m rumo_rag perguntar "Em que semestre a Engenharia de Energia tem Termodinâmica 1 e quantos créditos o curso exige?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F23-0005` | Matriz curricular de Engenharia de Energia (251 créditos) — transcrição | 1 |  — FCTE/UnB ( > Ano 3 · 5º semestre de Engenharia de Energia | 0.675 |
| 2 | `F23-0001` | Matriz curricular de Engenharia de Energia (251 créditos) — transcrição | 1 |  — FCTE/UnB ( > Ano 1 · 1º semestre de Engenharia de Energia | 0.686 |
| 3 | `F23-0000` | Matriz curricular de Engenharia de Energia (251 créditos) — transcrição | 1 | ricular atual do curso de Engenharia de Energia — FCTE/UnB ( | 0.651 |
| 4 | `F23-0007` | Matriz curricular de Engenharia de Energia (251 créditos) — transcrição | 1 |  — FCTE/UnB ( > Ano 4 · 7º semestre de Engenharia de Energia | 0.666 |
| 5 | `F23-0009` | Matriz curricular de Engenharia de Energia (251 créditos) — transcrição | 1 |  — FCTE/UnB ( > Ano 5 · 9º semestre de Engenharia de Energia | 0.651 |

!!! quote "Resposta gerada (ollama)"
    [3] O curso de Engenharia de Energia exige no mínimo 251 créditos. [4] No ano 7º (Ano 4), a disciplina Termodinâmica 1 é oferecida, com 4·0·6 créditos.

**Fontes citadas na resposta:**

- [3] **F23** · [Matriz curricular de Engenharia de Energia (251 créditos) — transcrição](https://fcte.unb.br/wp-content/uploads/2024/08/Captura-de-tela-de-2024-08-26-15-23-04.png) · p. 1 · chunk `F23-0000`
- [4] **F23** · [Matriz curricular de Engenharia de Energia (251 créditos) — transcrição](https://fcte.unb.br/wp-content/uploads/2024/08/Captura-de-tela-de-2024-08-26-15-23-04.png) · p. 1 · chunk `F23-0007`

!!! danger "Verificador de fidelidade: valores sem fonte"
    A resposta traz **6 créditos**, que não aparece em nenhum trecho recuperado. O sistema mostra este alerta ao estudante.


<p class="legenda">Busca 0.04 s · geração 1.55 s.</p>


### D6 · Biomédica

```text
$ python -m rumo_rag perguntar "Sou da graduação. Posso cursar uma disciplina do mestrado em Engenharia Biomédica? Como peço?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F26-0001` | PPGEB (Mestrado em Engenharia Biomédica) — como aluno de graduação cursa disciplinas do mestrado | 1 | ALUNO DE GRADUAÇÃO | 0.735 |
| 2 | `F26-0002` | PPGEB (Mestrado em Engenharia Biomédica) — como aluno de graduação cursa disciplinas do mestrado | 1 | ALUNO DE GRADUAÇÃO | 0.708 |
| 3 | `F28-0000` | PPGEB (Mestrado em Engenharia Biomédica) — edital de seleção do mestrado (ingresso em 2027/1) | 1 |  | 0.669 |
| 4 | `F25-0000` | PPGEB (Mestrado em Engenharia Biomédica) — matriz curricular (créditos mínimos) | 1 | MATRIZ CURRICULAR | 0.621 |
| 5 | `F28-0001` | PPGEB (Mestrado em Engenharia Biomédica) — edital de seleção do mestrado (ingresso em 2027/1) | 1 |  | 0.678 |

!!! quote "Resposta gerada (ollama)"
    Sim, você pode cursar uma disciplina do mestrado em Engenharia Biomédica enquanto está no curso de graduação [1]. Para isso, você deve seguir os seguintes passos:
    1) Verificar a lista de oferta vigente do curso;
    2) Verificar o período de matrícula de pós-graduação no calendário de matrícula;
    3) Solicitar a matrícula da disciplina do PPGEB ao coordenador de seu curso de graduação.

**Fontes citadas na resposta:**

- [1] **F26** · [PPGEB (Mestrado em Engenharia Biomédica) — como aluno de graduação cursa disciplinas do mestrado](https://ppgeb.unb.br/aluno-de-graduacao/) · p. 1 · chunk `F26-0001`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.09 s · geração 2.72 s.</p>


### D7 · Fora da base

```text
$ python -m rumo_rag perguntar "Qual o wifi da biblioteca da FCTE?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F21-0263` | Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) | 114 |  | 0.542 |
| 2 | `F17-0217` | Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) | 106 |  | 0.539 |
| 3 | `F21-0011` | Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) | 7 |  | 0.501 |
| 4 | `F21-0026` | Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) | 16 |  | 0.523 |
| 5 | `F17-0093` | Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) | 45 |  | 0.503 |

!!! quote "Resposta gerada (ollama)"
    Não encontrei essa informação nas fontes da base. Pode ser que seja um recurso adicional não mencionado nos projetos pedagógicos citados. Verifique diretamente com a Biblioteca UnB Gama ou a Central de Atendimento ao Estudante (CAE).

**Fontes citadas na resposta:** nenhuma.

<p class="legenda">Busca 0.09 s · geração 1.62 s.</p>


### D8 · Limitação

```text
$ python -m rumo_rag perguntar "Sou estudante de graduação da FCTE sem auxílio. Quanto pago no almoço do RU e até que horas ele funciona no Gama?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F03-0003` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Gama (FCTE) | 0.727 |
| 2 | `F17-0200` | Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) | 98 |  | 0.626 |
| 3 | `F21-0244` | Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) | 106 |  | 0.621 |
| 4 | `F13-0001` | Assistência estudantil na FCTE | 1 | ria de Desenvolvimento Social – Serviço de Programas Sociais | 0.627 |
| 5 | `F03-0002` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Ceilândia (FCTS) | 0.635 |
| 6 | `F03-0004` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Planaltina (FUP) | 0.633 |
| 7 | `F08-0009` | Cardápio semanal do RU Gama — 02/11 a 08/11/2026 | 2 | Almoço · sexta-feira 06/11/2026 | 0.625 |

!!! quote "Resposta gerada (ollama)"
    O aluno de graduação sem auxílio na FCTE (Faculdade de Ciências Tecnológicas e Engenharia) paga R$ 10,50 por refeição no RU Gama. O almoço funciona das 11h às 14h30, de segunda a sexta-feira, exceto feriados [1].

**Fontes citadas na resposta:**

- [1] **F03** · [Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE)](https://ru.unb.br/unidades/) · p. 1 · chunk `F03-0003`

!!! danger "Verificador de fidelidade: valores sem fonte"
    A resposta traz **R$ 10,50**, que não aparece em nenhum trecho recuperado. O sistema mostra este alerta ao estudante.


<p class="legenda">Busca 0.16 s · geração 2.06 s.</p>

