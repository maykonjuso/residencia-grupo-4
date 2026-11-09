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
| Base de conhecimento | Catálogo das 36 fontes oficiais, extração dos PDFs e estratégia de chunking | `rag/catalogo.yaml`, `rag/rumo_rag/extracao.py`, `chunking.py` |
| Recuperação | Embeddings, banco vetorial e busca híbrida | `rag/rumo_rag/indice.py` |
| Geração | Prompt, LLM local, citação das fontes e recusa fora da base | `rag/rumo_rag/geracao.py` |
| Avaliação | Perguntas-ouro, métricas de recuperação, fidelidade e alucinação | `rag/avaliacao/` |
| GitPage e integração | Documentação, diagramas e contrato de API com o Grupo 09 | `docs/`, `mkdocs.yml` |

<p class="legenda">Tabela 2. Componentes do RUmo e quem responde por cada um.</p>

Ser dono de um componente não significa fazer sozinho tudo o que o toca: a revisão da
documentação, por exemplo, é distribuída entre as cinco pessoas de propósito, porque é a
forma mais barata de o grupo inteiro entender o sistema.

## Contribuições por entrega

| Integrante | Entrega 1 | Entrega 2 | Entrega 3 |
|---|---|---|---|
| Maykon Júnio dos Santos Soares | | | |
| Gabriel Maciel Araújo | | | |
| Kyara Esteves de Sousa | | | |
| Keila Alves Ferreira | | | |
| Gabriella Oliveira de Souza Dias | | | |

<p class="legenda">Tabela 3. Contribuição de cada integrante por entrega. A preencher pelo grupo.</p>

## Grupo parceiro

**Grupo 09** · Turma 1 · Container: Iasmin Morena Vitor Marques, João Vítor Carvalho Barbosa, Ketlyn Karen Silva de Morais, Luan da Silva Feres e Pedro Henrique Muniz de Oliveira. Tema: mapeamento da FCTE. Veja a [divisão de responsabilidades](../visao/escopo-grupos.md).

## Mentoria

Mentor do Challenge 2: Jefferson Viana Fonseca Abreu.

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 09/11/2026 | 1.1 | Papéis e componentes definidos; tabela de contribuições por entrega | Maykon Soares |
