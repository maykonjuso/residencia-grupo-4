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

- [ ] O comportamento do requisito está implementado e **demonstrável**
- [ ] A resposta cita a fonte de cada afirmação e recusa o que não está na base (RF03, RF04)
- [ ] RNF01–RNF06 aplicáveis respeitados
- [ ] Mexi em chunking, embedding, fusão ou prompt? Rodei `python -m rumo_rag avaliar` e
      atualizei as tabelas de `docs/entrega-2/avaliacao.md` **neste PR**
- [ ] Documentação afetada atualizada, com linha nova no histórico de revisão da página
- [ ] `mkdocs build --strict` passa
- [ ] Revisado por pelo menos um colega
