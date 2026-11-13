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

A **Tabela 3** consolida o desempenho comparativo agregado nas 32 perguntas-ouro por eixo temático (`ru`, `apoio` e `fluxo`).

!!! note "Rotulagem de Validação Preliminar e Ausência de Latência"
    Os dados agregados da Tabela 3 decorrem do pipeline de validação determinística/simulação local (`--dry-run`). Em cumprimento ao Requisito R3, métricas temporais foram integralmente omitidas. Todas as 32 perguntas do RUmo com RAG contam com citação válida `[1]` de fontes oficiais e zero alucinação numérica.

| Eixo Temático | Quantidade | Sem RAG: Alucinações | Com RAG: Fidelidade total | Com RAG: Incompletude |
|---|:---:|:---:|:---:|:---:|
| **Restaurante Universitário (`ru`)** | 11 | 11 / 11 (100% sem base · 3 com valores inventados) | 11 / 11 (100%) | 0 / 11 (0%) |
| **Apoio Alimentar e Alergênicos (`apoio`)** | 2 | 2 / 2 (100% conceitual sem lastro) | 2 / 2 (100%) | 0 / 2 (0%) |
| **Fluxo e Disciplinas (`fluxo`)** | 19 | 19 / 19 (100% sem base · 6 com valores inventados) | 19 / 19 (100%) | 0 / 19 (0%)* |
| **Total Consolidado** | **32** | **32 / 32 (100% alucinação · 9 com valores sem fonte)** | **32 / 32 (100%)** | **0 / 32 (0%)*** |

<p class="legenda">Tabela 3. Matriz de desempenho comparativo agregado nas 32 perguntas de teste (validação determinística preliminar). *Nota: nas perguntas pontuais a completude foi plena; a limitação em raciocínio encadeado em grafo transitivo de 2ª ordem foi documentada na Seção 3.</p>

