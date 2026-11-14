# Comparação: LLM puro × RAG

Comparação empírica entre o modelo **Qwen2.5-7B-Instruct** operando em memória paramétrica pura e integrado ao pipeline RAG do RUmo (busca híbrida BGE-M3 + BM25 sobre 36 fontes oficiais).

---

## 1. Motivação e metodologia

Modelos de linguagem sem ancoragem documental sofrem alucinações severas em domínios fechados. Na FCTE e no RU, inventar tarifas, cardápios ou pré-requisitos causa prejuízos imediatos ao estudante.

Para mensurar esse comportamento, submetemos as **32 perguntas-ouro** (`rag/avaliacao/perguntas_ouro.jsonl`) a dois regimes sob parâmetros idênticos (temperatura = 0,2; top_p = 0,9; modelo `qwen2.5:7b` executado em GPU NVIDIA L4 com precisão FP16 no Colab e validado localmente via Ollama):

1. **LLM puro (Sem RAG):** O prompt envia apenas a pergunta do discente e uma instrução genérica de assistente acadêmico, sem injeção de contexto.
2. **RUmo (Com RAG):** A busca híbrida recupera os 5 chunks mais relevantes (`k=5`) e os injeta no prompt com metadados, regra de citação `[n]` e instrução de recusa fora da base (**RF03** e **RF04**).

### Estudo de ablação: 4 configurações avaliadas {: #estudo-de-ablacao-as-4-configuracoes-de-arquitetura-avaliadas }

Antes do teste de 38 perguntas, avaliamos **4 configurações de arquitetura** (`rag/testar_4_configuracoes.py` e `rag/comparativo_rag.py`) sobre 3 cenários canônicos:
- **`P1` (Tarifa do RU):** *"Quanto um estudante de graduação paga no almoço do RU?"* (Gabarito: R$ 4,50 - Grupo III ou R$ 0,00 - Grupo I, docs `F01`/`F04`).
- **`P2` (Fluxo curricular):** *"Quais são os pré-requisitos de Testes de Software na FCTE?"* (Gabarito: Requisitos de Software `FGA0313`, ligado a MDS `FGA0312`, doc `F16`).
- **`P3` (Fora da base / RF04):** *"Qual é a senha do Wi-Fi da biblioteca da FCTE?"* (Gabarito: Recusa obrigatória conforme RF04, sem documento associado).

A **Tabela 1** resume o comportamento medido em cada configuração.

| # | Configuração | Latência típica | Rastreabilidade / Fontes | Alucinações (`valores_sem_fonte`) | Recusa fora da base (`P3` / RF04) | Veredito |
|:---:|---|:---:|:---:|:---:|:---:|---|
| **1** | **LLM Pura (Zero-shot, sem RAG)** | ~3–5 s | 0% (sem fontes) | Nula em números; inventa nomes de entidades | Recusa semântica genérica (TI/secretaria) | **Descartada:** sem fontes auditáveis, viola RF03 e RNF01 |
| **2** | **RAG Extrativo (Sem LLM)** | < 0,1 s (após warmup) | 100% (trecho literal) | 0 (porém retorna valor errado de outro campus) | Falha (devolve trechos léxicos sem recusar) | **Descartada:** respostas truncadas, erro de contexto e viola RF04 |
| **3** | **RAG Generativo Simples (`k=3`)** | ~2–4 s | Alta (`[1]`–`[3]`) | 0 em números | Acerta (*"Não encontrei..."*) | **Insuficiente:** omite regras em listas longas de isenção e fluxo |
| **4** | **RAG Generativo Completo (`k=5` + Verificador)** | ~3–6 s | Total (`[1]`–`[5]`, deduplicadas) | 0 (auditada por regex determinística) | Acerta (*"Não encontrei..."*) | **Escolhida para o RUmo** |

<p class="legenda">Tabela 1. Estudo de ablação comparativo das 4 configurações de arquitetura (<code>rag/testar_4_configuracoes.py</code> e <code>rag/comparativo_rag.py</code>).</p>

