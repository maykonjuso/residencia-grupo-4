# Entrega 4 — Primeiro Protótipo Multiagente

A **Entrega 4** (Épico `#37`, requisitos **RF01** e **RF02**) marca a evolução do **RUmo** de um pipeline RAG linear para o primeiro **protótipo de Sistema Multiagente**, combinando classificação e decomposição de consultas em dois estágios, roteamento híbrido por domínio, execução paralela de agentes especialistas, validação factual com retorno ao sintetizador e composição com índices de citação isolados.

!!! info "Escopo atual do protótipo"
    Esta documentação reflete estritamente o que está implementado e executado no repositório (`rag/rumo_rag/`). Detalhes exclusivos dos agentes especialistas e ferramentas ainda em aberto nas issues **#41**, **#42** e **#43** estão marcados explicitamente como `[a preencher]` ou `[a detalhar]`.

---

## O que é a Entrega 4

O objetivo do protótipo é responder a perguntas simples ou compostas de estudantes da UnB (Campus Gama / FCTE) sobre o **Restaurante Universitário (RU)** e o **Fluxo de Graduação**, dividindo o trabalho entre agentes com papéis definidos e garantindo rastreabilidade das fontes exigida pelo contrato com o portal (`consultas_rag.py` / `POST /perguntar`).

A **Tabela 1** resume o estado atual da entrega entre o que foi implementado, o que aguarda detalhamento e o que ficou fora do escopo desta etapa.

| Categoria | Item / Componente | Situação | Observação |
|---|---|---|---|
| **Implementado** | Estrutura base de agentes (`rag/rumo_rag/agentes.py`) | Concluído | Classes `AgenteBase`, `AgenteRU`, `AgenteFluxo`, `AgenteValidador`, `Sintetizador` e `Orquestrador` |
| **Implementado** | Classificação e decomposição (`rag/rumo_rag/reescrita.py`) | Concluído | Estágio 1 (`d1-omni-600M`, limiar `0.39`) + Estágio 2 LLM conjunto (`decompor_com_roteamento`) e fallback sintático |
| **Implementado** | Roteamento híbrido (`rotear_subpergunta`) | Concluído | Cascata `Teste 1 (eixo LLM)` → `Regex` → `Teste 2 (d1-omni-600M)` |
| **Implementado** | Execução paralela e degradação graciosa | Concluído | `ThreadPoolExecutor` com `_LOCK_BUSCA` e `--falhar-agente` para simulação de falhas |
| **Implementado** | Validador factual e retorno ao sintetizador | Concluído | `AgenteValidador.validar` + `Sintetizador.processar_devolucao` e composição com `[n]` isolados por parte |
| **Implementado** | Experimento comparativo de roteamento (`perguntas_roteamento_multiplas.jsonl`) | Concluído | Comparação Regex vs. LLM conjunto (Teste 1) vs. `d1-omni-600M` (Teste 2) em 8 consultas / 17 subperguntas |
| **Aberto (`#41`, `#42`, `#43`)** | Prompts dedicados, regras de domínio e ferramentas específicas de `AgenteRU`, `AgenteFluxo` e `AgenteValidador` | `[a preencher]` | Estrutura e contratos prontos; especialização interna pendente das issues `#41`–`#43` |
| **Aberto (`#41`, `#42`, `#43`)** | Demonstração completa com modelo generativo LLM nos agentes finalizados | `[a preencher]` | Traces atuais executados com `--backend extrativo`; trace generativo final aguarda `#41`–`#43` |
| **Fora de escopo** | Integração em tempo real com API externa do Portal Único (Grupo 09) | Fora da entrega | Escopo do projeto unificado documentado em [Escopo entre Grupos](../visao/escopo-grupos.md) |
| **Fora de escopo** | Memória conversacional persistente multi-turno e autenticação SIGAA | Fora da entrega | Cada chamada ao `Orquestrador.executar` é stateless |

<p class="legenda">Tabela 1. Escopo implementado, pendências e itens fora da Entrega 4.</p>

---

## Navegação da Entrega 4

A documentação desta entrega segue os artefatos solicitados no enunciado e está organizada conforme a **Tabela 2**.

| Página | Conteúdo principal |
|---|---|
| [Arquitetura dos Agentes](arquitetura-agentes.md) | Diagrama Mermaid verticalizado dos agentes e conexões, além dos contratos de saída em código |
| [Responsabilidades dos Agentes](responsabilidades.md) | Tabela com papel, responsabilidades, o que cada agente **pode** e **não pode** fazer, e regras de negócio |
| [Fluxo de Interação e Roteamento](fluxo-de-interacao.md) | Diagrama de sequência de pergunta composta, mensagens trocadas e relatório comparativo de classificação/roteamento |
| [Demonstração Executada](demonstracao.md) | Comandos executados, traces reais (`--agentes --trace`), retorno do validador e simulação de falha |

<p class="legenda">Tabela 2. Estrutura de páginas da documentação da Entrega 4.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Versão inicial da documentação da Entrega 4 | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Refatoração para a estrutura padronizada (index, arquitetura, responsabilidades, fluxo de interação e demonstração) com marcação explícita de pendências | @maykonjuso |
