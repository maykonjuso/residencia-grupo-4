# Critérios de Prontidão (DoR) e Conclusão (DoD)

Definições de qualidade, maturidade e aceite para tarefas e entregas do **Grupo 04** no Challenge 2.

**Épico relacionado:** #2 · Definição do processo e fluxo de trabalho do grupo.

---

## 1. Contexto e motivação

Em um ciclo acelerado com sprints semanais de 7 dias e entregas pontuais às sextas-feiras, a clareza sobre o início e o término de uma tarefa é indispensável:

- **Sem DoR (*Definition of Ready*):** entra issue na sprint que ninguém sabe verificar, com dependências não atendidas ou premissas vagas, gerando bloqueios e retrabalho no meio da semana.
- **Sem DoD (*Definition of Done*):** "pronto" passa a ter significado diferente para cada pessoa da equipe — e divergências graves aparecem na Sprint Review de sexta-feira.

A **Figura 1** ilustra o ciclo de vida de uma issue, mapeando as duas barreiras de qualidade: o DoR como portão de entrada para a sprint e o DoD como critério de aceite para o merge e aprovação da entrega.

```mermaid
flowchart LR
    A["Backlog de Demandas<br>(Issues propostas)"] -->|Validação do DoR<br>no Planning| B["Sprint Backlog<br>(Issue Pronta para Executar)"]
    B -->|Desenvolvimento<br>Assíncrono + Dailies| C["Pull Request Aberto<br>(Branch da funcionalidade)"]
    C -->|Checklist do DoD<br>+ Review por Pares| D["Merge na main<br>+ GitPage publicada"]
    D -->|Sprint Review<br>(Sexta-feira)| E["Aceite pelo PO<br>(Concluído)"]
```

<p class="legenda">Figura 1. Fluxo de ciclo de vida da issue do DoR ao DoD.</p>

---

## 2. Definition of Ready (DoR) — Portão de entrada

Uma issue só pode ser puxada para o *Sprint Backlog* durante o Sprint Planning de segunda-feira se cumprir **todos** os critérios da **Tabela 1**. Se algum item falhar, a issue permanece no Product Backlog para refinamento.