!!! warning "Notas empíricas sobre o estudo de ablação das 4 configurações"
    1. **Gabarito oficial de `P1`:** O valor para graduação sem assistência socioeconômica é **R$ 4,50** (Grupo III, Resolução F04), sendo R$ 0,00 para o Grupo I (isentos).
    2. **Recusa da LLM Pura em `P3`:** O modelo puro não inventou senhas de Wi-Fi; emitiu recusa genérica (*"Não tenho acesso a senhas... contate o TI ou a secretaria"*). Verificadores sintáticos rígidos que buscavam a frase literal do RAG falhavam em detectar essa abstenção.
    3. **Escopo da métrica de Recusa:** A recusa aplica-se estritamente a perguntas fora da base documental (`P3`). Em perguntas de domínio (`P1` e `P2`), a métrica registra **N/A** (não aplicável), pois o sistema deve entregar o dado factual.
    4. **Invisibilidade de alucinações nominais em `valores_sem_fonte`:** O modelo puro alucinou FCTE como *"Faculdade Cásper Líbero"* (local), *"Faculdade de Ciências Tecnológicas"* (Q24) e *"Ciências e Tecnologia de Gama"* (D7/Q32), inventou cursos (*Elétrica e Sistemas de Informação* em Q23) e chamou o RU de *"Registro Universitário"* (C05). Como a regex monitora apenas números, moedas e códigos, acusou **zero alucinações**. Daí a necessidade da auditoria semântica complementar (RAGAS).
    5. **Groundedness vs. Corretude no RAG Extrativo:** Em `P1`, o modo extrativo devolveu **R$ 2,50** recortando o documento do campus Planaltina. Obteve zero alucinações na regex porque o número constava no chunk, mas errou a regra da FCTE. Apenas a síntese generativa (`k=5`) articulou a regra correta (R$ 4,50).
    6. **Aquecimento (Warmup) no RAG Extrativo:** A primeira consulta extrativa registrou ~5,9 s em medições locais sem warmup devido ao carregamento inicial do `bge-m3`. Com o modelo aquecido, a latência real é `< 0,1 s`.
    7. **Deduplicação de fontes:** O extrator deduplica identificadores (`dict.fromkeys`) para refletir a quantidade real de atos normativos distintos citados.

Para reproduzir a bateria comparativa localmente com o Ollama:

```bash
cd rag
export RUMO_OLLAMA_MODEL=qwen2.5:7b
python testar_4_configuracoes.py
python comparativo_rag.py
```

---

## 2. Casos comparativos representativos

A **Tabela 2** ilustra as diferenças qualitativas entre as abordagens em três casos emblemáticos.

| Pergunta | Resposta do LLM Puro (Sem RAG) | Resposta do RUmo (Com RAG) | Diagnóstico da Diferença |
|---|---|---|---|
| **Q01:** *"Quanto custa o almoço no RU para um estudante de graduação sem auxílio?"* | *Alucina valor plausível mas incorreto (ex.: R$ 5,00).* | *Recupera o valor oficial exato (R$ 4,50, Grupo III) com citação [1] de F01/F04.* | **Alucinação eliminada:** Ancoragem documental garante a tarifa correta. |
| **Q14:** *"Quais são os pré-requisitos de Testes de Software?"* | *Mistura requisitos de outras universidades (ex.: POO ou Engenharia de Requisitos).* | *Recupera o pré-requisito formal da FCTE citando o fluxograma F16.* | **Fluxo corrigido:** Respeito à matriz curricular oficial da FCTE/UnB. |
| **D7 (Fora da base):** *"Qual o wifi da biblioteca da FCTE?"* | *Inventa redes genéricas (ex.: `UnB-WiFi` ou `UnB-Gama-EDU`).* | *Recusa expressamente: "Não encontrei essa informação nas fontes da base" (RF04).* | **Recusa correta:** Evita inventar credenciais sem evidência oficial. |

<p class="legenda">Tabela 2. Casos representativos do protocolo de comparação entre modelo puro e RUmo com RAG.</p>

---

## 3. Limitação identificada: raciocínio em cascata {: #o-caso-em-que-o-rag-nao-ajudou }

Relatar apenas acertos mascara fragilidades de engenharia. Documentamos um caso real onde **a recuperação textual pura não produz a resposta completa**.

### Pergunta de teste

> *"Se um estudante for reprovado em Cálculo 1 no 1º semestre de Engenharia de Software, quais disciplinas ele fica impossibilitado de cursar até o 3º semestre?"*

### Diagnóstico da resposta

A **Tabela 3** compara a saída do sistema com o gabarito oficial da matriz de Engenharia de Software.

| Dimensão | Conteúdo observado |
|---|---|
| **Trechos recuperados** | Chunks do documento F16 (*Fluxograma de Engenharia de Software FCTE*, págs. 1 e 2) e normas de matrícula. |
| **Comportamento do RAG** | Recupera com precisão a tabela de disciplinas e pré-requisitos imediatos. Identifica que Cálculo 1 tranca Cálculo 2 no 2º semestre, mas **omite as dependências de 2ª ordem no 3º semestre** (disciplinas que exigem Cálculo 2 ou Física 1 em cascata). |
| **Gabarito oficial** | O estudante fica impedido de cursar **Cálculo 2** (2º semestre) e, por transitividade, as matérias subsequentes do 3º semestre dependentes de Cálculo 2. |
| **Diagnóstico técnico** | **Incompletude por falha de encadeamento transitivo.** O RAG recuperou os chunks corretos, mas o modelo falhou na dedução em cascata. |

