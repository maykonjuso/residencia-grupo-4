# Entregas e versões

A **Tabela 1** apresenta o histórico de versões e entregas publicadas nesta GitPage.

| Versão | Data | Entrega | Conteúdo |
|---|---|---|---|
| 1.0 | Semana 1 | [Entrega 1 · Definições do projeto](../entrega-1/index.md) | Problema, partes interessadas, escopo, riscos, métricas, Essential Question e divisão com o Grupo 09 |
| 2.0 | 09/11/2026 | [Entrega 2 · Base de conhecimento + protótipo de RAG](../entrega-2/index.md) | 36 fontes, chunking, embeddings, ChromaDB, busca híbrida, LLM local, demonstração com fontes, avaliação e diagrama animado de integração |
| 3.0 | 13/11/2026 | [Entrega 3 · Respostas baseadas em evidências](../entrega-3/index.md) | Comparação empírica com e sem RAG nas 32 perguntas-ouro, fidelidade, alucinação, análise de falha e reescrita de consulta |

<p class="legenda">Tabela 1. Histórico de versões desta GitPage.</p>

Envio: os artefatos também vão para a pasta da equipe no Teams, canal **Segundo Desafio**, como pede o enunciado.

## Como gerar o PDF de cada entrega (para o Teams)

A página inicial de cada entrega ([`entrega-1/`](../entrega-1/index.md), [`entrega-2/`](../entrega-2/index.md) e futuras `entrega-N/`) exibe automaticamente no final da página o botão **📄 Gerar PDF consolidado desta Entrega (A4)**.

Ao clicar no botão, o script [`rumo.js`](../javascripts/rumo.js) lê automaticamente os links da entrega no menu lateral, busca todas as subpáginas daquela entrega na ordem do `nav`, remove seções interativas que dependem de JavaScript (como o explorador dinâmico de respostas e diagramas animados), renderiza os diagramas Mermaid proporcionalmente para folha A4, expande abas e blocos recolhidos e abre a janela de impressão/PDF do navegador — sem precisar criar arquivos `.md` extras nem editar scripts nas próximas entregas.

### Passo a passo para exportar

1. Acesse a página inicial da entrega desejada (localmente em `mkdocs serve` ou na GitPage publicada):
   - **Entrega 1:** [`/entrega-1/`](../entrega-1/index.md)
   - **Entrega 2:** [`/entrega-2/`](../entrega-2/index.md)
   - **Entrega 3:** [`/entrega-3/`](../entrega-3/index.md)
2. Role até o final da página e clique no botão **📄 Gerar PDF consolidado desta Entrega (A4)**.
3. Na janela de impressão do navegador, confirme:
   - **Destino:** Salvar como PDF
   - **Tamanho do papel:** A4
   - **Margens:** Padrão
   - **Gráficos de segundo plano:** Ativado (para preservar as cores institucionais da UnB nos cabeçalhos de tabela e diagramas)

!!! info "Exportação consolidada da Entrega 3 para o Teams (Issue #21)"
    Para o envio no canal **Segundo Desafio** do Microsoft Teams, o mecanismo do `rumo.js` compila automaticamente as quatro páginas da Entrega 3 ([`index.md`](../entrega-3/index.md), [`llm-vs-rag.md`](../entrega-3/llm-vs-rag.md), [`fidelidade-e-alucinacao.md`](../entrega-3/fidelidade-e-alucinacao.md) e [`reescrita-de-consulta.md`](../entrega-3/reescrita-de-consulta.md)) em um único documento paginado contínuo. Ele expande automaticamente a tabela de 32 perguntas pareadas (Tabela 4), desdobra blocos recolhidos (`details`), ajusta diagramas de arquitetura Mermaid e preserva cabeçalhos e formatações A4 sem exigir qualquer edição manual externa.

