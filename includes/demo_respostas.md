
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
| 4 | `F04-0005` | Valores das refeições e grupos de acesso | 1 | Valores das refeições e grupos > Restaurante Executivo | 0.653 |
| 5 | `F03-0002` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Ceilândia (FCTS) | 0.582 |

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    Um estudante de graduação paga R$ 4,50 no almoço do RU, conforme o Grupo II mencionado em [1].

**Fontes citadas na resposta:**

- [1] **F04** · [Valores das refeições e grupos de acesso](https://ru.unb.br/precos-e-grupos/) · p. 1 · chunk `F04-0002`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 11.15 s · geração 25.62 s.</p>


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

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    O prato principal vegetariano estrito do almoço de quarta-feira, 11/11/2026, no RU Gama é abobrinha recheada com lentilha ao sugo. [1]

**Fontes citadas na resposta:**

- [1] **F09** · [Cardápio semanal do RU Gama — 09/11 a 15/11/2026](https://ru.unb.br/wp-content/uploads/2026/11/Gama-Semana-04-09-11-a-15-11.pdf) · p. 2 · chunk `F09-0007`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.1 s · geração 3.82 s.</p>


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

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    Os estudantes de graduação e pós-graduação stricto sensu presenciais, em situação de vulnerabilidade socioeconômica, têm direito a comer de graça no RU da UnB. Isso é regulamentado pelo Programa Auxílio Alimentação, administrado pela Diretoria do RU e regido pela Resolução DAC nº 06/2023. Os critérios de seleção e análise socioeconômica são responsabilidade da Diretoria de Desenvolvimento Social (DDS/DAC). [5]

**Fontes citadas na resposta:**

- [5] **F06** · [Programa Auxílio Alimentação — regras de uso](https://ru.unb.br/programa-auxilio-alimentacao/) · p. 1 · chunk `F06-0000`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.06 s · geração 8.97 s.</p>


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

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    Para cursar Testes de Software (FGA0314), é necessário ter cursado antes Requisitos de Software (FGA0313) [2]. Além disso, o fluxograma indica que também há uma ligação tracejada entre Métodos de Desenvolvimento de Software (FGA0312) e Testes de Software (FGA0314), mas não especifica se é um pré-requisito ou correquisito [1].

**Fontes citadas na resposta:**

- [1] **F16** · [Fluxograma de Engenharia de Software (235 créditos) — transcrição](https://software.unb.br/wp-content/uploads/2026/02/grade_curricular_esw.jpg) · p. 1 · chunk `F16-0012`
- [2] **F16** · [Fluxograma de Engenharia de Software (235 créditos) — transcrição](https://software.unb.br/wp-content/uploads/2026/02/grade_curricular_esw.jpg) · p. 1 · chunk `F16-0011`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.04 s · geração 8.25 s.</p>


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

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    Termodinâmica 1 é oferecida no 5º semestre do 3º ano de Engenharia de Energia [1]. O curso exige no mínimo 251 créditos [3].

**Fontes citadas na resposta:**

- [1] **F23** · [Matriz curricular de Engenharia de Energia (251 créditos) — transcrição](https://fcte.unb.br/wp-content/uploads/2024/08/Captura-de-tela-de-2024-08-26-15-23-04.png) · p. 1 · chunk `F23-0005`
- [3] **F23** · [Matriz curricular de Engenharia de Energia (251 créditos) — transcrição](https://fcte.unb.br/wp-content/uploads/2024/08/Captura-de-tela-de-2024-08-26-15-23-04.png) · p. 1 · chunk `F23-0000`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.04 s · geração 3.42 s.</p>


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

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    Sim, você pode cursar uma disciplina do mestrado em Engenharia Biomédica. Seguem os passos:
    
    1. Verifique a lista de ofertas vigente do curso.
    2. Confira o período de matrícula de pós-graduação no calendário de matrícula.
    3. Solicite a matrícula à disciplina do PPGEB ao coordenador do seu curso de graduação, indicando: 
       - seu nome completo e número de matrícula;
       - nome, código e turma da disciplina;
       - curso de graduação;
       - modalidade de cursada (ELETIVA ou OPTATIVA).
    
    4. O coordenador do curso de graduação abrirá um processo SEI:
       - para ELETIVA, o próprio coordenador aprovará e encaminhará para a secretaria de pós-graduação.
       - para OPTATIVA, será necessário aprovação do Colegiado do Curso de Graduação e do Colegiado do PPGEB. Em alguns casos, também da Câmara de Pesquisa e Pós-Graduação – CPP / DPG.
    
    [1][2]

**Fontes citadas na resposta:**

- [1] **F26** · [PPGEB (Mestrado em Engenharia Biomédica) — como aluno de graduação cursa disciplinas do mestrado](https://ppgeb.unb.br/aluno-de-graduacao/) · p. 1 · chunk `F26-0001`
- [2] **F26** · [PPGEB (Mestrado em Engenharia Biomédica) — como aluno de graduação cursa disciplinas do mestrado](https://ppgeb.unb.br/aluno-de-graduacao/) · p. 1 · chunk `F26-0002`

<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>


<p class="legenda">Busca 0.04 s · geração 14.99 s.</p>


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
| 5 | `F17-0093` | Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) | 45 |  | 0.504 |

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    Não encontrei essa informação nas fontes da base. Sugiro entrar em contato com a Secretaria Acadêmica da FCTE/UnB para obter detalhes específicos sobre o Wi-Fi da biblioteca.

**Fontes citadas na resposta:** nenhuma.

<p class="legenda">Busca 0.05 s · geração 3.77 s.</p>


### D8 · Limitação

```text
$ python -m rumo_rag perguntar "Sou estudante de graduação da FCTE sem auxílio. Quanto pago no almoço do RU e até que horas ele funciona no Gama?"
```

**Trechos recuperados (busca híbrida):**

| # | Chunk | Documento | Pág. | Seção | Similaridade |
|---|---|---|---|---|---|
| 1 | `F03-0003` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Gama (FCTE) | 0.727 |
| 2 | `F17-0200` | Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025) | 98 |  | 0.625 |
| 3 | `F21-0244` | Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023) | 106 |  | 0.621 |
| 4 | `F13-0001` | Assistência estudantil na FCTE | 1 | ria de Desenvolvimento Social – Serviço de Programas Sociais | 0.627 |
| 5 | `F03-0004` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Planaltina (FUP) | 0.633 |
| 6 | `F03-0002` | Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) | 1 | Campus Ceilândia (FCTS) | 0.635 |
| 7 | `F08-0009` | Cardápio semanal do RU Gama — 02/11 a 08/11/2026 | 2 | Almoço · sexta-feira 06/11/2026 | 0.625 |

!!! quote "Resposta gerada (Qwen2.5-7B-Instruct · 4 bits · local)"
    O almoço no RU Gama funciona de 11h às 14h30 de segunda a sexta-feira, exceto feriados. Como você é estudante de graduação da FCTE sem auxílio, pagará o preço normal. Não encontrei essa informação nas fontes da base. Sugiro entrar em contato com a Diretoria do Restaurante Universitário para obter o valor atual.

**Fontes citadas na resposta:** nenhuma.

<p class="legenda">Busca 0.11 s · geração 8.29 s.</p>

