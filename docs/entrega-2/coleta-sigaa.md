# Coleta no SIGAA público: turmas e pré-requisitos

Duas perguntas do RUmo dependiam de dado que a base não tinha ou que vinha de transcrição
manual: em que horário e sala é a aula (issue #56) e quais são os pré-requisitos de uma
disciplina (issue #52). As duas respostas estão no SIGAA da UnB, em páginas que **qualquer
pessoa abre sem login**:

- a **consulta de turmas** (`/sigaa/public/turmas/listar.jsf`), com a oferta do semestre por unidade;
- a **consulta de componentes curriculares** (`/sigaa/public/componentes/busca_componentes.jsf`),
  com a ficha de cada disciplina.

O coletor está em `rag/rumo_rag/coleta/sigaa.py`. Ele não entra na área autenticada, não guarda
nome de docente nem número de vagas e faz uma requisição por vez, com pausa entre elas. Isso
mudou a redação da RN-05, que proibia qualquer acesso ao SIGAA; a mudança está explicada em
[Regras de negócio](../entrega-1/regras-de-negocio.md).

```bash
cd rag
python -m rumo_rag.coleta turmas --ano 2026 --periodo 2 --dry-run       # baixa e mostra, sem gravar
python -m rumo_rag.coleta turmas --ano 2026 --periodo 2                 # grava JSON, texto curado e catálogo
python -m rumo_rag.coleta prerequisitos --curriculo software-2024-2 \
    --saida dados/sigaa/prerequisitos_software-2024-2.json               # fichas do SIGAA × grafo
python -m rumo_rag.coleta prerequisitos --local dados/sigaa/prerequisitos_software-2024-2.json   # recompara sem rede
```

!!! note "Por que o coletor abre a página duas vezes"
    O SIGAA é uma aplicação JSF: cada busca é um POST que carrega o estado da página. O
    balanceador da UnB só prende a sessão a um servidor a partir da segunda visita. Sem isso, o
    POST cai em outro servidor e a resposta é "a página que se está tentando acessar não está
    mais ativa". O coletor abre a página duas vezes antes de enviar a busca.

## Oferta de turmas (issue #56)

**Existe fonte aberta.** A consulta pública de turmas devolve, para a FCTE em 2026.2, **228
turmas de 132 disciplinas**, todas com horário por extenso e local. A coleta de 26/11/2026 está
em `rag/dados/turmas/fcte_2026-2.json`, validada por `rag/rumo_rag/coleta/schema_turmas.json`.

| Campo pedido na #56 | Onde está | Exemplo (FGA0314, turma 01) |
|---|---|---|
| `codigo`, `nome` | Cabeçalho do grupo de turmas | FGA0314, Testes de Software |
| `turma` | Coluna Código | 01 |
| `dia`, `inicio`, `fim` | Texto de ajuda do horário ("Terça-feira 08:00 às 09:50") | terça e quinta, 08:00–09:50 |
| `sala` | Coluna Local, separada em `salas` | `FCTE - I10` → `["I10"]` |
| `predio` | **Não publicado** | — |

<p class="legenda">Tabela 1. Campos da oferta de turmas e de onde cada um sai na consulta pública do SIGAA.</p>

O horário vem por extenso na própria página, num texto de ajuda junto do código. Assim o
coletor não precisa traduzir códigos como `35M12` por conta própria; o código fica guardado em
`horario_sigaa` só para conferência.

Três limitações ficam registradas:

- **O prédio não é publicado.** O campo Local traz a unidade e a sala (`FCTE - I10`,
  `FCTE - S2/I9`, `FCTE - LAB SS`), sem dizer em que prédio a sala fica.
- **O Local é texto livre.** Há casos como `NIT/LDS(segunda)/I1(sexta)`, em que cada dia tem uma
  sala. O campo `salas` lista as salas citadas; o texto original fica em `local`.
- **A nomenclatura ainda não foi conferida com o Grupo 09.** O SIGAA usa `I10` e `S2`; o portal
  do Grupo 09 navega por códigos como `T-004` dentro do prédio. O último critério da #56 ("os
  códigos de sala batem com os do Grupo 09") depende dessa conversa.

### Na base do RAG

A oferta entrou no catálogo como **F59**, por um texto curado gerado do JSON
(`rag/dados/curados/oferta_turmas_fcte_2026-2.md`): um parágrafo por disciplina, com código,
nome, turmas, dias, horário e sala. Na busca léxica, ela responde perguntas que citam turma,
sala ou horário ("Em que sala é a turma 01 de Compiladores 1?", "Qual o horário de Algoritmos
em Grafos em 2026.2?"). Quando a pergunta cita só o nome da disciplina ("Que horas é a aula de
Testes de Software?"), o fluxograma (F15/F16) ainda ganha. Para essa pergunta, a resposta
confiável é uma ferramenta que consulte o JSON pelo código, como já se faz com o cardápio.

## Pré-requisitos (issue #52)

**Existe fonte textual oficial.** A ficha pública de cada componente traz a expressão de
pré-requisito (`( FGA0138 OU FGA0313 )`), os correquisitos em campo separado, as equivalências
e o histórico de vigência de cada expressão. A distinção entre pré-requisito e correquisito
sobrevive à extração porque o próprio SIGAA as publica em campos diferentes.

O coletor baixou as **47 fichas** do currículo de Engenharia de Software (`software-2024-2`) e
comparou com o grafo curricular, que vem da transcrição do fluxograma (F16, o gabarito da #52).
Antes de comparar, os códigos antigos viram os vigentes pelas equivalências: o SIGAA ainda
escreve `FGA0138`, código antigo de MDS (hoje `FGA0312`). O resultado está em
`rag/dados/sigaa/prerequisitos_software-2024-2.json`:

| Situação | Relações |
|---|---|
| Iguais ao fluxograma | 74 |
| Diferentes | 20 |
| Disciplina sem ficha no SIGAA | 0 |

<p class="legenda">Tabela 2. Comparação entre os requisitos do SIGAA e o grafo curricular de Engenharia de Software (47 disciplinas, pré-requisitos e correquisitos), coleta de 26/11/2026.</p>

A regra que motivou a revisão, a de Testes de Software (FGA0314), **bate**: o SIGAA pede
`FGA0138 OU FGA0313`, que é MDS ou Requisitos, como está no grafo desde o PR #88.

As 20 diferenças:

| Disciplina | Relação | No grafo (fluxograma) | No SIGAA | Expressão do SIGAA | Fora do currículo |
|---|---|---|---|---|---|
| FGA0084 Desenvolvimento de Software | pré-requisito | nenhum | CIC0004 | `( ( CIC0004 ) OU ( CIC0007 ) )` | — |
| FGA0157 Probabilidade e Estatística Aplicada à Engenharia | pré-requisito | nenhum | MAT0025 | `( ( MAT0025 ) )` | — |
| FGA0071 Prática de Eletrônica Digital 1 | pré-requisito | nenhum | MAT0031 | `( ( MAT0031 ) )` | — |
| FGA0071 Prática de Eletrônica Digital 1 | correquisito | nenhum | FGA0073 | `( FGA0073 )` | — |
| FGA0073 Teoria de Eletrônica Digital 1 | pré-requisito | nenhum | MAT0031 | `( ( MAT0031 ) )` | — |
| FGA0160 Métodos Numéricos para Engenharia | pré-requisito | MAT0026 | (FGA0127 ou MAT0026) | `( MAT0026 ) OU ( FGA0127 )` | FGA0127 |
| FGA0108 Matemática Discreta 2 | pré-requisito | FGA0085 | (FGA0085 ou FGA0159) | `( ( FGA0085 ) OU ( FGA0159 ) )` | FGA0159 |
| FGA0142 Fundamentos de Arquiteturas de Computadores | pré-requisito | FGA0073 | (ENE0277 ou FGA0071) e (ENE0277 ou FGA0073) | `( ( ENE0277 ) OU ( FGA0071 E FGA0073 ) )` | ENE0277 |
| FGA0003 Compiladores 1 | pré-requisito | nenhum | FGA0146 | `( ( FGA0147 ) OU ( FGA0146 ) )` | — |
| FGA0030 Estruturas de Dados 2 | pré-requisito | FGA0146 | (CIC0090 ou FGA0120 ou FGA0146) | `( ( FGA0147 ) OU ( FGA0146 ) OU ( FGA0120 ) OU ( CIC0090 ) )` | CIC0090, FGA0120 |
| FGA0137 Sistemas de Banco de Dados 1 | pré-requisito | nenhum | (FGA0108 ou FGA0159) | `( ( FGA0159 ) OU ( FGA0108 ) )` | FGA0159 |
| FGA0170 Fundamentos de Sistemas Operacionais | pré-requisito | FGA0142 | (FGA0096 ou FGA0142 ou FGA0182) | `( ( FGA0182 ) OU ( FGA0096 ) OU ( FGA0142 ) )` | FGA0096, FGA0182 |
| FGA0173 Interação Humano Computador | pré-requisito | nenhum | FGA0312 | `( ( FGA0138 OU FGA0312 ) )` | — |
| FGA0124 Projeto e Análise de Algoritmos | pré-requisito | FGA0030 | FGA0146 | `( ( FGA0147 ) OU ( FGA0146 ) )` | — |
| FGA0208 Arquitetura e Desenho de Software | pré-requisito | nenhum | FGA0313 | `( ( FGA0172 OU FGA0313 ) )` | — |
| FGA0315 Qualidade de Software 1 | pré-requisito | nenhum | FGA0173 e FGA0307 | `( ( FGA0173 ) E ( FGA0184 OU FGA0307 ) )` | — |
| FGA0103 Fundamentos de Sistemas Embarcados | pré-requisito | nenhum | (FGA0096 ou FGA0170 ou FGA0182) | `( ( FGA0096 ) OU ( FGA0182 ) OU ( FGA0170 ) )` | FGA0096, FGA0182 |
| FGA0210 Paradigmas de Programação | pré-requisito | nenhum | FGA0003 e FGA0158 | `( ( FGA0158 E FGA0003 ) )` | — |
| FGA0242 Técnicas de Programação em Plataformas Emergentes | pré-requisito | nenhum | FGA0208 e FGA0314 | `( ( FGA0208 ) E ( FGA0238 OU FGA0314 ) )` | — |
| FGA0244 Programação para Sistemas Paralelos e Distribuídos | pré-requisito | FGA0211 | FGA0030 e FGA0211 | `( ( FGA0211 E FGA0030 ) )` | — |

<p class="legenda">Tabela 3. Relações em que o SIGAA e o grafo curricular discordam. "Fora do currículo" lista os códigos da expressão que não pertencem à matriz de Software, em geral alternativas de outros cursos.</p>

Há três tipos de diferença. O mais comum (14 casos) é um **requisito que o fluxograma não
desenha**, como Compiladores 1 exigir Estruturas de Dados 1; um deles é o correquisito entre
Prática e Teoria de Eletrônica Digital 1. Em cinco casos o grafo já tem a relação, mas o SIGAA
aceita **outras disciplinas como alternativa**, quase sempre de outro curso.
Um caso é **conflito de fato**: para Projeto e Análise de Algoritmos (FGA0124), o grafo diz
Estruturas de Dados 2 e o SIGAA diz Estruturas de Dados 1.

O grafo **não foi alterado** nesta mudança. A própria transcrição F16 avisa que "a lista oficial
de pré-requisitos de cada disciplina é a do SIGAA". Usar o SIGAA como fonte do grafo é uma
decisão de produto, e mexe no componente que o PR #89 está refatorando. Até lá, o grafo continua
saindo do fluxograma, e o relatório mostra exatamente o que falta nele.

## Catálogo e reindexação (issue #53)

**Política.** Cardápio não entra no índice: a semana corrente é servida pelo
`cardapio_semanal.json`, e `python -m rumo_rag ingerir` pula todo documento `tipo: cardapio`. Por
isso não há chunk de cardápio duplicado. A oferta de turmas segue a mesma ideia: só o semestre
corrente fica no catálogo. Quando o comando grava um semestre novo, ele avisa se a entrada do
anterior ainda está lá, e ela deve sair no mesmo PR.

**De onde vem a contagem de chunks.** A API da Entrega 3 servia 1.738 chunks. Cada mudança
desde então tem explicação:

| Mudança | Commit | Chunks |
|---|---|---|
| Base das Entregas 2 e 3 (36 fontes) | `2759405` | 1.738 |
| Cardápios antigos F08 e F09 saem do índice | `9492ce6` | 1.708 (−30) |
| Alergênicos por prato (#55) | `9ac3b9d` | 1.742 (+34) |
| 18 documentos da DDS sobre assistência estudantil | `d820488` | 1.950 (+208) |
| Integração do cardápio estruturado (#54, #55) | `14578c3` | 1.954 (+4) |
| Calendário 2026.2, feriados (F57) e verão 2027 (F58) | `54dc916` | 1.964 (+10) |
| Oferta de turmas 2026.2 (F59, esta mudança) | — | 2.001 (+37) |

<p class="legenda">Tabela 4. Evolução do número de chunks em <code>rag/dados/chunks.jsonl</code>, da Entrega 3 até a F59.</p>

Na regeneração, nenhum chunk das outras fontes mudou de conteúdo. Só a fronteira entre dois
trechos do F16 andou duas palavras, porque o arquivo tinha sido ajustado à mão no PR #88.

**Sem regressão.** A busca léxica (BM25) é a que roda na API publicada. Ela foi medida nas 32
perguntas de teste antes e depois da F59:

| Busca BM25 | Hit@1 | Hit@5 | MRR |
|---|---|---|---|
| Antes (1.964 chunks) | 0,906 | 1,000 | 0,936 |
| Primeira versão da F59 (uma seção por disciplina) | 0,906 | 0,969 | 0,924 |
| Versão final da F59 (2.001 chunks) | 0,906 | 1,000 | 0,936 |

<p class="legenda">Tabela 5. Recuperação BM25 nas 32 perguntas de teste antes e depois da oferta de turmas (<code>python -m rumo_rag avaliar --modo bm25</code>).</p>

A primeira versão piorou duas perguntas. Na Q24 ("Quantas vagas a FCTE oferta para Engenharia
de Software?"), os cinco primeiros resultados viraram trechos de turma, porque cada linha
repetia "FCTE" e o título dizia "Oferta de turmas". Na Q10, os 133 trechos curtos baixaram o
tamanho médio do BM25 e uma resposta desceu uma posição. A versão final usa um título seco e
junta várias disciplinas por trecho. Com isso, os resultados ficaram iguais aos de antes e a F59
não aparece entre os cinco primeiros de nenhuma das 32 perguntas.

A branch `chore/scripts-rag-local`, citada na #53, já foi mergeada: o commit dela (`18a6cdb`,
com `rag/indexar_chunks.py`) está na `main`, e a branch não existe mais no repositório.

A busca densa e a híbrida não foram medidas, porque recalcular os embeddings pede GPU. O
`ingerir` completo, com ChromaDB, precisa rodar numa máquina com GPU antes de publicar o índice
híbrido.

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 26/11/2026 | 1.0 | Coleta da oferta de turmas (#56) e dos pré-requisitos (#52) no SIGAA público, política de reindexação e medição sem regressão (#53) | Maykon Soares |
