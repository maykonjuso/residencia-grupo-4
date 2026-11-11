## O que muda

<!-- Descreva resumidamente o que foi feito neste Pull Request e quais issues ele resolve. -->
Closes #
Resolve #

## Tipo de mudança

- [ ] `feat`: Nova funcionalidade no código do protótipo
- [ ] `fix`: Correção de bug ou falha de recuperação/geração
- [ ] `docs`: Criação ou atualização de documentação na GitPage
- [ ] `chore`: Infraestrutura, dependências, scripts ou automação

## Requisito, Épico e Componente

- **Épico / Requisito:** <!-- Ex: Épico #2, RF03, RNF01 -->
- **Componente afetado:** <!-- Base de conhecimento | Recuperação | Geração | Avaliação | GitPage e integração -->
- **Tamanho estimado:** <!-- P | M | G -->

## O que tem em cada arquivo

<!-- Liste os arquivos alterados com uma breve explicação do motivo. -->
- **`caminho/do/arquivo`** — descrição da mudança

## Como verificar localmente

<!-- Comandos ou passos para reproduzir e testar localmente. -->
```bash
# Validação da documentação:
mkdocs build --strict

# Validação do protótipo RAG (se aplicável):
cd rag
python -m rumo_rag demo
python -m rumo_rag avaliar
```

## Checklist (Definition of Done - DoD)

- [ ] **Requisito demonstrável:** O comportamento do requisito está implementado, testado e demonstrável.
- [ ] **Regras inegociáveis do RUmo:**
  - [ ] Toda afirmação cita documento oficial, página e URL (RF03 / RNF01).
  - [ ] Fora da base, recusa expressamente sem inventar informações (RF04).
  - [ ] Nenhum dado sensível/pessoal coletado e sem chamadas externas não autorizadas (RNF02, RNF06).
- [ ] **Aferição de métricas:** Mexeu em chunking, embedding, fusão ou prompt? Rodou `python -m rumo_rag avaliar` e atualizou as tabelas de métricas na documentação neste mesmo PR.
- [ ] **Documentação e integridade:**
  - [ ] Páginas afetadas atualizadas com nova linha no histórico de revisão.
  - [ ] `mkdocs build --strict` executa com sucesso (sem warnings ou links quebrados).
- [ ] **Revisão por pares:** Revisado e aprovado por pelo menos um colega (preferencialmente o responsável pelo componente afetado).
