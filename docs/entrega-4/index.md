# Entrega 4 — Primeiro Protótipo Multiagente

A **Entrega 4** (Épico `#37`) marca a evolução do **RUmo** de um fluxo único de busca e resposta para o primeiro **protótipo de Sistema Multiagente**. Em vez de um único bloco responder a tudo de forma linear, o sistema passa a identificar quando há mais de um assunto na mesma dúvida, distribuir cada parte ao especialista adequado em paralelo, auditar a fidelidade dos dados antes de exibi-los e montar a resposta final mantendo as fontes de cada parte isoladas.

!!! info "Escopo atual do protótipo"
    Esta documentação descreve estritamente o comportamento implementado e testado na arquitetura multiagente do RUmo, incluindo o contrato comum de comunicação entre agentes (`#40`), os especialistas de RU (`#41`) e Fluxo (`#42`) com prompts e guarda de domínio próprios, o validador ativo (`#43`) com limite de 1 retentativa e recusa final, e o suporte a APIs compatíveis com OpenAI/OpenRouter.

---

## O que é a Entrega 4

O objetivo desta etapa é atender perguntas simples ou compostas de estudantes da UnB (Campus Gama / FCTE) sobre o **Restaurante Universitário (RU)** e o **Fluxo de Graduação** com colaboração coordenada entre agentes. A separação das fontes por bloco garante compatibilidade com o cliente do portal único da universidade, que exige que cada citação corresponda exatamente à lista de fontes daquela parte.

A **Tabela 1** resume o que já funciona no protótipo, o que aguarda detalhamento e o que ficou fora do escopo desta semana.

| Categoria | Item / Capacidade | Situação | O que faz na prática |
|---|---|---|---|
| **Implementado** | Contrato comum e rastreamento entre agentes (`#40`) | Concluído | Padroniza a comunicação via mensagens e respostas tipadas e registra todas as interações em ordem cronológica |
| **Implementado** | Especialização do Agente do RU (`#41`) e do Agente de Fluxo (`#42`) | Concluído | Cada agente possui prompt de sistema próprio, guarda preventiva contra perguntas fora do seu domínio e higienização automática de recusas |
| **Implementado** | Classificação e divisão de perguntas compostas | Concluído | Detecta múltiplos tópicos via limiar neural calibrado (`0,39`) ou cruzamento explícito entre RU e Fluxo, dividindo em subperguntas independentes |
| **Implementado** | Roteamento híbrido por assunto | Concluído | Escolhe o agente adequado combinando a sugestão gerada na divisão da pergunta, regras diretas por palavras-chave e um classificador neural de apoio |
| **Implementado** | Execução simultânea e tolerância a falhas | Concluído | Dispara consultas ao RU e ao Fluxo de Graduação ao mesmo tempo e permite simular queda de um agente sem derrubar a parte saudável |
| **Implementado** | Validador ativo e devolução ao sintetizador (`#43`) | Concluído | Validador determinístico (sem LLM) reprova valores sem fonte ou falta de citação, devolve para no máximo **1 retentativa com feedback** e aplica recusa padrão se reprovar duas vezes |
| **Implementado** | Suporte a provedor local ou API externa (OpenRouter/OpenAI) | Concluído | Permite executar decomposição e agentes via Ollama, HuggingFace local, modo extrativo ou API compatível com OpenAI mantendo o padrão local |
| **Implementado** | Comparativo experimental de roteamento | Concluído | Avalia três estratégias de roteamento em um conjunto de 8 perguntas múltiplas (17 subperguntas) de linguagem natural |
| **Implementado** | Cardápio estruturado por compartimento (`#54`) | Concluído | Converte as refeições dos cardápios em JSON por compartimento da bandeja e trilha alimentar (*padrão*, *ovolacto* e *vegano*), preservando documento e página de origem em cada opção |
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
    | 1.4 | 18/11/2026 | @GabrielMacielBR | Atualização do panorama após conclusão do contrato (`#40`), especialização (`#41`/`#42`) e validador ativo (`#43`) | — |
