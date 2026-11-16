# Demonstração Executada

Esta página registra execuções reais do protótipo multiagente via terminal, comprovando a execução em paralelo entre especialistas, o isolamento das citações por assunto, a correção automática quando o validador reprova um dado, a entrega parcial quando um agente falha e o encaminhamento em linguagem natural.

!!! warning "Execução determinística com modo extrativo (aguardando #41, #42 e #43)"
    As execuções abaixo foram feitas no modo extrativo (`--backend extrativo`) com modelos locais offline (`HF_HUB_OFFLINE=1`) para validar de forma reproduzível a coordenação do Orquestrador, a conferência do Agente Validador e a composição pelo Sintetizador. A demonstração completa usando modelo generativo com as instruções dedicadas de cada agente aguarda a conclusão das issues **#41**, **#42** e **#43** (`[a preencher]`).

---

## Caso 1 — Pergunta composta executada em paralelo (RU e Fluxo)

Comando executado no terminal dentro da pasta `rag/`:

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo
```

Saída registrada pelo rastreamento passo a passo:

```text
1. Classificação/Decomposição: composta=True (p=0.0, limiar=0.39, 1.915s)
   - Subpergunta 1: O que tem no almoço
   - Subpergunta 2: quais os pré-requisitos de Testes de Software
2. Roteamento (2 execução(ões)):
   - "O que tem no almoço" -> ru
   - "quais os pré-requisitos de Testes de Software" -> fluxo
3. Execução em paralelo: tempo_total=3.683s | soma_individual=7.271s | ganho=3.588s
   - [Agente RU] 3.596s · OK (5 trechos)
   - [Agente Fluxo] 3.675s · OK (5 trechos)
4. Validador factual: ru: APROVADO, fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=False
```

### Evidências observadas na resposta final

A **Tabela 1** traduz as métricas obtidas e identifica os documentos oficiais citados nos dois blocos entregues ao estudante.

| Critério verificado | Resultado observado na execução | O que isso comprova |
|---|---|---|
| **Divisão da pergunta composta** | Separou *"O que tem no almoço"* e *"quais os pré-requisitos de Testes de Software"* em dois atendimentos | Identificou corretamente dois assuntos independentes na mesma consulta |
| **Paralelismo real** | Tempo total de `3,683 s` contra soma individual de `7,271 s` (`3,596 s + 3,675 s`, economia de `3,588 s`) | Os dois especialistas trabalharam ao mesmo tempo, reduzindo quase pela metade o tempo total |
| **Fontes separadas por assunto** | A parte do RU citou os documentos *Cardápio semanal do RU Gama — 02/11 a 08/11/2026* e *09/11 a 15/11/2026*; a parte de Fluxo citou o documento *Fluxograma de Engenharia de Software (235 créditos) — transcrição* | Cada assunto manteve sua própria numeração iniciada em 1 e sua própria lista de fontes, sem misturar referências |
| **Validação factual** | Ambas as partes foram aprovadas pelo Agente Validador | Nenhuma resposta trouxe valores sem respaldo ou deixou de citar a fonte oficial |

<p class="legenda">Tabela 1. Síntese das evidências obtidas no Caso 1 durante execução paralela sem falhas.</p>

---

## Caso 2 — Validador reprova informação inventada e devolve ao Sintetizador

O retorno entre o **Agente Validador** e o **Sintetizador** é comprovado pelo teste automatizado `test_validador_reprova_valor_inventado_e_devolve_ao_sintetizador` em `rag/testes/test_orquestrador.py`:

1. Quando o Agente Validador identifica algum número ou dado específico sem respaldo nos trechos recuperados, ou percebe que a resposta omitiu citações, ele reprova o bloco e solicita devolução ao Sintetizador.
2. Ao receber a devolução, se a resposta original veio de um modelo generativo e houver trechos oficiais disponíveis, o Sintetizador gera automaticamente uma versão extrativa literal baseada apenas nesses trechos.
3. Caso não existam trechos suficientes ou o bloqueio persista, o Sintetizador aplica a frase padrão de recusa e inclui um aviso explícito da validação junto ao bloco.

!!! info "Registro ao vivo de reprovação com modelo generativo"
    A gravação completa de um trace ao vivo exibindo uma reprovação durante geração em modelo de linguagem aguarda a conclusão das instruções dedicadas nas issues `#41`–`#43` (`[a preencher]`).

