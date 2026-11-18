# Responsabilidades dos Agentes

A divisão clara de papéis no **RUmo** impede que o mesmo componente decida rotas, consulte documentos, audite fatos e monte o texto final sem separação de interesses. O objetivo desta página é deixar explícito o que cada agente **pode** e **não pode** fazer dentro do protótipo implementado.

!!! warning "Escopo das issues dependentes (#41, #42 e #43)"
    As tabelas abaixo descrevem exatamente o comportamento implementado no código atual. Estratégias adicionais de geração, instruções específicas de domínio ou ferramentas auxiliares atribuídas internamente ao Agente do RU, ao Agente de Fluxo e ao Agente Validador estão marcadas como `[a detalhar]` até o fechamento das issues **#41**, **#42** e **#43**.

---

## Matriz de responsabilidades (o que pode e o que não pode)

A **Tabela 1** detalha o papel, a função central e as fronteiras de atuação de cada agente e do Sintetizador.

| Agente / Componente | Papel | Responsabilidade principal | O que PODE fazer | O que NÃO PODE fazer |
|---|---|---|---|---|
| **Orquestrador** | Coordenação e controle de fluxo | Receber a dúvida do estudante, identificar se há mais de um assunto, encaminhar cada parte ao especialista certo em paralelo e consolidar o resultado | Dividir perguntas compostas em subperguntas; escolher o agente responsável por cada assunto; disparar especialistas ao mesmo tempo; simular falha controlada em testes; acionar o Agente Validador e o Sintetizador | Buscar trechos diretamente no banco de documentos; escrever a resposta final de domínio por conta própria; alterar ou renumerar as citações produzidas pelos especialistas |
| **Agente do RU** | Especialista no Restaurante Universitário | Responder dúvidas sobre cardápio, horários de funcionamento, valores das refeições, isenção, acesso na catraca e alergênicos | Consultar os documentos oficiais do Restaurante Universitário e guias de apoio de forma sincronizada; redigir a resposta com citação explícita das fontes consultadas. Ferramentas e instruções dedicadas: `[a detalhar na issue #41]` | Responder dúvidas de outros domínios sem encaminhamento explícito; aprovar a própria resposta no lugar do Agente Validador; misturar sua resposta com a de outro agente |
| **Agente de Fluxo** | Especialista em Fluxo de Graduação | Responder dúvidas sobre pré-requisitos, créditos, estágio obrigatório, trancamento de turma, ingresso na área básica e matrícula em pós-graduação | Consultar os documentos oficiais de fluxogramas e normas acadêmicas da FCTE/UnB junto aos guias de apoio; redigir a resposta citando os documentos utilizados. Ferramentas e instruções dedicadas: `[a detalhar na issue #42]` | Buscar ou inventar informações sobre o Restaurante Universitário; apagar ou modificar fontes retornadas pelo índice; aprovar a própria resposta |
| **Agente Validador** | Auditoria factual e de citações | Conferir cada resposta gerada pelos especialistas antes de ela seguir para a entrega ao estudante | Verificar se todos os números ou fatos específicos da resposta constam nos trechos recuperados e se há citação de fonte válida; aprovar o bloco ou devolvê-lo ao Sintetizador para correção. Checagens semânticas extras: `[a detalhar na issue #43]` | Fazer novas buscas no banco de documentos para preencher lacunas; inventar dados para consertar uma resposta incompleta; aprovar texto que contenha valores sem respaldo nas fontes |
| **Sintetizador** | Correção de devoluções e montagem final | Tratar respostas reprovadas pelo validador e compor o texto final mantendo as referências de cada parte separadas | Converter respostas reprovadas em saída extrativa segura com base nos trechos já recuperados (ou aplicar recusa padrão e aviso explícito quando não houver base); montar a resposta final em blocos independentes sinalizando eventuais falhas parciais | Fundir ou renumerar referências entre subperguntas diferentes; descartar uma parte aprovada quando outro agente falhar; ocultar avisos de falha ou de reprovação |

<p class="legenda">Tabela 1. Matriz de responsabilidades, permissões e restrições dos agentes e do sintetizador.</p>

---

## Regras garantidas pela arquitetura

Além da divisão individual de papéis da **Tabela 1**, o desenho do sistema assegura cinco garantias operacionais resumidas na **Tabela 2**.

| Garantia operacional | Como funciona hoje | Pendência vinculada |
|---|---|---|
| **Classificação em dois estágios** | Primeiro avalia se a pergunta mistura mais de um assunto usando o limiar calibrado em `0,39`; quando necessário, divide em subperguntas por modelo linguístico ou, em caso de indisponibilidade, por conectivos gramaticais | Calibração adicional em perguntas reais em aberto: `[a preencher]` |
| **Roteamento em cascata** | Prioriza a sugestão de assunto emitida na própria divisão da pergunta; se faltar sugestão, usa regras por palavras-chave e recorre ao classificador neural (com limiar de confiança `0,60`) apenas em casos ambíguos | Inclusão de novos domínios além de RU e Fluxo: `[a detalhar]` |
| **Execução paralela segura** | Dispara especialistas diferentes ao mesmo tempo para economizar latência, enquanto sincroniza as leituras ao índice vetorial para evitar conflitos de concorrência | Ajuste fino de tempo limite por agente: `[a preencher]` |
| **Isolamento de fontes por assunto** | Cada bloco da resposta mantém sua própria contagem de citações e sua própria lista de documentos, cumprindo a exigência do cliente do portal único | Validação integrada diretamente no portal único: `[a preencher]` |
| **Degradação graciosa em falha** | Se um especialista falhar ou ficar indisponível, o sistema entrega normalmente a resposta do agente saudável acompanhada de aviso explícito sobre a parte faltante | Política de nova tentativa automática por falha transitória: `[a preencher]` |

<p class="legenda">Tabela 2. Garantias operacionais implementadas no protótipo multiagente e pendências registradas.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Criação da página dedicada de responsabilidades com matriz pode / não pode e regras contratuais | @maykonjuso |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Reescrita em linguagem descritiva evitando identificadores internos e siglas | @maykonjuso |
