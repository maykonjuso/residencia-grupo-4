# Entrega 4 · Primeiro protótipo multiagente

**Semana 4 do Challenge 2.** Prazo: sexta-feira, 20/11/2026. Foco desta etapa, segundo o enunciado: *colaboração entre agentes, definição clara de responsabilidades e qualidade das interações entre eles*.

---

## 1. Escopo e checklist do que foi pedido

A Entrega 4 evolui o fluxo único da Entrega 3 para o primeiro **sistema multiagente do RUmo** (Épico `#37`), mantendo a fidelidade às fontes e o isolamento das citações exigido pelo portal único.

### Agentes

- [x] **Mínimo de dois agentes especializados:** `Agente do RU` e `Agente de Fluxo` com prompts dedicados, guarda preventiva de domínio e consulta sincronizada à base (`#41`).
- [x] **Agentes adicionais de coordenação e validação:** `Orquestrador` com decomposição/roteamento híbrido e execução em paralelo (`#42`), `Agente Validador` determinístico sem LLM com até 1 retentativa (`#43`) e `Sintetizador` de resposta.
- [x] **Contrato unificado e rastreio:** comunicação tipada via mensagens, respostas e histórico cronológico de interações (`#40`).

### Documentação

- [x] **Diagrama da arquitetura dos agentes:** fluxo verticalizado, conexões entre componentes e tabela consolidada de modelos, RAG e ferramentas. ([Ver arquitetura](arquitetura-agentes.md))
- [x] **Descrição das responsabilidades:** matriz do que cada agente pode e não pode fazer e garantias operacionais. ([Ver responsabilidades](responsabilidades.md))
- [x] **Fluxo de interação e colaboração:** diagrama de sequência para perguntas compostas, tratamento de falhas e comparativo das estratégias de roteamento. ([Ver fluxo](fluxo-de-interacao.md))

### Demonstração

- [x] **Fluxo completo com os agentes colaborando:** execução paralela, devolução com reparo do validador (`qwen2.5:7b`), degradação graciosa, roteamento neural, avaliação nas 12 perguntas múltiplas e consulta ao cardápio semanal estruturado com alergênicos (`F56`). ([Ver demonstração](demonstracao.md))

### Além do pedido

- [x] **Cardápio semanal estruturado com alergênicos (`#54`, `#55`):** `cardapio_semanal.json` organizado por compartimento, trilha alimentar e alergênicos por prato como fonte direta do Agente do RU.
- [x] **API v1.0 multiagente e nuvem (`#44`, `#53`):** `POST /perguntar` integrado ao `Orquestrador` mantendo o contrato v1.0 estrito (`trace` opcional), base com 56 documentos cadastrados em `rag/catalogo.yaml` (55 indexados em 1.964 chunks em `rag/dados/chunks.jsonl`) e preparo leve para deploy na Vercel e no Render.

---

## 2. Resultado em números

A **Tabela 1** sintetiza as principais decisões, volumes e métricas alcançados no protótipo desta entrega.

| Dimensão | Resultado no protótipo |
|---|---|
| Agentes e papéis | `4` agentes (`Orquestrador`, `Agente do RU`, `Agente de Fluxo`, `Agente Validador`) + `Sintetizador` |
| Base de conhecimento | `56` documentos oficiais cadastrados (`55` indexados no RAG = `1.964` chunks + `F56` em `cardapio_semanal.json` com alergênicos) |
| Decomposição e roteamento (12 múltiplas) | `12/12` (`100%`) das consultas quebradas e roteadas nas `31` subperguntas esperadas |
| Acurácia em linguagem natural (`17` subperguntas) | `76,5%` (Regex) → `94,1%` (`d1-omni-600M`) → `100,0%` (`qwen2.5:7b` conjunto) |
| Ganho de execução em paralelo | Economia de `48,6%` no tempo dos agentes (`264,50 s` paralelos vs `514,13 s` individuais) |
| Validação factual ativa (`Agente Validador`) | `31/31` partes aprovadas no desfecho (`2` desvios interceptados: `M07` corrigida; `M04` recusada) |
| Suíte automatizada e API | `233` testes aprovados (`1` ignorado) e `POST /perguntar` compatível com contrato v1.0 |
| Fora de escopo nesta semana | Comunicação em tempo real com o portal do [Grupo 09](../visao/escopo-grupos.md) e memória conversacional contínua |

<p class="legenda">Tabela 1. Resumo técnico e métricas consolidadas da Entrega 4.</p>

---

## 3. Navegação da Entrega 4

1. [Arquitetura dos Agentes](arquitetura-agentes.md): Diagrama verticalizado com os quatro agentes, conexões entre componentes, tabela consolidada de modelos e ferramentas utilizadas e pontos de extensão.
2. [Responsabilidades dos Agentes](responsabilidades.md): Matriz do que cada agente e o sintetizador podem e não podem fazer, além das garantias operacionais.
3. [Fluxo de Interação e Roteamento](fluxo-de-interacao.md): Diagrama de sequência para perguntas compostas, tratamento de falhas e síntese comparativa de roteamento.
4. [Demonstração Executada](demonstracao.md): Execuções reais comprovando paralelismo, reparo do validador, degradação graciosa, cardápio semanal com alergênicos e apêndice completo (`M01`–`M12`).

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 16/11/2026 | 1.0 | Estrutura inicial da Entrega 4 (Épico #37) | @GabrielMacielBR |
    | 18/11/2026 | 1.4 | Atualização após conclusão do contrato (`#40`), especialistas (`#41`), `Orquestrador` (`#42`), validador ativo (`#43`) e cardápio estruturado (`#54`, por @Kyara2) | @GabrielMacielBR |
    | 20/11/2026 | 2.0 | Alinhamento editorial ao estilo das Entregas 1–3 e consolidação de alergênicos (`#55`), API multiagente (`#44`), pilha técnica e apêndice `M01`–`M12` | @GabrielMacielBR |
    | 27/11/2026 | 2.1 | Alinhamento da contagem da base para 56 fontes (55 indexadas / 1.964 chunks + F56) (Issue #96) | Keila Alves |