---

## Caso 3 — Degradação graciosa diante da queda simulada de um agente

Para testar se a resposta saudável continua sendo entregue quando um especialista falha, o comando abaixo simula uma queda intencional no agente do Restaurante Universitário (`--falhar-agente ru`):

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "O que tem no almoço e quais os pré-requisitos de Testes de Software?" \
  --agentes --trace --backend extrativo --falhar-agente ru
```

Saída registrada no terminal:

```text
3. Execução em paralelo: tempo_total=1.798s | soma_individual=1.797s | ganho=0.0s
   - [Agente RU] 0.0s · ERRO (RuntimeError: Falha simulada no agente 'ru')
   - [Agente Fluxo] 1.797s · OK (5 trechos)
4. Validador factual: ru: ignorado (agente falhou) ..., fluxo: APROVADO
5. Composição (Sintetizador): 2 parte(s) · índices [n] isolados=True · degradado=True
```

Enquanto a parte sobre *Testes de Software* foi respondida e validada normalmente citando o *Fluxograma de Engenharia de Software (235 créditos) — transcrição*, o bloco do Restaurante Universitário exibiu o aviso claro abaixo:

```text
⚠ Aviso (Agente RU): não foi possível obter esta parte da resposta (RuntimeError: Falha simulada no agente 'ru').
```

---

## Caso 4 — Roteamento em linguagem natural sem palavras-chave óbvias

Quando a pergunta não contém termos literais como *"RU"*, *"almoço"* ou *"jantar"*, as regras léxicas não conseguem decidir sozinhas e o roteador aciona o classificador neural de domínio (`limiar de confiança = 0,60`):

```bash
cd rag
HF_HUB_OFFLINE=1 ../.venv/bin/python -m rumo_rag \
  "Onde vejo se a comida de hoje tem derivados de leite?" \
  --agentes --trace --backend extrativo
```

Saída registrada pelo rastreamento:

```text
2. Roteamento (1 execução(ões)):
   - "Onde vejo se a comida de hoje tem derivados de leite?" -> ru
3. [Agente RU] 3.929s · OK (5 trechos)
4. Validador factual: ru: APROVADO
```

O sistema encaminhou a dúvida corretamente para o **Agente do RU**, recuperou trechos dos documentos de cardápio semanal do campus Gama (*Cardápio semanal do RU Gama — 02/11 a 08/11/2026* e *09/11 a 15/11/2026*) contendo informações sobre bebidas e ingredientes (*`Leite integral ou Bebida de soja`*) e teve a resposta aprovada pelo validador.

---

## Caso 5 — Demonstração final com agentes especializados (`#41`, `#42` e `#43`)

| Item aguardado | Conteúdo esperado após `#41`, `#42` e `#43` |
|---|---|
| Execução completa com modelo generativo final | `[a preencher]` |
| Exemplo de resposta final produzida pelos agentes especializados | `[a preencher]` |
| Evidência de validação semântica ampliada (`#43`) | `[a preencher]` |

<p class="legenda">Tabela 2. Espaços reservados para a demonstração generativa final após a entrega das issues #41, #42 e #43.</p>

??? abstract "Histórico de revisão"
    | Versão | Data | Autor | Descrição | Revisor |
    |---|---|---|---|---|
    | 1.0 | 16/11/2026 | @GabrielMacielBR | Registro inicial dos traces e simulações de falha multiagente | @keilogger |
    | 1.1 | 16/11/2026 | @GabrielMacielBR | Renomeação para `demonstracao.md`, remoção de lacunas não observadas e inclusão de `[a preencher]` para `#41`–`#43` | @maykonjuso |
    | 1.2 | 16/11/2026 | @GabrielMacielBR | Substituição de códigos de fontes e símbolos internos por descrições dos documentos reais nas explicações e tabelas | @maykonjuso |
