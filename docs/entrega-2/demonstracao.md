---
hide:
  - navigation
---

# Demonstração

O enunciado pede quatro evidências. Todas aparecem em cada consulta abaixo, que são **saídas reais** do protótipo (`python -m rumo_rag demo`, gravadas em `rag/avaliacao/demo_respostas.json`).

| Evidência pedida | Onde aparece em cada consulta |
|---|---|
| Consulta submetida ao sistema | Bloco de terminal com a pergunta |
| Recuperação dos chunks mais relevantes | Tabela com chunk, documento, página, seção e similaridade |
| Resposta fundamentada no conteúdo recuperado | Caixa "Resposta gerada", com citações [n] |
| Evidência das fontes utilizadas | Lista "Fontes citadas", com link para o documento original, mais o selo do verificador de fidelidade |

<p class="legenda">Tabela 1. Evidências pedidas e onde estão.</p>

## Explorar de forma interativa

<div id="rm-explorador" class="rm-explorador" aria-live="polite"></div>

## Como cada resposta é verificada

Além das citações [n], cada resposta passa por um **verificador de fidelidade** (`geracao.valores_sem_fonte`). Todo preço, data, horário, código de disciplina ou quantidade (créditos, horas, vagas) que aparece na resposta é procurado nos trechos recuperados. Se algum não aparece, a resposta recebe um alerta. Esse é o tipo de erro mais perigoso para o estudante, e o verificador pegou um caso real nesta demonstração (D8).

## Análise das respostas

--8<-- "includes/demo_analise.md"

## Consultas completas

--8<-- "includes/demo_respostas.md"
