## O que muda

<!-- Descreva resumidamente o que foi feito e quais issues este PR resolve. -->
Resolve #
Closes #

## Requisito / Épico

<!-- Indique o épico ou requisito relacionado (ex: Épico #2, RF01, RNF03). -->

## O que tem em cada arquivo

<!-- Liste os arquivos alterados com uma breve explicação do motivo. -->
- **`arquivo`** — descrição da mudança

## Como verificar

<!-- Comandos ou passos para reproduzir e testar localmente. -->
```bash
mkdocs build --strict
# ou
python -m rumo_rag demo
```

## Checklist (Definition of Done)

- [ ] O comportamento está implementado e demonstrável
- [ ] RNF aplicáveis respeitados
- [ ] Se mexeu em chunking, embedding, fusão ou prompt: rodou a avaliação (`python -m rumo_rag avaliar`) e atualizou as tabelas de métricas no mesmo PR
- [ ] A documentação reflete fielmente o código (sem divergências de números ou fontes)
- [ ] Diagramas e tabelas conferidos no MkDocs (`mkdocs serve` / `mkdocs build --strict`)
- [ ] Revisão de pelo menos um colega de equipe
