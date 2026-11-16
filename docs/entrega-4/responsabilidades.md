# Responsabilidades dos Agentes

A divisão de responsabilidades entre os agentes do **RUmo** evita acoplamento entre roteamento, recuperação de domínio, validação factual e composição final. O foco desta etapa é delimitar exatamente o que cada papel **pode** e **não pode** fazer no protótipo implementado em `rag/rumo_rag/agentes.py`.

!!! warning "Escopo das issues dependentes (#41, #42 e #43)"
    Esta tabela descreve os contratos implementados no código atual (`agentes.py` e `reescrita.py`). Estratégias avançadas de geração, prompts específicos ou ferramentas adicionais atribuídas internamente a `AgenteRU`, `AgenteFluxo` e `AgenteValidador` encontram-se marcadas como `[a detalhar]` até o fechamento das issues **#41**, **#42** e **#43**.

---

## Matriz de responsabilidades (o que pode e o que não pode)

A **Tabela 1** especifica o papel, a responsabilidade principal e os limites explícitos de cada agente e do componente `Sintetizador`.

| Agente / Componente | Papel | Responsabilidade principal | O que PODE fazer | O que NÃO PODE fazer |
|---|---|---|---|---|
| **Orquestrador** (`Orquestrador`) | Coordenação e controle de fluxo | Receber a consulta do estudante, classificar/decompor, rotear subperguntas, disparar execuções em paralelo e consolidar o retorno | Acionar `classificar_composta` e `decompor_com_roteamento`; executar `rotear_subpergunta`; rodar agentes em paralelo via `ThreadPoolExecutor`; simular falha controlada via `--falhar-agente`; acionar `AgenteValidador` e `Sintetizador` | Recuperar trechos diretamente do corpus; gerar texto final ao estudante por conta própria; alterar os índices `[n]` das fontes dos agentes especialistas |
| **Agente RU** (`AgenteRU`) | Recuperação e resposta de domínio (`eixo="ru"`) | Responder subperguntas sobre o Restaurante Universitário (cardápio, horários, valores, isenção, acesso e alergênicos) | Consultar trechos dos eixos `"ru"` e `"apoio"` via `buscar_contexto` (com `_LOCK_BUSCA`); gerar resposta via `gerar_resposta` e retornar `RespostaAgente` com fontes citadas `[n]`. Ferramentas/prompts dedicados: `[a detalhar na issue #41]` | Responder subperguntas de outros eixos sem roteamento explícito; validar ou aprovar sua própria resposta no lugar do `AgenteValidador`; compor ou fundir blocos de outros agentes |
| **Agente Fluxo** (`AgenteFluxo`) | Recuperação e resposta de domínio (`eixo="fluxo"`) | Responder subperguntas sobre Fluxo de Graduação da UnB/FCTE (pré-requisitos, créditos, estágio, trancamento, ABI e pós) | Consultar trechos dos eixos `"fluxo"` e `"apoio"` via `buscar_contexto` (com `_LOCK_BUSCA`); gerar resposta via `gerar_resposta` e retornar `RespostaAgente` com fontes citadas `[n]`. Ferramentas/prompts dedicados: `[a detalhar na issue #42]` | Consultar ou inventar informações do eixo `"ru"`; suprimir ou alterar fontes retornadas pelo índice vetorial; validar ou aprovar sua própria resposta |
| **Agente Validador** (`AgenteValidador`) | Validação factual e guarda de citações | Auditar a fidelidade de cada `RespostaAgente` bem-sucedida antes da composição final | Inspecionar `geracao.valores_sem_fonte` e `geracao.resposta_sem_citacao`; emitir `ResultadoValidacao` com `acao_recomendada="aprovar"` ou `"devolver_ao_sintetizador"`. Checagens semânticas extras: `[a detalhar na issue #43]` | Buscar novos documentos no índice para preencher lacunas; inventar fatos para consertar a resposta; aprovar resposta com valores numéricos ou entidades sem respaldo nas fontes |
| **Sintetizador** (`Sintetizador`) | Tratamento de devoluções e composição contratual | Tratar respostas reprovadas pelo validador (`processar_devolucao`) e compor a resposta multi-partes (`compor`) sem misturar `[n]` | Converter devolução em fallback extrativo quando `backend != "extrativo"` e houver trechos; aplicar `RECUSA` sem trechos ou inserir `[Aviso do Agente Validador: ...]`; montar partes separadas com `[n]` isolados e avisos de falha (`degradado=True`) | Renumerar ou fundir listas `[n]` entre subperguntas diferentes; descartar uma parte aprovada quando outro agente falhar; omitir aviso de falha parcial ou devolução |

<p class="legenda">Tabela 1. Responsabilidades, permissões e restrições dos agentes e do componente sintetizador.</p>

---

## Regras contratuais e de execução garantidas pelo desenho

Além dos papéis individuais da **Tabela 1**, os agentes obedecem às restrições operacionais sintetizadas na **Tabela 2**.

| Regra / Contrato | Onde é aplicada | Comportamento implementado no código | Pendência vinculada |
|---|---|---|---|
| **Classificação em 2 estágios (`0.39`)** | `reescrita.py` + `Orquestrador` | `classificar_composta` usa `d1-omni-600M` com `LIMIAR_COMPOSTA = 0.39` e alimenta `decompor_com_roteamento` (com fallback sintático `_decompor_fallback`) | Calibração adicional em perguntas em aberto: `[a preencher]` |
| **Roteamento em cascata** | `rotear_subpergunta` (`agentes.py`) | Prioriza `eixo_sugerido` do LLM conjunto (Teste 1), passa por Regex determinística em empate/omissão e recorre ao `d1-omni-600M` (`limiar_confianca = 0.60`, Teste 2) | Novos domínios além de `ru` e `fluxo`: `[a detalhar]` |
| **Paralelismo thread-safe** | `Orquestrador` + `AgenteBase` | `ThreadPoolExecutor` dispara subperguntas em paralelo; `_LOCK_BUSCA` protege a busca vetorial (`TOP_K = 5`) mantendo a geração paralela | Ajuste fino de timeout por agente: `[a preencher]` |
| **Isolamento de índices `[n]`** | `Sintetizador.compor` | Cada bloco da resposta composta preserva sua própria numeração `[1], [2], ...` e lista de fontes correspondente ao contrato esperado por `consultas_rag.py` | Validação integrada no cliente do portal: `[a preencher]` |
| **Degradação graciosa** | `Orquestrador` + `Sintetizador` | Falha em um especialista gera aviso na parte correspondente sem bloquear os demais (`degradado=True`) | Políticas de retry automático por erro transitório: `[a preencher]` |

<p class="legenda">Tabela 2. Mapeamento das regras operacionais, garantias atuais e itens pendentes.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Criação da página dedicada de responsabilidades com matriz pode / não pode e regras contratuais | @maykonjuso |