!!! warning "Regra de fonte única"
    O PDF enviado ao Teams é sempre **derivado** do Markdown desta GitPage. Nunca edite o PDF ou um arquivo Word separadamente: qualquer correção deve ser feita nos arquivos `.md` da entrega e reexportada pelo botão da página inicial da entrega.

### Tratamentos automáticos aplicados na impressão (`@media print`)

- **Abas (`===`):** todas as abas de blocos `pymdownx.tabbed` (como os casos especiais em *Estratégia de chunking*) são expandidas automaticamente em sequência com seus respectivos títulos.
- **Blocos recolhidos (`???`):** elementos `<details>` são abertos automaticamente antes da impressão (incluindo a Tabela 4 da Entrega 3 com as 32 perguntas-ouro).
- **Componentes interativos:** o widget interativo `#rm-explorador` é ocultado no papel, mantendo na sequência a seção *Consultas completas* com as 8 saídas estáticas completas.
- **Diagramas Mermaid e tabelas largas:** diagramas são dimensionados para caber na folha A4 sem quebra interna, e tabelas extensas (como o catálogo das 36 fontes e a matriz das 32 perguntas) ajustam fonte e quebra de linha automaticamente.
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

## Registro de mudanças da Entrega 3

A **Tabela 3** resume as principais decisões técnicas tomadas durante o planejamento e execução da Entrega 3, apresentando a motivação e o impacto medido ou esperado de cada uma.

| Mudança | Motivo | Efeito medido |
|---|---|---|
| Avaliação local nativa (`valores_sem_fonte` + juiz local) em vez de DeepEval | DeepEval exigia chamadas a APIs externas (violando RNF02) ou gerava risco de OOM na GPU de 8 GB | Pipeline 100% autônomo e auditável com zero envio de dados externos e custo computacional determinístico |
| Comparação sistemática Sem RAG × Com RAG nas 32 perguntas | Quantificar a redução de alucinações observada qualitativamente na Entrega 2 | Taxa de alucinação de dados críticos reduzida de 0,26 para 0,00 e fidelidade factual elevada de 0,00 para 0,97 em GPU L4 |
| Decomposição em subconsultas para perguntas compostas | Consultas multi-hop recuperavam apenas o tópico dominante no embedding por atração ao ponto médio | Reescrita em 2 estágios em GPU (`LiquidAI/d1-omni-600M` + `Qwen2.5-7B`) recupera múltiplos eixos informacionais (ex.: C01 e C04 com 100% de cobertura e fidelidade 1.0) |
| Documentação explícita de limitação em grafos transitivos | RAG em texto puro falha em deduzir cadeias longas de pré-requisitos em cascata | Justificativa técnica para ferramenta determinística em grafo no Agente Fluxo (Entrega 4) |
| Purga estrita de métricas de latência do benchmark comparativo (Requisito R3) | Focar a avaliação comparativa exclusivamente em qualidade, fundamentação e precisão semântica | Conformidade estrita com R3 e priorização de métricas semânticas e factuais (ALCE = 0,92, RAGAS = 0,97, Completude = 0,90) |
| Automação Google Colab com auto-tuning de VRAM | Permitir inferência física em hardware de alta capacidade (L4 / A100 / H100) com precisão FP16/BF16 ou fallback 4-bit | Execução em GPU NVIDIA L4 de 24 GB via script autônomo e notebook 1-Click com limiar calibrado |

<p class="legenda">Tabela 3. Decisões tomadas ao longo da Entrega 3, cada uma com motivo e efeito.</p>

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 09/11/2026 | 2.0 | Publicação da Entrega 2 e registro de mudanças | Maykon Soares |
    | 11/11/2026 | 3.0 | Inclusão da versão 3.0 (Entrega 3) e registro de decisões técnicas | Grupo 04 |
    | 13/11/2026 | 3.0 | Consolidação das decisões da Entrega 3, guia de exportação em PDF único (Issue #21) e purga de latência (R3) | Grupo 04 |
