# Demonstração Executada

Esta página registra uma execução real do fluxo multiagente com Ollama, e por um teste de falha controlada. A demonstração cobre decomposição, roteamento, execução paralela, validação, composição, citações separadas e trace.

!!! info "Ambiente da demonstração"
    Execução local em 18/11/2026, com busca BM25 e backend Ollama. O primeiro carregamento do classificador neural baixou os pesos do modelo; nas execuções seguintes os arquivos ficaram em cache.

---

## Caso 1 — Pergunta composta respondida pelos dois especialistas

Comando executado na pasta rag/:

```bash
RUMO_BUSCA=bm25 python -m rumo_rag "Quais os pré-requisitos de Testes de Software e que horas abre o RU?" --agentes --trace --backend ollama
```

### Trace real da execução

```text
1. Classificação/Decomposição: composta=True (p=0.3503, limiar=0.39, 6.988s)
   - Subpergunta 1: Quais são os pré-requisitos para a disciplina de Testes de Software?
   - Subpergunta 2: Que horas o Restaurante Universitário (RU) abre?
2. Roteamento (2 execuções):
   - Pré-requisitos de Testes de Software -> fluxo
   - Horário de abertura do RU -> ru
3. Execução paralela: tempo_total=13.050s | soma_individual=24.178s | ganho=11.128s
   - Agente Fluxo: OK (5 trechos)
   - Agente RU: OK (5 trechos)
4. Validador factual: fluxo APROVADO; ru APROVADO
5. Composição: 2 partes | índices [n] isolados=True | degradado=False
6. Trace oficial: 5 interações Mensagem -> Resposta
   - Orquestrador -> Agente Fluxo
   - Orquestrador -> Agente RU
   - Orquestrador -> Agente Validador (Fluxo)
   - Orquestrador -> Agente Validador (RU)
   - Orquestrador -> Sintetizador
```

O classificador marcou p=0.3503, abaixo do limiar 0.39. A proteção de cruzamento entre os domínios ainda identificou RU + Fluxo e acionou a decomposição.

### Resposta final registrada

**Agente Fluxo — pré-requisitos de Testes de Software**

> Para cursar Testes de Software (FGA0314), é preciso ter cursado antes Requisitos de Software (FGA0313) [1][5].

Fontes desta parte: fluxograma de Engenharia de Software (documento F16), página 1.

**Agente RU — horário de funcionamento**

> O horário de funcionamento do Restaurante Universitário (RU) Gama/FCTE para o café da manhã é das 7h às 9h30, de segunda a sexta-feira, exceto feriados. [5]

Fonte desta parte: Unidades do RU e horários de funcionamento (inclui RU Gama/FCTE) (documento F03), página 1.

Os números de citação são locais a cada parte; a fonte do RU não aparece na resposta de Fluxo, nem o inverso.

<p class="legenda">Tabela 1. Resultado real da execução multiagente com Ollama: dois especialistas, duas validações aprovadas e fontes separadas.</p>

---

## Caso 2 — Falha simulada em um especialista

O argumento --falhar-agente ru simula uma indisponibilidade para exercitar a degradação controlada:

```bash
RUMO_BUSCA=bm25 python -m rumo_rag "Quais os pré-requisitos de Testes de Software e que horas abre o RU?" --agentes --trace --backend ollama --falhar-agente ru
```

Na execução, o Agente Fluxo respondeu e foi aprovado; o Agente RU falhou intencionalmente. O trace marcou a composição como degradado=True, manteve a resposta saudável de Fluxo e mostrou um aviso para a parte do RU. A falha de um agente não apagou o resultado do outro.


??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Registro inicial dos traces e simulações de falha multiagente | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Renomeação para demonstracao.md e padronização das evidências | @maykonjuso |
    | 1.2 | 18/11/2026 | @keilogger | Inclusão do trace real com Ollama, das respostas finais da execução pela CLI | — |
