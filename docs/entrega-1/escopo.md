# Escopo e requisitos

## Dentro do escopo

- **RU do campus Gama:** preços por grupo de usuário, gratuidade e Auxílio Alimentação, horários, como acessar (carteirinha digital), cardápio semanal (café, almoço e jantar), regimento.
- **Fluxo de disciplinas da FCTE:** grades e pré-requisitos das cinco engenharias de graduação, informações do PPGEB, ingresso pela ABI, calendário 2026.2, matrícula no SIGAA, trancamento, regimentos da UnB e da FCTE.
- **Apoio:** Guia Alimentar para a População Brasileira e o guia da ANVISA sobre alergênicos, para perguntas gerais de alimentação.

## Fora do escopo (nesta fase)

- Dados pessoais do estudante (histórico, IRA, matrícula): o RUmo **não acessa o SIGAA** nem pede login.
- Outros campi: o RU Darcy Ribeiro, Ceilândia e Planaltina aparecem na base só porque estão nos mesmos documentos.
- Recomendação nutricional individual ou dieta: o RUmo informa o cardápio, não prescreve.
- Mapeamento de salas e rotas: é do [Grupo 09](../visao/escopo-grupos.md).

## Requisitos funcionais

| ID | Requisito | Entrega |
|---|---|---|
| RF01 | Responder perguntas em português sobre o RU e o fluxo de disciplinas | 2 |
| RF02 | Recuperar os trechos mais relevantes de uma base de documentos oficiais | 2 |
| RF03 | Citar, em cada resposta, os trechos usados (documento, página e URL) | 2 |
| RF04 | Responder "Não encontrei essa informação nas fontes da base" quando não houver base | 2 |
| RF05 | Ler cardápios em PDF como tabela, separando refeição e dia | 2 |
| RF06 | Expor `POST /perguntar` no contrato comum com o Grupo 09 | 4 |
| RF07 | Receber foto de prato ou cardápio e identificar os componentes | 5 |
| RF08 | Atualizar o cardápio semanal automaticamente | 6 |

<p class="legenda">Tabela 1. Requisitos funcionais e entrega prevista.</p>

## Requisitos não funcionais

| ID | Requisito | Como verificar |
|---|---|---|
| RNF01 | Usar só fontes oficiais, com URL e data de coleta | [Catálogo](../entrega-2/base-de-conhecimento.md) |
| RNF02 | Rodar localmente, sem enviar perguntas a serviços externos (padrão) | LLM e embeddings locais; API externa só se configurada |
| RNF03 | Busca em menos de 1 s; resposta completa em menos de 30 s numa GPU de 8 GB | Tempos registrados na [demonstração](../entrega-2/demonstracao.md) |
| RNF04 | Reprodutível: um comando refaz a base e o índice | `python -m rumo_rag ingerir` |
| RNF05 | Identidade visual da UnB, comum com o Grupo 09 | Esta GitPage |
| RNF06 | Não coletar dados pessoais (LGPD) | Sem login e sem registro de identidade |

<p class="legenda">Tabela 2. Requisitos não funcionais.</p>
