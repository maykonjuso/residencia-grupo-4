# Entrega 4 — Primeiro Protótipo Multiagente

A **Entrega 4** (Épico `#37`) marca a evolução do **RUmo** de um fluxo único de busca e resposta para o primeiro **protótipo de Sistema Multiagente**. Em vez de um único bloco responder a tudo de forma linear, o sistema passa a identificar quando há mais de um assunto na mesma dúvida, distribuir cada parte ao especialista adequado em paralelo, auditar a fidelidade dos dados antes de exibi-los e montar a resposta final mantendo as fontes de cada parte isoladas.

!!! info "Escopo atual do protótipo"
    Esta documentação descreve estritamente o comportamento implementado e testado no repositório. Detalhes internos dos agentes especialistas e ferramentas adicionais ainda em desenvolvimento nas issues **#41**, **#42** e **#43** aparecem marcados como `[a preencher]` ou `[a detalhar]`.

---

## O que é a Entrega 4

O objetivo desta etapa é atender perguntas simples ou compostas de estudantes da UnB (Campus Gama / FCTE) sobre o **Restaurante Universitário (RU)** e o **Fluxo de Graduação** com colaboração coordenada entre agentes. A separação das fontes por bloco garante compatibilidade com o cliente do portal único da universidade, que exige que cada citação corresponda exatamente à lista de fontes daquela parte.

A **Tabela 1** resume o que já funciona no protótipo, o que aguarda detalhamento e o que ficou fora do escopo desta semana.

| Categoria | Item / Capacidade | Situação | O que faz na prática |
|---|---|---|---|
| **Implementado** | Estrutura base dos agentes e do orquestrador | Concluído | Define os papéis de coordenação, atendimento ao RU, atendimento ao Fluxo de Graduação, validação factual e composição final da resposta |
| **Implementado** | Classificação e divisão de perguntas compostas | Concluído | Detecta quando uma dúvida mistura mais de um tópico (com limiar calibrado em `0,39`) e a divide em subperguntas independentes, com opção de separação por conectivos em caso de falha |
| **Implementado** | Roteamento híbrido por assunto | Concluído | Escolhe o agente adequado combinando a sugestão gerada na divisão da pergunta, regras diretas por palavras-chave e um classificador neural de apoio |
| **Implementado** | Execução simultânea e tolerância a falhas | Concluído | Dispara consultas ao RU e ao Fluxo de Graduação ao mesmo tempo e permite simular queda de um agente sem derrubar a parte saudável |
| **Implementado** | Conferência factual e retorno ao sintetizador | Concluído | Confirma se valores e afirmações aparecem nos trechos recuperados, solicita correção quando encontra inconsistência e preserva citações independentes por assunto |
| **Implementado** | Comparativo experimental de roteamento | Concluído | Avalia três estratégias de roteamento em um conjunto de 8 perguntas múltiplas (17 subperguntas) de linguagem natural |
| **Implementado** | Cardápio estruturado por compartimento (`#54`) | Concluído | Converte as refeições dos cardápios em JSON por compartimento da bandeja e trilha alimentar (*padrão*, *ovolacto* e *vegano*), preservando documento e página de origem em cada opção |
| **Aberto (`#41`, `#42`, `#43`)** | Prompts especializados, regras finas e ferramentas próprias dos agentes | `[a preencher]` | Contratos e fluxo base estão prontos; a especialização interna depende do fechamento das issues `#41` a `#43` |
| **Aberto (`#41`, `#42`, `#43`)** | Demonstração completa com modelo generativo final | `[a preencher]` | As execuções atuais validam o fluxo de forma determinística no modo extrativo; a execução final com modelo generativo aguarda `#41` a `#43` |
| **Fora de escopo** | Comunicação em tempo real com a API do Portal Único (Grupo 09) | Fora da entrega | Integração geral do sistema unificado descrita em [Divisão com o Grupo 09](../visao/escopo-grupos.md) |
| **Fora de escopo** | Memória conversacional contínua e login autenticado | Fora da entrega | Cada pergunta é processada de forma independente, sem histórico pessoal de usuário |

<p class="legenda">Tabela 1. Visão geral do que foi implementado, do que está pendente e do que ficou fora de escopo na Entrega 4.</p>

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
