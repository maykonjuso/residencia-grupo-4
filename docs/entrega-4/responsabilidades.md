# Responsabilidades dos Agentes

A divisão clara de papéis no **RUmo** impede que o mesmo componente decida rotas, consulte documentos, audite fatos e monte o texto final sem separação de interesses. O objetivo desta página é deixar explícito o que cada agente **pode** e **não pode** fazer dentro do protótipo implementado.

!!! info "Estado dos papéis e regras implementadas"
    As tabelas abaixo descrevem o comportamento atual após a entrega do contrato comum (`#40`), das instruções e guardas dedicadas do Agente do RU e do Agente de Fluxo (`#41`), do Orquestrador (`#42`) e do Agente Validador ativo (`#43`).

---

## Matriz de responsabilidades (o que pode e o que não pode)

A **Tabela 1** detalha o papel, a função central e as fronteiras de atuação de cada agente e do Sintetizador.

| Agente / Componente | Papel | Responsabilidade principal | O que PODE fazer | O que NÃO PODE fazer |
|---|---|---|---|---|
| **Orquestrador** | Coordenação e controle de fluxo | Receber a dúvida do estudante, identificar se há mais de um assunto, encaminhar cada parte ao especialista certo em paralelo e consolidar o resultado | Dividir perguntas compostas em subperguntas; escolher o agente responsável por cada assunto; disparar especialistas ao mesmo tempo; simular falha controlada em testes; acionar o Agente Validador e o Sintetizador | Buscar trechos diretamente no banco de documentos; escrever a resposta final de domínio por conta própria; alterar ou renumerar as citações produzidas pelos especialistas |
| **Agente do RU** | Especialista no Restaurante Universitário | Responder dúvidas sobre cardápio, horários de funcionamento, valores das refeições, isenção, acesso na catraca e alergênicos | Consultar os documentos oficiais do Restaurante Universitário e o cardápio semanal estruturado (`cardapio_semanal.json`, com alergênicos por prato) de forma sincronizada; usar prompt de sistema próprio; aplicar guarda de domínio recusando consultas exclusivas de Fluxo antes da busca e higienizar recusas removendo citações espúrias | Responder dúvidas acadêmicas ou de outros domínios; aprovar a própria resposta no lugar do Agente Validador; misturar sua resposta com a de outro agente |
| **Agente de Fluxo** | Especialista em Fluxo de Graduação | Responder dúvidas sobre pré-requisitos, créditos, estágio obrigatório, trancamento de turma e matrícula em pós-graduação | Consultar os documentos oficiais de fluxogramas e normas acadêmicas da FCTE/UnB; usar prompt de sistema próprio; aplicar guarda de domínio recusando consultas exclusivas de RU antes da busca e higienizar recusas | Buscar ou inventar informações sobre o Restaurante Universitário; apagar ou modificar fontes retornadas pelo índice; aprovar a própria resposta |
| **Agente Validador** | Auditoria factual ativa (sem LLM) | Conferir cada resposta gerada pelos especialistas antes da entrega, reprovando e devolvendo respostas sem lastro factual ou sem citação | Verificar de forma determinística (sem custo nem alucinação de LLM) se preços, datas, horários, códigos de disciplinas e quantidades constam nos trechos recuperados e se há citação válida; aprovar ou reprovar com motivo explícito para devolução ao Sintetizador | Fazer novas buscas no banco de documentos; chamar outro LLM para julgar; inventar dados para consertar uma resposta incompleta; aprovar texto com valores sem respaldo nas fontes |
| **Sintetizador** | Correção de devoluções e montagem final | Tratar devoluções do Agente Validador (limite máximo de **1 retentativa**) e compor o texto final mantendo as referências separadas | Acionar 1 única retentativa com feedback do validador no mesmo backend configurado (ou reexecução controlada do agente) e aplicar recusa padrão quando a segunda tentativa também falhar; montar a resposta final em blocos independentes | Entrar em laço de múltiplas retentativas; trocar silenciosamente um backend LLM pelo modo extrativo; fundir ou renumerar referências entre subperguntas diferentes |

<p class="legenda">Tabela 1. Matriz de responsabilidades, permissões e restrições dos agentes e do sintetizador.</p>

---

## Regras garantidas pela arquitetura

Além da divisão individual de papéis da **Tabela 1**, o desenho do sistema assegura cinco garantias operacionais resumidas na **Tabela 2**.

| Garantia operacional | Como funciona hoje | Evolução prevista (próximas semanas) |
|---|---|---|
| **Classificação em dois estágios** | Avalia se a pergunta mistura mais de um assunto usando o limiar calibrado em `0,39`, além de acionar automaticamente a divisão quando há cruzamento explícito de termos RU + Fluxo ou duas ou mais cláusulas interrogativas | Nova calibração do limiar com perguntas reais coletadas em testes com estudantes (Semana 7) |
| **Roteamento em cascata** | Prioriza a sugestão de assunto emitida na própria divisão da pergunta; se faltar sugestão, usa regras por palavras-chave e recorre ao classificador neural (com limiar de confiança `0,60`) apenas em casos ambíguos | Extensão do roteador para novos domínios acadêmicos e integração com o Grupo 09 (Semana 6) |
| **Execução paralela segura** | Dispara especialistas diferentes ao mesmo tempo para economizar latência, enquanto sincroniza as leituras ao índice vetorial para evitar conflitos de concorrência | Ajuste fino de timeout por agente conforme perfil do provedor LLM em produção |
| **Isolamento de fontes por assunto** | Cada bloco da resposta mantém sua própria contagem de citações e sua própria lista de documentos, cumprindo a exigência do cliente do portal único | Validação ponta a ponta do isolamento de fontes diretamente na interface do portal único (Semana 6) |
| **Degradação graciosa e recusa final** | Se um especialista falhar, entrega a parte saudável com aviso explícito; se uma parte reprovar duas vezes no validador (limite de 1 retentativa), aplica recusa honesta sem exibir afirmações sem lastro | Política de nova tentativa automática para falhas transitórias de rede em APIs externas |

<p class="legenda">Tabela 2. Garantias operacionais implementadas no protótipo multiagente e evoluções previstas.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Criação da página dedicada de responsabilidades com matriz pode / não pode e regras contratuais | @maykonjuso |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Reescrita em linguagem descritiva evitando identificadores internos e siglas | @maykonjuso |
    | 1.2 | 18/11/2026 | @GabrielMacielBR | Atualização das responsabilidades após entrega de `#40`, `#41`, `#42` e `#43` | — |
    | 1.3 | 20/11/2026 | @GabrielMacielBR | Remoção de placeholders na Tabela 2, retirada de menção à ABI, inclusão do cardápio semanal estruturado no Agente do RU e ajuste de numeração das issues | — |
