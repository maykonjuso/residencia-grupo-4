# Escopo e requisitos

## MVP

> **O RUmo responde, em português, perguntas sobre o RU e o fluxo de disciplinas da FCTE
> usando só documentos oficiais da UnB, cita documento, página e URL em cada resposta, e
> recusa o que não está na base.**

Isso é RF01 a RF05, e foi **atingido na Entrega 2**: o protótipo responde pela linha de
comando, com fontes, e recusa fora da base. O que vem depois são os entregáveis das Semanas
4 a 7, não o mínimo do produto.

!!! warning "Prioridade de produto × obrigação de cronograma"
    As duas coisas não coincidem, e misturá-las confunde a leitura. A coluna **Prioridade**
    abaixo é o valor para quem usa o RUmo. A coluna **Obrigatório** marca o que o Challenge 2
    exige em determinada semana, independente disso.

    O caso claro é o RF07 (foto do prato): para o estudante que quer saber o preço do almoço
    é um extra — `could` por valor de produto. Como entregável da Semana 5, é obrigatório.
    O grupo entrega os dois conjuntos; a tabela só deixa de fingir que são a mesma coisa.

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

| ID | Requisito | Prioridade | Entrega | Obrigatório | Situação |
|---|---|---|---|---|---|
| RF01 | Responder perguntas em português sobre o RU e o fluxo de disciplinas | must · MVP | 2 | Semana 2 | entregue |
| RF02 | Recuperar os trechos mais relevantes de uma base de documentos oficiais | must · MVP | 2 | Semana 2 | entregue |
| RF03 | Citar, em cada resposta, os trechos usados (documento, página e URL) | must · MVP | 2 | Semana 2 | entregue |
| RF04 | Responder "Não encontrei essa informação nas fontes da base" quando não houver base | must · MVP | 2 | Semana 2 | entregue |
| RF05 | Ler cardápios em PDF como tabela, separando refeição e dia | must · MVP | 2 | Semana 2 | entregue |
| RF06 | Expor `POST /perguntar` no contrato comum com o Grupo 09 | should | 4 | Semana 4 | planejado |
| RF07 | Receber foto de prato ou cardápio e identificar os componentes | could | 5 | Semana 5 | planejado |
| RF08 | Atualizar o cardápio semanal automaticamente | should | 6 | Semana 6 | planejado |

<p class="legenda">Tabela 1. Requisitos funcionais. <strong>Prioridade</strong> é o valor para quem usa o RUmo; <strong>Obrigatório</strong> é a semana em que o Challenge 2 cobra o entregável. RF01–RF05 formam o MVP.</p>

## Requisitos não funcionais

| ID | Requisito | Como verificar |
|---|---|---|
| RNF01 | Usar só fontes oficiais, com URL e data de coleta | [Catálogo](../entrega-2/base-de-conhecimento.md) |
| RNF02 | Rodar localmente, sem enviar perguntas a serviços externos (padrão) | LLM e embeddings locais; API externa só se configurada |
| RNF03 | Busca em menos de 1 s; resposta completa em menos de 30 s numa GPU de 8 GB | Tempos registrados na [demonstração](../entrega-2/demonstracao.md) |
| RNF04 | Reprodutível: um comando refaz a base e o índice | `python -m rumo_rag ingerir` |
| RNF05 | Identidade visual da UnB, comum com o Grupo 09 | Esta GitPage |
| RNF06 | Não coletar dados pessoais (LGPD) | Sem login e sem registro de identidade |

<p class="legenda">Tabela 2. Requisitos não funcionais. RNF01, RNF02 e RNF06 são <strong>must</strong>: sustentam as regras de negócio do RUmo (só fonte oficial, nada sai para serviço externo, nenhum dado pessoal). Os outros três são <strong>should</strong>.</p>

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 09/11/2026 | 1.1 | Declara o MVP, prioriza RF01–RF08 e separa valor de produto de obrigação de cronograma | Maykon Soares |
