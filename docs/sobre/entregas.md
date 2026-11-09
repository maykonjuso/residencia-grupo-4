# Entregas e versões

A **Tabela 1** apresenta o histórico de versões e entregas publicadas nesta GitPage.

| Versão | Data | Entrega | Conteúdo |
|---|---|---|---|
| 1.0 | Semana 1 | [Entrega 1 · Definições do projeto](../entrega-1/index.md) | Problema, partes interessadas, escopo, riscos, métricas, Essential Question e divisão com o Grupo 09 |
| 2.0 | 09/11/2026 | [Entrega 2 · Base de conhecimento + protótipo de RAG](../entrega-2/index.md) | 36 fontes, chunking, embeddings, ChromaDB, busca híbrida, LLM local, demonstração com fontes, avaliação e diagrama animado de integração |

<p class="legenda">Tabela 1. Histórico de versões desta GitPage.</p>

Envio: os artefatos também vão para a pasta da equipe no Teams, canal **Segundo Desafio**, como pede o enunciado.

## Como gerar o PDF de cada entrega (para o Teams)

A página inicial de cada entrega ([`entrega-1/`](../entrega-1/index.md), [`entrega-2/`](../entrega-2/index.md) e futuras `entrega-N/`) exibe automaticamente no final da página o botão **📄 Gerar PDF consolidado desta Entrega (A4)**.

Ao clicar no botão, o script [`rumo.js`](../javascripts/rumo.js) lê automaticamente os links da entrega no menu lateral, busca todas as subpáginas daquela entrega na ordem do `nav`, remove seções interativas que dependem de JavaScript (como o explorador dinâmico de respostas e diagramas animados), renderiza os diagramas Mermaid proporcionalmente para folha A4, expande abas e blocos recolhidos e abre a janela de impressão/PDF do navegador — sem precisar criar arquivos `.md` extras nem editar scripts nas próximas entregas.

### Passo a passo para exportar

1. Acesse a página inicial da entrega desejada (localmente em `mkdocs serve` ou na GitPage publicada):
   - **Entrega 1:** [`/entrega-1/`](../entrega-1/index.md)
   - **Entrega 2:** [`/entrega-2/`](../entrega-2/index.md)
2. Role até o final da página e clique no botão **📄 Gerar PDF consolidado desta Entrega (A4)**.
3. Na janela de impressão do navegador, confirme:
   - **Destino:** Salvar como PDF
   - **Tamanho do papel:** A4
   - **Margens:** Padrão
   - **Gráficos de segundo plano:** Ativado (para preservar as cores institucionais da UnB nos cabeçalhos de tabela e diagramas)

!!! warning "Regra de fonte única"
    O PDF enviado ao Teams é sempre **derivado** do Markdown desta GitPage. Nunca edite o PDF ou um arquivo Word separadamente: qualquer correção deve ser feita nos arquivos `.md` da entrega e reexportada pelo botão da página inicial da entrega.

### Tratamentos automáticos aplicados na impressão (`@media print`)

- **Abas (`===`):** todas as abas de blocos `pymdownx.tabbed` (como os casos especiais em *Estratégia de chunking*) são expandidas automaticamente em sequência com seus respectivos títulos.
- **Blocos recolhidos (`???`):** elementos `<details>` são abertos automaticamente antes da impressão.
- **Componentes interativos:** o widget interativo `#rm-explorador` é ocultado no papel, mantendo na sequência a seção *Consultas completas* com as 8 saídas estáticas completas.
- **Diagramas Mermaid e tabelas largas:** diagramas são dimensionados para caber na folha A4 sem quebra interna, e tabelas extensas (como o catálogo das 36 fontes) ajustam fonte e quebra de linha automaticamente.
- **Links internos:** links entre páginas da mesma entrega são convertidos em âncoras internas (`#secao`) dentro do próprio documento consolidado.

## Registro de mudanças da Entrega 2

A **Tabela 2** resume as principais decisões técnicas tomadas durante a evolução da Entrega 2 e o efeito medido em cada uma.

| Mudança | Motivo | Efeito medido |
|---|---|---|
| Qwen2.5-1.5B → Qwen2.5-7B (4 bits) | O 1,5B inventava preços e pratos | Sem alucinação nas perguntas da demonstração |
| Cardápio lido como tabela | Texto corrido misturava os dias | Um registro por refeição e por dia (15 por semana) |
| Subseções unidas à seção-mãe | O chunk de preço não dizia de qual grupo era | O chunk do Grupo II traz o grupo e os valores juntos |
| Datas e códigos como termo único no BM25 + peso 3 | O embedding não separava os dias do cardápio | Almoço de 11/11 passou a vir em 1º |
| multilingual-e5-base → bge-m3 | Comparação no conjunto de teste | Hit@1 (denso): 0,875 → 0,969 |
| Embeddings em fp16 | O bge-m3 em fp32 mais o LLM de 7B estouravam a GPU de 8 GB | Os dois cabem na mesma placa |

<p class="legenda">Tabela 2. Decisões tomadas ao longo da Entrega 2, cada uma com motivo e efeito.</p>