<p class="legenda">Tabela 3. Diagnóstico da limitação do RAG em cadeia de pré-requisitos transitivos.</p>

### Causa-raiz

1. **RAG textual não infere sobre grafos:** O chunk traz relações locais de dependência imediata. Mapear cadeias longas ($A \rightarrow B \rightarrow C$) exige travessia em grafo direcionado acíclico (DAG). Modelos de 7B têm dificuldade de deduzir caminhos transitivos a partir de tabelas em texto corrido.
2. **Dispersão de atenção (*Lost in the Middle*):** Chunks de fluxograma agrupam dezenas de disciplinas densas, dispersando a atenção do modelo sobre relações secundárias.

### Encaminhamento para a Entrega 4

Esse resultado comprova que **a recuperação puramente textual é insuficiente para navegar estruturas curriculares complexas**. O projeto endereça essa limitação na próxima fase:

- **Evolução Multiagente (Entrega 4):** O **Agente Fluxo** utilizará uma ferramenta determinística (*tool calling*) com navegação em grafo estruturado (JSON/NetworkX), substituindo a dedução probabilística do texto corrido por busca formal no DAG de disciplinas.

---

## 4. Matriz consolidada e registro das 32 perguntas-ouro

A **Tabela 4** consolida o desempenho comparativo agregado nas 32 perguntas-ouro por eixo temático (`ru`, `apoio` e `fluxo`).

!!! note "Medição Real em GPU NVIDIA L4 e Ausência de Latência"
    Os dados agregados da Tabela 4 decorrem da execução física em GPU NVIDIA L4 no Google Colab. Em conformidade com o Requisito R3, métricas temporais foram omitidas. Todas as 32 perguntas com RAG registram zero alucinação numérica (`valores_sem_fonte = 0`) e fidelidade factual de 0,97.

| Eixo Temático | Quantidade | Sem RAG: Alucinações | Com RAG: Fidelidade total | Com RAG: Incompletude |
|---|:---:|:---:|:---:|:---:|
| **Restaurante Universitário (`ru`)** | 11 | 11 / 11 (6 com valores inventados) | 10 / 11 (91%) | 1 / 11 (Q04)* |
| **Apoio Alimentar e Alergênicos (`apoio`)** | 2 | 2 / 2 (0 com valores inventados) | 2 / 2 (100%) | 0 / 2 (0%) |
| **Fluxo e Disciplinas (`fluxo`)** | 19 | 19 / 19 (3 com valores inventados) | 19 / 19 (100%) | 0 / 19 (0%) |
| **Total Consolidado** | **32** | **32 / 32 (9 com valores sem fonte)** | **31 / 32 (97%)** | **1 / 32 (3%)*** |

<p class="legenda">Tabela 4. Matriz de desempenho comparativo agregado nas 32 perguntas de teste (medido em GPU NVIDIA L4). *Nota: Q04 apresentou abstenção/recusa por falta de detalhe específico de gratuidade no trecho recuperado.</p>

??? info "Tabela 5 · Registro completo das 32 perguntas-ouro: LLM puro × RAG (clique para expandir)"

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

    <p class="legenda">Tabela 5. Tabela mestre das 32 perguntas-ouro (<code>rag/avaliacao/perguntas_ouro.jsonl</code>) para comparação lado a lado entre LLM puro e RUmo com RAG (validação determinística preliminar).</p>

---

## 5. Instruções para reprodução física em GPU no Google Colab {: #5-instrucoes-para-reproducao-fisica-em-gpu-no-google-colab }

!!! info "Finalidade da avaliação em nuvem vs. Produção"
    O uso temporário de GPUs potentes no Google Colab acelerou a extração dos relatórios comparativos e decorreu da falta momentânea de acesso ao MacBook Air M4 (24 GB) da equipe. Trata-se de um ambiente empregado puramente para avaliação, e não para o sistema em produção: a arquitetura do RUmo permanece estritamente restrita para caber nas especificações de uma **NVIDIA GeForce RTX 4060 de 8 GB** (hardware de referência adotado desde a Entrega 1).

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
    | 13/11/2026 | 3.1 | Inclusão do estudo de ablação das 4 configurações (Tabela 1), análise empírica crítica e renumeração | Grupo 04 |
