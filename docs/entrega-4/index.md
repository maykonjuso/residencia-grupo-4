# Entrega 4 — Primeiro Protótipo Multiagente

A **Entrega 4** (Épico `#37`) marca a evolução do **RUmo** de um fluxo único de busca e resposta para o primeiro **protótipo de Sistema Multiagente**. Em vez de um único bloco responder a tudo de forma linear, o sistema passa a identificar quando há mais de um assunto na mesma dúvida, distribuir cada parte ao especialista adequado em paralelo, auditar a fidelidade dos dados antes de exibi-los e montar a resposta final mantendo as fontes de cada parte isoladas.

!!! info "Escopo atual do protótipo"
    Esta documentação descreve o comportamento implementado e demonstrado no repositório. Os agentes de domínio, o orquestrador e o validador seguem o contrato `Agente` / `Mensagem` / `Resposta`; a CLI pode executar o fluxo multiagente.

---

## O que é a Entrega 4

O objetivo desta etapa é atender perguntas simples ou compostas de estudantes da UnB (Campus Gama / FCTE) sobre o **Restaurante Universitário (RU)** e o **Fluxo de Graduação** com colaboração coordenada entre agentes. A separação das fontes por bloco permite conferir cada afirmação contra as referências da parte correspondente.

A **Tabela 1** resume o que funciona no protótipo e os limites desta entrega.

| Categoria | Item / Capacidade | Situação | O que faz na prática |
|---|---|---|---|
| **Implementado** | Estrutura e contrato dos agentes | Concluído | Orquestrador, Agente RU, Agente Fluxo, Agente Validador e Sintetizador comunicam-se por `Mensagem` e `Resposta`; as interações podem ser registradas em `Trace` |
| **Implementado** | Classificação e divisão de perguntas compostas | Concluído | Detecta assuntos múltiplos, divide a pergunta e inclui proteção para cruzamentos RU + Fluxo mesmo quando a probabilidade fica abaixo do limiar `0,39` |
| **Implementado** | Roteamento híbrido por assunto | Concluído | Escolhe o agente adequado combinando a sugestão gerada na divisão da pergunta, regras diretas por palavras-chave e um classificador neural de apoio |
| **Implementado** | Execução simultânea e tolerância a falhas | Concluído | Dispara consultas ao RU e ao Fluxo de Graduação ao mesmo tempo e permite simular queda de um agente sem derrubar a parte saudável |
| **Implementado** | Prompts especializados e proteção de domínio | Concluído | RU e Fluxo têm instruções próprias, recusam consultas claramente fora do seu domínio e mantêm as fontes do próprio eixo |
| **Implementado** | Conferência factual e retorno ao sintetizador | Concluído | Confere citações e valores, permite uma tentativa de correção e recusa quando a resposta continua sem respaldo |
| **Implementado** | CLI multiagente | Concluído | A CLI aceita `--agentes` e `--trace` para executar e exibir a colaboração entre os agentes |
| **Implementado** | Comparativo experimental de roteamento | Concluído | Avalia três estratégias de roteamento em um conjunto de 8 perguntas múltiplas (17 subperguntas) de linguagem natural |
| **Implementado** | Cardápio estruturado por compartimento (`#54`) | Concluído | Converte as refeições dos cardápios em JSON por compartimento da bandeja e trilha alimentar (*padrão*, *ovolacto* e *vegano*), preservando documento e página de origem em cada opção |
| **Fora de escopo** | Atendimento geral a qualquer assunto ou campus da UnB | Não incluído | Os especialistas desta entrega cobrem os domínios RU e Fluxo acadêmico da FCTE |
| **Fora de escopo** | Memória conversacional contínua e login autenticado | Fora da entrega | Cada pergunta é processada de forma independente, sem histórico pessoal de usuário |

<p class="legenda">Tabela 1. Visão geral do que foi implementado e do que ficou fora de escopo na Entrega 4.</p>

!!! note "Apoio à montagem de prato — Cardápio estruturado (#54)"
    Como complemento da base de conhecimento para a interface do monta-prato, o módulo de coleta transforma os cardápios já extraídos da base em JSON organizado por compartimento da bandeja (incluindo almoço, jantar e café da manhã) e por trilha alimentar (*padrão*, *ovolactovegetariano* e *vegetariano estrito*). Cada opção mantém o documento e a página de origem, trata falhas de formatação do PDF com avisos e pode ser gerada em `rag/` via `python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09 --refeicao almoco`.

---

## Navegação da Entrega 4

A documentação segue os três artefatos solicitados no enunciado e o registro da execução do sistema, conforme a **Tabela 2**.

| Página | O que você encontra |
|---|---|
| [Arquitetura dos Agentes](arquitetura-agentes.md) | Diagrama verticalizado com os quatro agentes, o sintetizador, as conexões entre eles e os pontos de extensão |
| [Responsabilidades dos Agentes](responsabilidades.md) | Tabela descrevendo o papel, as responsabilidades, o que cada componente **pode** e **não pode** fazer e as regras garantidas |
| [Fluxo de Interação e Roteamento](fluxo-de-interacao.md) | Diagrama de sequência em linguagem direta para uma pergunta composta e o comparativo das estratégias de classificação e roteamento |
| [Demonstração Executada](demonstracao.md) | Execuções reais em terminal comprovando paralelismo, isolamento de citações, retorno do validador e degradação graciosa |

<p class="legenda">Tabela 2. Guia de navegação da documentação da Entrega 4.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Versão inicial da documentação da Entrega 4 | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Refatoração para a estrutura padronizada com marcação explícita de pendências | @maykonjuso |
    | 1.2 | 16/11/2026 | @GabrielMacielBR | Adequação para leitura descritiva sem siglas nem jargões de código internos | @maykonjuso |
    | 1.3 | 18/11/2026 | @GabrielMacielBR | Inclusão breve do cardápio estruturado por compartimento (`#54`, por @Kyara2) no resumo da Entrega 4 | — |
    | 1.4 | 18/11/2026 | @keilogger | Atualização do estado da Entrega 4 após a implementação e demonstração do fluxo multiagente | — |
