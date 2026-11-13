# RUmo — contexto do projeto

Assistente com RAG para o **Restaurante Universitário** e o **fluxo de disciplinas** das
engenharias da FCTE (campus Gama da UnB). Grupo 04 da Residência em IA, Challenge 2,
conduzido por Challenge Based Learning com Scrum adaptado.

Site: https://maykonjuso.github.io/residencia-grupo-4/

## Onde está o quê

Tudo na branch `main` — documentação e código juntos, de propósito. A `gh-pages` é gerada
pelo workflow `.github/workflows/pages.yml` e **não se edita à mão**.

```
docs/   GitPage em MkDocs Material: as entregas, a visão e o "sobre"
rag/    o protótipo: catálogo de fontes, ingestão, índice, geração e avaliação
```

## O que este produto é

O RUmo responde **só** a partir de documentos oficiais da UnB, cita a fonte de cada
afirmação e recusa o que não está na base. Não é um chatbot que sabe de tudo: a recusa é
funcionalidade, não limitação. Inventar o preço de uma refeição ou um pré-requisito de
disciplina causa dano real a quem perguntou.

## Regras que atravessam todo o código

Quebrar qualquer uma é bug de produto, não questão de estilo. A lista formal está em
[`docs/entrega-1/regras-de-negocio.md`](docs/entrega-1/regras-de-negocio.md) (issue #9).

- **Só fonte oficial**, com URL e data de coleta (RNF01)
- **Toda afirmação cita documento, página e URL** (RF03)
- **Fora da base, recusa**: "Não encontrei essa informação nas fontes da base" (RF04)
- **Nada sai para serviço externo por padrão**: LLM e embeddings locais; API externa só se
  configurada explicitamente (RNF02)
- **Nenhum dado pessoal**: sem login, sem SIGAA, sem registro de identidade (RNF06)

## Convenções

- Código, comentários, commits e documentação em **português**
- Todo trabalho rastreia para um **RF/RNF** de [`docs/entrega-1/escopo.md`](docs/entrega-1/escopo.md)
  ou é tarefa de processo declarada. Sem isso, falta requisito — converse antes de codar
- **Branch própria → PR para `main` → aprovação de pelo menos um colega → merge.**
  Nunca commite direto na `main`
- Nomes de branch: `feat/<slug>` · `fix/<slug>` · `docs/<slug>` · `chore/<slug>`
- Commits no imperativo, com escopo entre parênteses quando ajudar:
  `feat(recuperacao): implementa reescrita de consulta para perguntas compostas`
- O PR sempre cita a issue (`Closes #12`), porque é o que liga o código ao RF e ao épico
- **Mexeu em chunking, embedding, fusão ou prompt? Rode `python -m rumo_rag avaliar` e
  atualize as tabelas de `docs/entrega-2/avaliacao.md` no mesmo PR.** Calibragem sem medição
  é como se descobre, semanas depois, que a mudança piorou o sistema
- Documentação afetada atualizada na mesma mudança, **com linha nova no histórico de revisão
  da página**
- `mkdocs build --strict` tem de passar antes do merge

## Comandos

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd rag
python -m rumo_rag ingerir                      # baixa, extrai, divide, indexa
python -m rumo_rag perguntar "Quanto custa o almoço?"
python -m rumo_rag avaliar                      # métricas de recuperação
python -m rumo_rag demo
python -m unittest discover -s testes -v      # regras de negócio RN-01 a RN-05 (sem GPU)

cd .. && pip install -r requirements-docs.txt
mkdocs serve                                    # :8000
mkdocs build --strict                           # o que o CI cobra
```

## Números e suas fontes de verdade

Não repita número de cabeça: confira na fonte. Divergência entre página e código é o erro
mais caro que esta documentação pode ter.

| Número | Fonte de verdade |
|---|---|
| 36 fontes (F01–F36) | `rag/catalogo.yaml` |
| 1.738 chunks | `rag/dados/chunks.jsonl` |
| 32 perguntas de teste | `rag/avaliacao/perguntas_ouro.jsonl` |
| Hit@1, Hit@5, MRR | `rag/avaliacao/resultado_recuperacao_*.json` |
| Modelos, limiares, pesos, tamanho de chunk | `rag/rumo_rag/config.py` |

A configuração final é a **busca híbrida**, que tem Hit@1 menor que a densa pura
(0,938 contra 0,969). Não é erro: o conjunto de teste quase não tem datas nem códigos, que é
onde o vetor falha, e o grupo preferiu perder MRR médio a errar o dia do cardápio. Está
justificado em `docs/entrega-2/avaliacao.md` — e é pergunta provável da banca.

## Equipe

Maykon Soares (Product Owner, dev · GitPage e integração) · Gabriel Maciel (Scrum Master,
dev · Base de conhecimento) · Kyara Esteves (dev · Geração) · Keila Alves (dev ·
Recuperação) · Gabriella Oliveira (dev · Avaliação).

Os cinco componentes estão divididos entre as cinco pessoas. Antes de mexer em componente que
não é seu, confira de quem é a issue — refatorar o componente de outro sem avisar gera
conflito de merge. Papéis e componentes em [`docs/sobre/equipe.md`](docs/sobre/equipe.md).

## Grupo parceiro

O Grupo 09 cuida do mapeamento da FCTE. São **dois sistemas independentes**: bases, índices e
prompts não são compartilhados, e a integração (Semana 6) é um extra que não pode atrapalhar
as entregas. O contrato proposto está em [`docs/visao/escopo-grupos.md`](docs/visao/escopo-grupos.md).
