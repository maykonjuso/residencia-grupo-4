# Big Idea e Essential Question

O Challenge 2 segue o modelo CBL (*Challenge Based Learning*): parte de uma **Big Idea**, cada grupo formula a sua **Essential Question** e daí sai o **Challenge**.

## Big Idea

> **Qualidade de vida.** *Empoderando pessoas com IA para compreender melhor, decidir melhor e viver melhor.*

## Challenge Statement (comum a todos os grupos)

> Projetar e desenvolver uma solução baseada em IA capaz de apoiar a tomada de decisão em um contexto relacionado à qualidade de vida.

Restrições do desafio e como o RUmo atende a cada uma:

| Restrição do Challenge | Como o RUmo atende |
|---|---|
| Entender o problema antes da solução | [Problema](../entrega-1/problema.md) e [partes interessadas](../entrega-1/stakeholders.md) definidos na Entrega 1, antes do código |
| Justificar decisões técnicas | Chunking, embeddings, banco vetorial e busca híbrida justificados com experimento ([avaliação](../entrega-2/avaliacao.md)) |
| Explicitar riscos e limitações | [Riscos e limitações](../entrega-1/riscos.md), mais os casos de falha mostrados na [demonstração](../entrega-2/demonstracao.md) |
| Validar com métricas objetivas | Hit@1, Hit@5 e MRR em 32 perguntas com resposta conhecida; taxa de recusa fora da base ([métricas](../entrega-1/metricas.md)) |
| Utilizar evidências confiáveis | Só fontes oficiais (UnB, Ministério da Saúde, ANVISA, Planalto), com URL e data de coleta |

<p class="legenda">Tabela 1. Restrições do Challenge 2 e onde cada uma é tratada.</p>

## Essential Question do Grupo 04

> **Como a IA pode ajudar o estudante da FCTE a decidir melhor onde e o que comer no campus e quais disciplinas cursar, com respostas confiáveis e rastreáveis até as fontes oficiais da UnB?**

### Guiding questions (perguntas-guia)

1. Quais dúvidas sobre o RU e sobre o fluxo de disciplinas o estudante tem com mais frequência, e onde está a resposta oficial de cada uma?
2. Como transformar documentos heterogêneos (resoluções em PDF, cardápio em tabela, fluxograma em imagem, páginas com abas) em uma base que um sistema consiga consultar?
3. Como garantir que a resposta venha do documento e não da "memória" do modelo, e como mostrar isso ao estudante?
4. Como medir se a recuperação de informação está boa antes de pôr o sistema na frente de usuários?
5. Como o nosso sistema conversa com o sistema do Grupo 09 sem os dois virarem um projeto só?

## Challenge do Grupo 04

> Construir um assistente com RAG para o RU e o fluxo de disciplinas do campus Gama que responda **só com base em fontes oficiais**, **cite** cada fonte e **recuse** perguntas sem base, e que exponha uma API para ser chamada pelo orquestrador comum com o Grupo 09.