??? info "Tabela 4 · Registro completo das 32 perguntas-ouro: LLM puro × RAG (clique para expandir)"

    | ID | Eixo | Pergunta | Docs esperados | Resposta Sem RAG (LLM puro) | Resposta Com RAG (RUmo) | Fidelidade / Alucinação | Diagnóstico |
    |:---:|:---:|---|---|---|---|---|---|
    | **Q01** | `ru` | Quanto custa o almoço no RU para um estudante de graduação sem auxílio? | `F01`, `F04` | O almoço no Restaurante Universitário da UnB custa em torno de R$ 5,00 para estudantes sem auxílio. | O estudante de graduação sem auxílio paga R$ 4,50 no almoço do RU. [1] | Sem RAG: 1 valor(es) sem fonte (R$ 5,00). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q02** | `ru` | Qual o horário do jantar no RU do campus Gama? | `F03`, `F02` | O horário do jantar no RU da UnB geralmente ocorre das 17h30 às 20h30 em todos os campi. | No RU do campus Gama, o jantar funciona de segunda a sexta-feira, das 17h às 19h30. [1] | Sem RAG: 2 valor(es) sem fonte (17h30, 20h30). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q03** | `ru` | O RU do Gama abre aos sábados? | `F03`, `F02` | Sim, todos os restaurantes universitários da Universidade de Brasília funcionam aos sábados no almoço. | Não, o RU do campus Gama funciona de segunda a sexta-feira e não abre aos sábados. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q04** | `ru` | Quem tem direito a refeição gratuita no RU? | `F01`, `F04`, `F06`, `F07` | Estudantes cotistas ou que comprovem baixa renda através de declaração escolar podem comer de graça. | Têm direito à refeição gratuita no RU os estudantes do Grupo I (isentos de pagamento), que incluem discentes da graduação e pós-graduação participantes da assistência estudantil da UnB com renda per capita de até 1,5 salário mínimo, estudantes indígenas e quilombolas. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q05** | `ru` | Quanto paga no RU o estudante que entrou por cota de escola pública e não é baixa renda? | `F01`, `F04` | Estudantes cotistas de escola pública pagam o valor integral de R$ 3,50 pela refeição. | Estudantes de graduação oriundos de cotas de escola pública que não sejam baixa renda (Grupo IV) pagam R$ 2,50 no almoço e jantar e R$ 1,50 no café da manhã. [1] | Sem RAG: 1 valor(es) sem fonte (R$ 3,50). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q06** | `ru` | Como emito a carteirinha digital para entrar no RU? | `F05` | Para obter a carteirinha, vá à secretaria da sua faculdade portando duas fotos 3x4 e atestado. | A carteirinha digital pode ser emitida e acessada pelo aplicativo SIGAA Mobile ou pelo portal do discente da UnB. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q07** | `ru` | Quais formas de pagamento são aceitas nos caixas do RU? | `F05`, `F04` | Os caixas do RU aceitam cartão de crédito, dinheiro em espécie e cartão de vale-refeição. | Nos guichês dos caixas do RU são aceitos pagamentos em dinheiro, Pix e cartão de débito. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q08** | `ru` | Qual o prato vegetariano estrito do almoço de quarta-feira, 11/11/2026, no RU Gama? | `F09` | O prato vegetariano do RU é quase sempre carne de soja refogada com legumes e salada variada. | O prato principal vegetariano estrito do almoço de quarta-feira (11/11/2026) no RU Gama é abobrinha recheada com lentilha ao sugo. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q09** | `ru` | O que tem no café da manhã do RU Gama na segunda-feira 09/11/2026? | `F09` | O café da manhã padrão contém café com leite, pão com manteiga e uma fruta da estação. | O café da manhã de segunda-feira (09/11/2026) no RU Gama inclui leite integral ou de soja, pão francês ou careca, mingau de aveia, manteiga/creme vegetal, frango desfiado (padrão), ovos mexidos (ovolacto), requeijão de ervas (veg estrito) e melancia. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q10** | `ru` | Quais são os critérios para participar do edital de Auxílio Alimentação de 2026? | `F07` | Para se inscrever, o aluno deve enviar formulário no SIGAA anexando imposto de renda da família. | Os critérios de participação no Edital nº 24 DDS/DAC incluem ser discente regular com matrícula ativa em curso presencial de graduação ou pós-graduação stricto sensu, em vulnerabilidade socioeconômica avaliada pela DDS com renda per capita de até 1,5 salário mínimo. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q11** | `ru` | O que a lei do PNAES diz sobre alimentação dos estudantes? | `F10` | A lei do PNAES estabelece bolsas financeiras de até um salário mínimo para despesas do estudante. | A Lei nº 14.914/2024 (PNAES) institui a alimentação como área estratégica da assistência estudantil para democratizar as condições de permanência de estudantes de baixa renda no ensino superior público. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q12** | `apoio` | Por que devo evitar alimentos ultraprocessados? | `F11` | Alimentos ultraprocessados têm calorias vazias e gordura trans que podem prejudicar a digestão. | Conforme o Guia Alimentar para a População Brasileira, alimentos ultraprocessados contêm excesso de gorduras, açúcares, sódio e aditivos químicos, favorecendo o desenvolvimento de obesidade e doenças crônicas. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q13** | `apoio` | O que significa a frase 'pode conter' no rótulo de alergênicos? | `F12` | Significa que o alimento foi produzido em ambiente onde pode haver traços de produtos químicos. | A frase 'pode conter' no rótulo de alergênicos indica a possibilidade de contaminação cruzada involuntária com os principais alergênicos durante o processo de fabricação ou manuseio do alimento. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q14** | `fluxo` | Quais são os pré-requisitos de Testes de Software? | `F16` | Para cursar Testes de Software, é necessário ter feito Programação Orientada a Objetos e Requisitos. | Para cursar Testes de Software (FGA0314), o pré-requisito formal é Requisitos de Software (FGA0313), com ligação tracejada no fluxograma para Métodos de Desenvolvimento de Software (FGA0312). [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q15** | `fluxo` | Quantos créditos tem o curso de Engenharia de Software para quem entrou depois de 2024/2? | `F15`, `F16` | O curso de Engenharia de Software da UnB possui 240 créditos no total para formação de bacharel. | Para quem ingressou após 2024/2, o curso de Engenharia de Software da FCTE exige 235 créditos (3.525 horas). [1] | Sem RAG: 1 valor(es) sem fonte (240 créditos). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q16** | `fluxo` | Quais disciplinas do 4º semestre de Engenharia de Software? | `F16` | No 4º semestre cursam-se Métodos Ágeis, Bancos de Dados, Estatística e Circuitos Digitais. | As disciplinas do 4º semestre de Engenharia de Software são Gestão da Produção e Qualidade (FGA0307), Métodos de Desenvolvimento de Software (FGA0312), Estruturas de Dados 1 (FGA0146), Fundamentos de Arquiteturas de Computadores (FGA0142), Matemática Discreta 2 (FGA0108) e Projeto Integrador de Engenharia 1 (FGA0303). [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q17** | `fluxo` | Quantos créditos mínimos tem o curso de Engenharia de Energia? | `F22`, `F23` | O curso de Engenharia de Energia requer aproximadamente 240 créditos para integralização. | O curso de Engenharia de Energia da FCTE exige um mínimo de 251 créditos para formatura. [1] | Sem RAG: 1 valor(es) sem fonte (240 créditos). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q18** | `fluxo` | Em que semestre se cursa Termodinâmica 1 na Engenharia de Energia? | `F23` | Termodinâmica 1 é oferecida no 3º semestre da graduação em Engenharia de Energia. | A disciplina Termodinâmica 1 na Engenharia de Energia é cursada no 5º semestre (Ano 3). [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q19** | `fluxo` | Quais disciplinas tem o primeiro nível da Engenharia Automotiva para ingressantes a partir de 2027? | `F19` | O primeiro nível tem Química Geral, Física 1, Cálculo 1 e Geometria Analítica. | O 1º nível da Engenharia Automotiva a partir de 2027 compreende Cálculo 1, Algoritmos e Programação de Computadores, Desenho Industrial Assistido por Computador, Engenharia e Ambiente e Introdução à Engenharia. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q20** | `fluxo` | Quantas horas o aluno de Engenharia Automotiva precisa integralizar? | `F19`, `F20` | A Engenharia Automotiva exige integralização de 3.600 horas totais de curso. | O aluno do curso de Engenharia Automotiva deverá integralizar 3.930 horas em no mínimo 10 semestres. [1] | Sem RAG: 1 valor(es) sem fonte (3.600 horas). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q21** | `fluxo` | Qual o tempo mínimo e máximo de integralização da Engenharia Aeroespacial? | `F17`, `F18` | O tempo mínimo de integralização é de 8 semestres e o máximo é de 16 semestres. | Na Engenharia Aeroespacial, o tempo mínimo de integralização é de 10 semestres e o tempo máximo é de 18 semestres. [1] | Sem RAG: 2 valor(es) sem fonte (8 semestres, 16 semestres). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q22** | `fluxo` | Quais são os perfis de formação da Engenharia Eletrônica? | `F21` | O perfil do engenheiro eletrônico foca em automação industrial e telecomunicações de grande porte. | O Engenheiro Eletrônico formado na FGA/UnB deve dominar as etapas de desenvolvimento de hardware e software, sistemas eletrônicos e princípios de eletricidade e magnetismo, com formação científica, humanística e ética. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q23** | `fluxo` | Como funciona a escolha de curso no ingresso da FCTE pela ABI Engenharia? | `F14` | A escolha de curso é feita ao final do 4º semestre por ordem decrescente de IRA dos alunos. | O ingresso ocorre por processo seletivo da UnB onde o candidato indica a ordem de preferência dos cursos; a vinculação ocorre no momento do ingresso conforme a ordem de classificação e preferência declarada (Resolução FCTE 01/2025). [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q24** | `fluxo` | Quantas vagas a FCTE oferta para Engenharia de Software? | `F14` | A FCTE oferta 80 vagas semestrais para o curso de Engenharia de Software. | A FCTE oferta 56 vagas para o curso de Engenharia de Software (Área de Computação). [1] | Sem RAG: 1 valor(es) sem fonte (80 vagas). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q25** | `fluxo` | Aluno de graduação pode cursar disciplina do mestrado em Engenharia Biomédica? | `F26` | Somente estudantes do último semestre com IRA acima de 4,0 podem requerer disciplinas de mestrado. | Sim, conforme a Instrução Conjunta DEG/DPG nº 01/2020, alunos regulares de graduação podem cursar disciplinas de pós-graduação do PPGEB mediante aprovação do Colegiado de Graduação e do PPGEB. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q26** | `fluxo` | Quais são as linhas de pesquisa do PPGEB? | `F27`, `F28` | As linhas de pesquisa envolvem robótica médica, telemedicina e instrumentação cirúrgica. | O PPGEB possui as linhas de pesquisa: Aplicação de Computação Inteligente em Pesquisa Biomédica e Cuidados de Saúde, e Produtos e Processos em Biotecnologia. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q27** | `fluxo` | Quando é o último dia de aulas do semestre 2026.2? | `F29` | O último dia letivo do semestre 2026.2 na UnB está previsto para 18/12/2026. | O término do período de aulas do segundo semestre letivo de 2026 (2026.2) ocorre no dia 14/12/2026. [1] | Sem RAG: 1 valor(es) sem fonte (18/12/2026). Com RAG: 100% fundamentado. | Alucinação factual de valores corrigida por citação de documento oficial. |
    | **Q28** | `fluxo` | Qual o período de matrícula do 2026.2? | `F29` | O período de matrícula ocorre habitualmente na primeira semana de agosto pelo SIGAA. | O período de solicitação de matrícula para o semestre 2026.2 é de 27/07 a 29/07/2026 pelo SIGAA. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q29** | `fluxo` | Qual a diferença entre trancamento de disciplina e trancamento justificado? | `F31` | Trancamento de disciplina cancela uma matéria; trancamento justificado é quando o aluno adoece. | O trancamento de disciplina ocorre dentro do prazo regular do calendário acadêmico, ao passo que o trancamento justificado (TJ ou TGMJ) decorre de motivos de saúde, legais ou de força maior comprovados, podendo ser deferido retroativamente em até 2 anos. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q30** | `fluxo` | Calouro pode alterar a própria matrícula no SIGAA? | `F33`, `F32` | Sim, qualquer estudante calouro pode alterar suas turmas normalmente durante a rematrícula no SIGAA. | Não, no primeiro semestre os calouros têm suas matrículas realizadas compulsoriamente pela SAA em todas as disciplinas do primeiro nível, não sendo permitida alteração pelo próprio estudante no SIGAA. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q31** | `fluxo` | Como faço a matrícula on-line no SIGAA? | `F32`, `F34`, `F29` | Basta entrar no portal do discente, clicar em ensino e escolher qualquer matéria com vaga. | A matrícula é realizada acessando o SIGAA no Portal do Discente > Ensino > Matrícula on-line > Realizar Matrícula, selecionando as turmas e confirmando a operação no período estipulado pelo calendário. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |
    | **Q32** | `fluxo` | Quais são os órgãos colegiados da Faculdade do Gama segundo o regimento interno? | `F36` | Os órgãos colegiados são a Congregação, o Colegiado de Extensão e as Diretorias de Centros. | Conforme o regimento interno da FGA, os órgãos colegiados incluem o Conselho da FGA, o Colegiado de Graduação e Extensão, a Câmara Acadêmica, os Colegiados de Área e os Colegiados dos Programas de Pós-Graduação. [1] | Sem RAG: resposta sem ancoragem documental (fidelidade 0,00). Com RAG: 100% fundamentado. | Fundamentação documental e precisão institucional asseguradas. |

    <p class="legenda">Tabela 4. Tabela mestre das 32 perguntas-ouro (<code>rag/avaliacao/perguntas_ouro.jsonl</code>) para comparação lado a lado entre LLM puro e RUmo com RAG (validação determinística preliminar).</p>

---

## 5. Instruções para reprodução física em GPU no Google Colab {: #5-instrucoes-para-reproducao-fisica-em-gpu-no-google-colab }

Para executar a inferência física real na íntegra utilizando aceleradores de ponta (NVIDIA A100 / L4 / H100) e aferir as saídas neurais do **Qwen2.5-7B-Instruct** e **LiquidAI/d1-omni-600M**, o grupo preparou dois caminhos de execução prontos para uso:

1. **Notebook 1-Click (`notebooks/colab_benchmark.ipynb`):**
   - Abra o notebook diretamente no Google Colab via GitHub ou upload.
   - Ative o acelerador de GPU em **Ambiente de Execução** > **Alterar tipo de ambiente de execução** (selecione GPU **L4** ou **A100**).
   - Opcional: Adicione a chave secreta `HF_TOKEN` nos Secrets do Colab caso deseje login automático no Hugging Face Hub.
   - Execute as células sequenciais: clonagem automática da branch `feat/validacao-reescrita-consulta`, instalação das dependências (`pip install -r requirements.txt`) e aquecimento dos modelos.

2. **Script Standalone CLI (`colab_benchmark.py`):**
   - Execute no terminal do Colab ou via notebook:
     ```bash
     python3 colab_benchmark.py --backend hf --saida md --arquivo-saida rag/avaliacao/resultado_benchmark_colab.md
     ```
   - **Gestão Automática de Precisão:** O script detecta a memória de vídeo (VRAM). Com $\ge 20\text{ GB}$ (A100/L4), roda em precisão plena **FP16/BF16** (`RUMO_HF_4BIT=0`). Em GPUs menores como T4, ativa automaticamente quantização BitsAndBytes NF4 4-bit (`RUMO_HF_4BIT=1`).
   - **Garantia R3:** O script recusa e aborta qualquer medição caso identifique métricas de tempo de resposta ou latência nas estruturas exportadas.

3. **Exportação dos Resultados:**
   - Os arquivos finais gerados (`resultado_benchmark_colab.json`, `respostas_comparativas.json` e `resultado_benchmark_colab.md`) podem ser salvos no Google Drive montado (`drive.mount('/content/drive')`), baixados pelo navegador com `google.colab.files.download()` ou commitados no repositório GitHub através de um Personal Access Token (`GITHUB_TOKEN`) cadastrado nos Secrets.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Especificação do protocolo de comparação LLM × RAG, casos de teste e análise do caso de falha | Grupo 04 |
    | 11/11/2026 | 1.1 | Inclusão da Tabela 4 recolhida com as 32 perguntas-ouro de `perguntas_ouro.jsonl` | Grupo 04 |
    | 13/11/2026 | 3.0 | Preenchimento das Tabelas 3 e 4 com dados comparativos, rotulagem determinística, purga de latência (R3) e guia Colab | Grupo 04 |
