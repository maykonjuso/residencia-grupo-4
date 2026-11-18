# Responsabilidades dos Agentes

A divisão clara de papéis no **RUmo** impede que o mesmo componente decida rotas, consulte documentos, audite fatos e monte o texto final sem separação de interesses. O objetivo desta página é deixar explícito o que cada agente **pode** e **não pode** fazer dentro do protótipo implementado.

!!! info "Como ler a matriz"
    A tabela registra o que cada agente pode fazer e os limites que impedem buscas fora do eixo, afirmações sem fonte e mistura de citações.

---

## Matriz de responsabilidades (o que pode e o que não pode)

A **Tabela 1** detalha o papel, a função central e as fronteiras de atuação de cada agente e do Sintetizador.

| Agente / Componente | Papel | Responsabilidade principal | O que PODE fazer | O que NÃO PODE fazer |
|---|---|---|---|---|
| **Orquestrador** | Coordenação e controle de fluxo | Receber a dúvida do estudante, identificar se há mais de um assunto, encaminhar cada parte ao especialista certo em paralelo e consolidar o resultado | Dividir perguntas compostas em subperguntas; escolher o agente responsável por cada assunto; disparar especialistas ao mesmo tempo; simular falha controlada em testes; acionar o Agente Validador e o Sintetizador | Buscar trechos diretamente no banco de documentos; escrever a resposta final de domínio por conta própria; alterar ou renumerar as citações produzidas pelos especialistas |
| **Agente do RU** | Especialista no Restaurante Universitário | Responder sobre cardápios, refeições, horários, preços, grupos de pagamento, isenção, auxílio e alergênicos | Buscar no eixo `ru`; gerar com `INSTRUCOES_RU`; citar os trechos utilizados; declarar incerteza ou recusar quando a base não responde | Responder sobre disciplinas; inventar preços, datas ou condições de pagamento; omitir citações ou aprovar a própria resposta |
| **Agente de Fluxo** | Especialista em fluxo acadêmico da FCTE/UnB | Responder sobre disciplinas, pré-requisitos, créditos, cursos e normas acadêmicas | Buscar no eixo `fluxo`; gerar com `INSTRUCOES_FLUXO`; distinguir relações explicitadas por seta cheia das ligações tracejadas; citar as fontes e explicitar incerteza | Responder sobre o RU; tratar uma ligação tracejada como pré-requisito confirmado; inventar códigos ou regras; aprovar a própria resposta |
| **Agente Validador** | Auditoria factual e de citações | Conferir cada resposta antes da composição final | Verificar citações e valores numéricos contra as fontes recebidas; devolver a resposta quando falhar na conferência; informar motivos no trace | Fazer novas buscas; inventar dados; substituir a responsabilidade do especialista por interpretação sem fonte |
| **Sintetizador** | Correção e composição | Corrigir uma resposta reprovada e montar os blocos finais | Fazer no máximo uma retentativa com feedback do Validador e os trechos já recuperados; aplicar a recusa padrão quando a correção não for suficiente; preservar partes e fontes isoladas | Fazer uma nova busca; misturar ou renumerar citações entre partes; ocultar falhas de um agente |

<p class="legenda">Tabela 1. Matriz de responsabilidades, permissões e restrições dos agentes e do sintetizador.</p>

---

## Regras garantidas pela arquitetura

Além da divisão individual de papéis da **Tabela 1**, o desenho do sistema assegura cinco garantias operacionais resumidas na **Tabela 2**.

| Garantia operacional | Como funciona hoje | Limite conhecido |
|---|---|---|
| **Classificação e decomposição** | Combina detecção de pergunta composta, divisão com sugestão de domínio e fallback para cruzamento RU + Fluxo ou conectivos | Perguntas ambíguas fora desses domínios podem exigir revisão humana |
| **Roteamento em cascata** | Usa domínio sugerido na decomposição, regras lexicais e classificador neural para casos ambíguos | Os especialistas cobrem RU e Fluxo da FCTE; não há agente geral para todo assunto da UnB |
| **Execução paralela segura** | Executa especialistas simultaneamente e sincroniza acesso ao índice | O tempo depende do backend de geração e da máquina/serviço que executa o modelo |
| **Isolamento de fontes** | Cada bloco mantém suas citações e fontes do domínio correspondente | A numeração das citações é local a cada parte da resposta |
| **Degradação graciosa** | Se um agente falhar, a parte saudável ainda é entregue com aviso; a resposta é marcada como degradada | Uma falha não é repetida automaticamente; correção do Validador tem limite de uma tentativa |

<p class="legenda">Tabela 2. Garantias operacionais implementadas e limites conhecidos do protótipo multiagente.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Criação da página dedicada de responsabilidades com matriz pode / não pode e regras contratuais | @maykonjuso |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Reescrita em linguagem descritiva evitando identificadores internos e siglas | @maykonjuso |
    | 1.2 | 18/11/2026 | @keilogger | Substituição de pendências antigas pela implementação real de prompts, guardas, validação e síntese | — |