| Critério | Descrição | Como validar |
|---|---|---|
| **Rastreabilidade de requisitos** | Rastreia diretamente para um RF ou RNF de [Escopo e requisitos](../entrega-1/escopo.md) ou é tarefa de processo declarada. | Conferir código do RF/RNF (ex: RF03, RNF01) indicado na issue. |
| **Critério de verificação objetivo** | Possui forma clara e demonstrável de verificação (comportamento observável ou métrica). | Passos reprodutíveis descritos no campo "Como verificar" da issue. |
| **Vínculo com Épico** | Está formalmente vinculada a um épico ativo do projeto. | Tag ou menção expressa ao épico (ex: Épico #2). |
| **Estimativa e viabilidade** | Possui tamanho relativo estimado (**P / M / G**) e cabe integralmente dentro de uma semana. | Estimativa preenchida conforme a [matriz de tamanhos](processo.md#5-estimativa-de-esforco-p-m-g). Tarefas maiores que **G** devem ser fatiadas. |
| **Responsável definido** | Possui um dono atribuído ([dono de componente](equipe.md)). | Campo *Assignee* preenchido no GitHub. |
| **Dependências disponíveis** | Insumos técnicos necessários estão previamente prontos (fonte coletada no `catalogo.yaml`, modelo baixado, GPU liberada). | Nenhuma dependência externa bloqueante em aberto. |
| **Alinhamento com mapa de riscos** | Riscos técnicos identificados estão associados ao [mapa de riscos](../entrega-1/riscos.md), quando aplicável. | Menção ao risco correspondente (ex: RSK02) e plano de mitigação. |
| **Consenso da equipe** | Nenhum integrante do grupo possui dúvida aberta ou discordância sobre o escopo da tarefa. | Discussão validada no Planning presencial na Sala 313. |

<p class="legenda">Tabela 1. Matriz de critérios da Definition of Ready (DoR).</p>

### Checklist do DoR

Para agilizar o planejamento, o checklist abaixo é integrado ao template padrão de issues do repositório:

- [ ] Rastreia para um RF ou RNF de [`docs/entrega-1/escopo.md`](../entrega-1/escopo.md), ou é tarefa de processo declarada
- [ ] Tem forma objetiva de verificação (comportamento observável ou métrica)
- [ ] Está ligada a um épico
- [ ] Tem tamanho estimado (P / M / G) e cabe em uma semana
- [ ] Tem dono atribuído ([donos de componente](equipe.md))
- [ ] Dependências identificadas e disponíveis (fonte coletada, modelo baixado, GPU livre)
- [ ] Riscos ligados ao [mapa de riscos](../entrega-1/riscos.md), quando houver
- [ ] Ninguém do grupo tem dúvida aberta sobre ela

---

## 3. Definition of Done (DoD) — Critério de aceite

Uma funcionalidade ou documento só é considerado "pronto" (*Done*) quando atende a todos os critérios listados na **Tabela 2**. A verificação ocorre no Pull Request e na Sprint Review de sexta-feira.

| Critério | Descrição | Onde é validado |
|---|---|---|
| **Demonstração em execução** | O comportamento do requisito está implementado, testado e demonstrável localmente. | Terminal / Protótipo (`python -m rumo_rag demo`). |
| **Revisão por pares (Code Review)** | Código submetido via Pull Request para a branch `main`, aprovado por pelo menos um colega de equipe. | GitHub PR com *Approve* formal. |
| **Citação de fontes e recusa (RF03/RF04)** | Toda resposta gerada cita documento oficial, página e URL. Se a resposta não estiver na base, recusa expressamente. | Verificação manual e testes do módulo de geração. |
| **Requisitos não-funcionais (RNF)** | Conformidade com RNF01–RNF06: sem envio não autorizado de dados externos e sem armazenamento de dados pessoais. | Inspeção de código e logs de rede. |
| **Calibração com medição no mesmo PR** | Qualquer mudança em chunking, embedding, busca híbrida ou prompt exige rodar a avaliação e atualizar os resultados no mesmo PR. | `python -m rumo_rag avaliar` e atualização das tabelas de métricas. |
| **Documentação sincronizada** | Documentação afetada atualizada na GitPage, com nova linha inserida na tabela de histórico de revisão da página. | Arquivos `.md` correspondentes em `docs/`. |
| **Integridade de build do MkDocs** | A compilação estrita passa sem qualquer erro, aviso ou link quebrado. | Execução de `mkdocs build --strict`. |
| **Aprovação na Sprint Review** | Incremento apresentado na Sprint Review de sexta-feira e formalmente aceito pelo Product Owner. | Aceite na reunião de fechamento de sprint. |

<p class="legenda">Tabela 2. Matriz de critérios da Definition of Done (DoD).</p>

### Aferição obrigatória no mesmo PR: por que é indispensável?

O item sobre medição de métricas no mesmo Pull Request é uma regra inegociável da engenharia do RUmo:

> Calibragem de parâmetros sem medição imediata gera regressões silenciosas no sistema RAG. Alterações que aparentemente melhoram uma resposta pontual podem degradar a recuperação média (Hit@1 e MRR) ou aumentar alucinações em outras consultas. Portanto, **toda modificação em extração, chunking, embeddings ou prompt deve conter o resultado de `python -m rumo_rag avaliar` commitado no mesmo PR**.

### Checklist do DoD

Checklist incorporado em `.github/pull_request_template.md`:

- [ ] O comportamento do requisito foi implementado e **demonstrado rodando**
- [ ] Código em PR, aprovado por pelo menos um colega
- [ ] **A resposta cita a fonte de cada afirmação e recusa o que não está na base** (RF03, RF04)
- [ ] RNF01–RNF06 aplicáveis respeitados
- [ ] Mexeu em chunking, embedding ou prompt? A avaliação foi rodada de novo e a linha de base atualizada **no mesmo PR**
- [ ] Documentação afetada atualizada na GitPage, com linha nova no histórico da página
- [ ] `mkdocs build --strict` passa localmente sem erros ou avisos
- [ ] Apresentada na Sprint Review de sexta-feira e aceita pelo PO

---

## 4. Modelos e automação no GitHub

Para facilitar o cumprimento desses critérios no dia a dia sem burocracia manual, ambos os acordos estão automatizados nos templates do repositório:

- **DoR nas Issues:** O arquivo [`.github/ISSUE_TEMPLATE/tarefa.md`](https://github.com/maykonjuso/residencia-grupo-4/blob/main/.github/ISSUE_TEMPLATE/tarefa.md) carrega automaticamente o checklist de prontidão a cada nova demanda criada.
- **DoD nos Pull Requests:** O arquivo [`.github/pull_request_template.md`](https://github.com/maykonjuso/residencia-grupo-4/blob/main/.github/pull_request_template.md) carrega a lista de verificação de conclusão exigida antes do merge na branch `main`.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Criação formal das matrizes de DoR e DoD (Épico #2), checklists integrados e justificativa de calibração com métricas | Grupo 04 |
