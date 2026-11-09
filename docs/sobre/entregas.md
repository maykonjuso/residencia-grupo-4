# Entregas e versões

| Versão | Data | Entrega | Conteúdo |
|---|---|---|---|
| 1.0 | Semana 1 | Entrega 1 · Definições do projeto | Problema, partes interessadas, escopo, riscos, métricas, Essential Question e divisão com o Grupo 09 |
| 2.0 | 09/11/2026 | Entrega 2 · Base de conhecimento + protótipo de RAG | 36 fontes, chunking, embeddings, ChromaDB, busca híbrida, LLM local, demonstração com fontes, avaliação e diagrama animado de integração |

<p class="legenda">Tabela 1. Histórico de versões desta GitPage.</p>

Envio: os artefatos também vão para a pasta da equipe no Teams, canal **Segundo Desafio**, como pede o enunciado.

## Como gerar o documento do Teams

O documento entregue no Teams é **gerado a partir desta GitPage**, nunca escrito à parte. Isso
garante que site e documento digam a mesma coisa em toda entrega.

```bash
pip install -r requirements-docs.txt
mkdocs build
open site/print_page/index.html     # no Linux: xdg-open
```

Na página aberta: **Imprimir** (`Cmd+P` ou `Ctrl+P`) → destino **Salvar como PDF** →
marcar *Imprimir imagens de fundo* (ou *Background graphics*) → salvar.

O plugin [`print-site`](https://timvink.github.io/mkdocs-print-site-plugin/) junta as 26 páginas
de conteúdo na ordem do `nav`, com capa e sumário. A página inicial fica de fora de propósito:
ela usa o template `home.html` e não tem título de primeiro nível, o que faria o
`mkdocs build --strict` do CI falhar.

!!! warning "Antes de subir, confira três coisas no PDF"
    As regras de impressão em `docs/stylesheets/extra.css` resolvem o essencial, mas o papel
    não reproduz tudo o que a tela faz:

    1. **O contrato `POST /perguntar`** (em *Divisão com o Grupo 09*) tem três abas —
       Requisição, Resposta e Sem base. No PDF elas saem **empilhadas**, na ordem dos títulos.
       Confira que as três apareceram: sem as regras de impressão, só a primeira sairia, e o
       contrato é conteúdo avaliado.
    2. **Os diagramas animados** não existem no papel. No lugar deles sai uma linha apontando
       para a versão online. Se o diagrama for essencial para a banca, inclua uma captura de
       tela na página.
    3. **Blocos recolhíveis** (como os históricos de revisão) devem sair abertos.

O PDF é **derivado**. Achou erro nele, corrija no Markdown e gere de novo — corrigir direto no
PDF ou no Word cria duas versões divergentes do mesmo documento.

## Registro de mudanças da Entrega 2

| Mudança | Motivo | Efeito medido |
|---|---|---|
| Qwen2.5-1.5B → Qwen2.5-7B (4 bits) | O 1,5B inventava preços e pratos | Sem alucinação nas perguntas da demonstração |
| Cardápio lido como tabela | Texto corrido misturava os dias | Um registro por refeição e por dia (15 por semana) |
| Subseções unidas à seção-mãe | O chunk de preço não dizia de qual grupo era | O chunk do Grupo II traz o grupo e os valores juntos |
| Datas e códigos como termo único no BM25 + peso 3 | O embedding não separava os dias do cardápio | Almoço de 11/11 passou a vir em 1º |
| multilingual-e5-base → bge-m3 | Comparação no conjunto de teste | Hit@1 (denso): 0,875 → 0,969 |
| Embeddings em fp16 | O bge-m3 em fp32 mais o LLM de 7B estouravam a GPU de 8 GB | Os dois cabem na mesma placa |

<p class="legenda">Tabela 2. Decisões tomadas ao longo da Entrega 2, cada uma com motivo e efeito.</p>
