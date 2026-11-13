# Entrega 3 · Respostas baseadas em evidências (LLM × RAG)

**Semana 3 do Challenge 2.** Prazo: sexta-feira, 13/11/2026. Foco desta etapa: *comparação empírica com e sem RAG, medição quantitativa de fidelidade e alucinação, e reescrita de consultas compostas*.

---

## 1. O que esta entrega demonstra

Na Entrega 2, o grupo colocou em operação o protótipo funcional do RUmo e observou qualitativamente que o modelo Qwen2.5-7B reduziu as alucinações observadas na versão 1.5B. 

A **Entrega 3 transforma essa observação em medição formal**: responde as mesmas 32 perguntas-ouro do conjunto de teste com e sem RAG, mede o ganho de fidelidade, comprova a eliminação de alucinações em dados sensíveis (preços, pratos e pré-requisitos) e introduz o módulo de reescrita para consultas compostas.

### Estrutura de entrega e áreas abordadas

- [ ] **Comparação lado a lado (Sem RAG × Com RAG):** As 32 perguntas-ouro de `rag/avaliacao/perguntas_ouro.jsonl` respondidas com e sem RAG pelo Qwen2.5-7B local. ([Ver especificação](llm-vs-rag.md))
- [ ] **Medição de fidelidade e alucinação:** Protocolo de avaliação local medindo taxa de citação, fidelidade, recusa e alucinação. ([Ver metodologia e métricas](fidelidade-e-alucinacao.md))
- [ ] **Transparência metodológica:** Documentação analítica de um caso real onde o RAG não ajudou ou teve limitação. ([Ver análise de falha](llm-vs-rag.md#o-caso-em-que-o-rag-nao-ajudou))
- [ ] **Reescrita de consulta para perguntas compostas:** Mecanismo de decomposição de consultas multi-hop mitigando o risco R04. ([Ver arquitetura de reescrita](reescrita-de-consulta.md))
- [x] **Conformidade arquitetural (RNF02 e RNF03):** Avaliações executadas 100% localmente preservando privacidade sem envio de dados a APIs de terceiros (arquitetura dimensionada para a RTX 4060 8 GB, com latência e respostas aferidas nesta entrega em **MacBook Air M4 24 GB**).

---

## 2. Resultados esperados e metas

A **Tabela 1** apresenta a matriz de consolidação dos resultados comparativos no conjunto de 32 perguntas de teste, estruturada para receber as medições frente às metas da Entrega 1.

| Dimensão avaliada | Modelo Puro (Sem RAG) | RUmo (Com RAG) | Meta (Entrega 1) |
|---|:---:|:---:|:---:|
| **Taxa de citação de fontes [n]** | *A medir* | *A medir* | ≥ 0,95 |
| **Fidelidade factual** | *A medir* | *A medir* | ≥ 0,90 |
| **Taxa de recusa em perguntas sem base** | *A medir* | *A medir* | 1,00 |
| **Taxa de alucinação de dados críticos** | *A medir* | *A medir* | 0,00 |
| **Completude em perguntas compostas** | *A medir* | *A medir* | ≥ 0,85 |
| **Latência média por consulta** | *A medir* | *A medir* | < 30 s |

<p class="legenda">Tabela 1. Matriz executiva de métricas comparativas da Entrega 3.</p>

---

## 3. Navegação da Entrega 3

1. [Comparação LLM puro × RAG](llm-vs-rag.md): Protocolo de teste lado a lado nas 32 perguntas, casos de cardápio e fluxo, e documentação do caso de falha do RAG.
2. [Fidelidade e taxa de alucinação](fidelidade-e-alucinacao.md): Metodologia de medição, justificativa da avaliação local e equações das métricas de fundamentação.
3. [Reescrita de consulta para perguntas compostas](reescrita-de-consulta.md): Decomposição de intenção, pipeline multi-hop e ganho medido na recuperação de múltiplos documentos.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Estrutura inicial da Entrega 3 (Épico #4): checklist, matriz de métricas e navegação | Grupo 04 |
    | 13/11/2026 | 1.1 | Registro do ambiente de medição local (MacBook Air M4 24 GB, divergindo da RTX 4060 8 GB) | Grupo 04 |
