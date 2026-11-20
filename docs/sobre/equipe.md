# Equipe

**Grupo 04** · Turma 1 · Sala 313 (planilha *Grupos Challenge 2*).

## Papéis

O projeto roda em **Scrum adaptado**, que tem três responsabilidades: Product Owner, Scrum
Master e desenvolvedores. Todas as cinco pessoas são desenvolvedoras — quem acumula PO ou
Scrum Master também desenvolve. Além do papel, cada pessoa é dona de um componente do
sistema, para que nenhuma parte fique sem responsável.

| Integrante | GitHub | Papel | Componente |
|---|---|---|---|
| Maykon Júnio dos Santos Soares | [@maykonjuso](https://github.com/maykonjuso) | Product Owner e dev | GitPage e integração |
| Gabriel Maciel Araújo | [@GabrielMacielBR](https://github.com/GabrielMacielBR) | Scrum Master e dev | Base de conhecimento |
| Kyara Esteves de Sousa | [@Kyara2](https://github.com/Kyara2) | Dev | Geração |
| Keila Alves Ferreira | [@keilogger](https://github.com/keilogger) | Dev | Recuperação |
| Gabriella Oliveira de Souza Dias | [@Gabizinha88](https://github.com/Gabizinha88) | Dev | Avaliação |

<p class="legenda">Tabela 1. Papéis e componentes do Grupo 04, definidos na Semana 3.</p>

## O que cada componente cuida

| Componente | Responsabilidade | Onde fica |
|---|---|---|
| Base de conhecimento | Catálogo das 54 fontes oficiais (53 indexadas em RAG + cardápio semanal estruturado), extração dos PDFs e estratégia de chunking | `rag/catalogo.yaml`, `rag/rumo_rag/extracao.py`, `chunking.py`, `cardapio.py` |
| Recuperação | Embeddings, banco vetorial e busca híbrida | `rag/rumo_rag/indice.py` |
| Geração | Prompt, LLM (local ou OpenRouter), citação das fontes e recusa fora da base | `rag/rumo_rag/geracao.py` |
| Avaliação | Perguntas-ouro, métricas de recuperação, fidelidade e alucinação | `rag/avaliacao/` |
| GitPage e integração | Documentação, diagramas e contrato de API com o Grupo 09 | `docs/`, `mkdocs.yml`, `rag/rumo_rag/api.py` |

<p class="legenda">Tabela 2. Componentes do RUmo e quem responde por cada um.</p>

Ser dono de um componente não significa fazer sozinho tudo o que o toca: a revisão da
documentação, por exemplo, é distribuída entre as cinco pessoas de propósito, porque é a
forma mais barata de o grupo inteiro entender o sistema.

## Contribuições por entrega

| Integrante | Entrega 1 | Entrega 2 | Entrega 3 | Entrega 4 |
|---|---|---|---|---|
| Maykon Júnio dos Santos Soares | Estrutura inicial da GitPage (`MkDocs Material`, identidade UnB/FCTE), definições do projeto (problema, stakeholders, MVP, RF01–RF08, riscos, métricas, divisão com G09) e papéis (`#5`, `#6`, `#10`, PR `#22`) | Curadoria inicial da base e protótipo do RAG (ingestão, busca híbrida, demonstração), esteira animada do RAG (PR `#1`), scripts locais de reindexação e consistência numérica (`#16`) | API `POST /perguntar` (contrato v1.0 com G09), autenticação por token e deploy no Render (PR `#35`); apoio à publicação e exportação para o Teams (`#20`, `#21`) | Frente de coleta e gestão do backlog: especificação do Épico `#37` e da frente de coleta (`#38`, `#52`, `#53`, `#56`), gestão das issues e integração contínua com o Grupo 09 |
| Gabriel Maciel Araújo | Processo de trabalho do grupo, critérios DoR/DoD e template padrão de Pull Request (`#7`, `#8`, PR `#27`) | Revisão completa da Entrega 2 (`#13`, `#15`, PR `#24`), gerador de PDF A4 consolidado na GitPage (`rumo.js`), ajustes de diagramas Mermaid e correção do explorador interativo (`#25`) | Comparação LLM × RAG nas 32 perguntas-ouro, métricas RAGAS/ALCE/RGB, reescrita multi-hop em 2 estágios (`d1-omni-600M` + `Qwen2.5-7B`), benchmark em GPU (Colab L4) e documentação (`#4`, `#28`–`#31`, PRs `#32`, `#36`) | Frente de entregas: `Orquestrador`, paralelismo, roteamento híbrido, `AgenteValidador` ativo (`#42`, `#43`), testes automatizados (`#45`), API v1.0 multiagente/Vercel (`#44`), integração `cardapio_semanal.json` + alergênicos + 18 fontes DDS (`#53`–`#55`), documentação e publicação (`#46`, `#48`, PRs `#71`, `#74`, `#79`) |
| Kyara Esteves de Sousa | Formalização das regras de negócio RN-01 a RN-05 (`#9`, PR `#26`) | Apoio na curadoria da base e especificação das regras de geração, citação e recusa fora da base | Implementação da geração pareada sem RAG vs. com RAG nas perguntas-ouro (`#17`, PR `#34`) | Frente de coleta: scraper do cardápio semanal do RU Gama (`#50`, PR `#73`), estruturação do cardápio por compartimento e trilha alimentar em JSON (`#54`, PR `#70`) e perfil leve no navegador (`#66`, PR `#72`) |
| Keila Alves Ferreira | Revisão das páginas da Entrega 1 e da seção Visão do projeto (`#11`, `#12`) | Apoio na validação da estratégia de recuperação e busca híbrida da base de conhecimento | Especificação e acompanhamento da reescrita de consulta para perguntas compostas (`#19`) | Frente de entregas: camada de agentes (`Agente`, `Mensagem`, `Resposta`, `Trace`, `#40`), implementação inicial do `AgenteRU` e do `AgenteFluxo` (`#41`, PRs `#68`, `#69`), atualização da documentação/demonstração multiagente (`#46`, `#47`, PR `#77`) e protótipo do grafo de pré-requisitos (`#61`) |
| Gabriella Oliveira de Souza Dias | Revisão da página inicial e da seção Sobre (`#14`) | Apoio na curadoria das perguntas de teste e critérios de avaliação da recuperação | Acompanhamento das métricas de fidelidade factual e taxa de alucinação (`#18`) | Frente de coleta: correção da recuperação de preço do RU no BM25 com sinônimos (`#51`, PR `#67`) e extração/integração de alergênicos por prato no cardápio estruturado (`#55`, PR `#78`) |

<p class="legenda">Tabela 3. Contribuição de cada integrante nas Entregas 1 a 4 (na Semana 4, o grupo dividiu-se em frente de entregas — Gabriel e Keila — e frente de coleta — Maykon, Kyara e Gabriella).</p>

## Grupo parceiro

**Grupo 09** · Turma 1 · Container: Iasmin Morena Vitor Marques, João Vítor Carvalho Barbosa, Ketlyn Karen Silva de Morais, Luan da Silva Feres e Pedro Henrique Muniz de Oliveira. Tema: mapeamento da FCTE. Veja a [divisão de responsabilidades](../visao/escopo-grupos.md).

## Mentoria

Mentor do Challenge 2: Jefferson Viana Fonseca Abreu.

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 09/11/2026 | 1.1 | Papéis e componentes definidos; tabela de contribuições por entrega | Maykon Soares |
    | 18/11/2026 | 1.2 | Catálogo passa a 37 fontes (Issue #55) | Grupo 04 |
    | 20/11/2026 | 1.3 | Preenchimento da Tabela 3 (Entregas 1 a 4) e atualização da base para 54 fontes (Issue #48) | Grupo 04 |
