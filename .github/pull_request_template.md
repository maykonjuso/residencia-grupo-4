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

- [ ] O comportamento do requisito foi implementado e **demonstrado rodando**
- [ ] Código em PR, aprovado por pelo menos um colega
- [ ] **A resposta cita a fonte de cada afirmação e recusa o que não está na base** (RF03, RF04)
- [ ] RNF01–RNF06 aplicáveis respeitados
- [ ] Mexeu em chunking, embedding ou prompt? A avaliação foi rodada de novo e a linha de base atualizada **no mesmo PR**
- [ ] Documentação afetada atualizada na GitPage, com linha nova no histórico da página
- [ ] `mkdocs build --strict` passa localmente sem erros ou avisos
- [ ] Apresentada na Sprint Review de sexta-feira e aceita pelo PO
