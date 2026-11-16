# Entrega 4 · Primeiro Protótipo Multiagente

**Semana 4 do Challenge 2.** Foco: *sistema multiagentes colaborativo com especialização por domínio, orquestração paralela, validação factual e estudo comparativo de roteamento*.

!!! info "Envio e prazo da entrega"
    Prazo: **sexta-feira (20/11/2026)**. Os artefatos desta entrega também são exportados para a pasta da equipe no Microsoft Teams, canal **4_Second Challenge**.

---

## 1. Escopo da entrega

Nas Entregas 2 e 3, o RUmo executava toda consulta por meio de um único fluxo monolítico de busca e geração. Quando o estudante fazia uma pergunta composta cruzando temas distintos (por exemplo, cardápio do RU e pré-requisitos de disciplina), a busca competia pelos mesmos *slots* de contexto e o gerador misturava instruções.

Na **Entrega 4**, essa arquitetura evolui para um **Sistema Multiagentes** coordenado pelo [`Orquestrador`](https://github.com/maykonjuso/residencia-grupo-4/blob/main/rag/rumo_rag/agentes.py), com separação explícita de responsabilidades, execução paralela e auditoria factual automática antes da síntese final.

### Checklist de entregáveis

- [x] **Mínimo de 2 agentes especializados (+ agentes adicionais):** implementados `AgenteRU` (*Research Agent · Eixo RU*), `AgenteFluxo` (*Research Agent · Eixo Acadêmico/FCTE*), `AgenteValidador` (*Validation Agent · Fidelidade Factual e RN-02*), `Sintetizador` (*Analysis & Communication Agent · Reparo e composição com isolamento de `[n]`*) e `Orquestrador` em `rag/rumo_rag/agentes.py`. ([Ver arquitetura e responsabilidades](arquitetura-agentes.md))
- [x] **Diagrama da arquitetura e descrição de responsabilidades:** papéis, escopo documental, fluxograma de dados, contratos (`RespostaAgente` e `ResultadoValidacao`) e limites de cada agente. ([Ver arquitetura](arquitetura-agentes.md))
- [x] **Fluxo de interação, colaboração paralela e relatório de roteamento:** diagrama de sequência das interações, controle de concorrência e experimento comparando **Regex**, **LLM Conjunto (Teste 1)** e **`LiquidAI/d1-omni-600M` (Teste 2)** em perguntas múltiplas. ([Ver orquestração e relatório](orquestrador-e-roteamento.md))
- [x] **Demonstração de fluxo colaborativo completo:** execução real via CLI com `--agentes --trace`, comprovação de paralelismo (`tempo_paralelo_s < soma_tempos_individuais_s`), ciclo de devolução ao `Sintetizador` e degradação elegante (`--falhar-agente`). ([Ver demonstração](demonstracao-agentes.md))

---

## 2. Resumo dos agentes do sistema

A **Tabela 1** mapeia cada componente implementado em `rag/rumo_rag/agentes.py` para os papéis previstos na arquitetura multiagentes.

| Agente no RUmo | Papel clássico | Classe (`agentes.py`) | Responsabilidade central |
|---|---|---|---|
| **Orquestrador** | *Orchestrator / Router* | `Orquestrador` | Classifica e decompõe a consulta (`reescrita.py`), roteia cada subpergunta ao domínio adequado, dispara buscas/gerações em paralelo (`ThreadPoolExecutor`) e coordena validação e síntese |
| **Agente RU** | *Research Agent* (Domínio RU) | `AgenteRU` | Recupera chunks restritos a `eixo="ru"` (com fallback em `apoio`) e gera resposta fundamentada com citações `[n]` locais sobre preços, cardápio, horários, alergênicos e auxílio |
| **Agente Fluxo** | *Research Agent* (Domínio FCTE) | `AgenteFluxo` | Recupera chunks restritos a `eixo="fluxo"` (com fallback em `apoio`) e gera resposta com citações `[n]` locais sobre grades, pré-requisitos, PPCs, trancamento e pós-graduação |
| **Agente Validador** | *Validation Agent* | `AgenteValidador` | Audita cada `RespostaAgente` contra os trechos recuperados (`valores_sem_fonte` e `resposta_sem_citacao` da RN-02); reprova e devolve ao `Sintetizador` quando encontra inconsistência |
| **Sintetizador** | *Analysis & Communication Agent* | `Sintetizador` | Trata devoluções do `AgenteValidador` (aplicando `fallback_extrativo` ou sinalização factual) e compõe a resposta final mantendo os índices `[n]` isolados por parte (regra contratual) |

<p class="legenda">Tabela 1. Papéis, classes e responsabilidades dos agentes da Entrega 4.</p>

---

## 3. Navegação da Entrega 4

1. [Arquitetura e responsabilidades dos agentes](arquitetura-agentes.md): diagrama estrutural Mermaid, responsabilidades individuais, escopo documental e contratos `RespostaAgente` / `ResultadoValidacao`.
2. [Orquestração, fluxo de colaboração e roteamento](orquestrador-e-roteamento.md): diagrama de sequência entre os agentes e **relatório comparativo completo** (Regex × LLM Conjunto Teste 1 × `d1-omni-600M` Teste 2).
3. [Demonstração colaborativa em execução](demonstracao-agentes.md): saídas reais com `--agentes --trace`, prova de paralelismo, validação com devolução e simulação de falha (`--falhar-agente`).

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 16/11/2026 | 1.0 | Criação da documentação da Entrega 4 (Primeiro Protótipo Multiagente · Épico #37) | Grupo 04 |
