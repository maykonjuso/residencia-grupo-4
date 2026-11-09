A **Tabela 2** sintetiza o desempenho da recuperação, da geração e da verificação de fontes nas oito consultas da demonstração (`D1` a `D8`).

| ID | Pergunta (resumo) | Recuperação | Resposta | Fontes | Avaliação |
|---|---|---|---|---|---|
| D1 | Preço do almoço (graduação) | Chunk do Grupo II em 1º | R$ 4,50, Grupo II | F04 | <span class="selo selo--verde">correta</span> |
| D2 | Vegetariano estrito, quarta 11/11 | Almoço de 11/11 em 1º | Abobrinha recheada com lentilha ao sugo | F09 p.2 | <span class="selo selo--verde">correta</span> |
| D3 | Quem come de graça | Resolução CAD 37/2025 em 1º, 2º e 3º | Cita só o Programa Auxílio Alimentação | F06 | <span class="selo selo--laranja">incompleta</span> |
| D4 | Pré-requisito de Testes de Software | Linhas de pré-requisito em 1º e 2º | Requisitos de Software (FGA0313), com a ressalva da seta tracejada vinda de MDS | F16 | <span class="selo selo--verde">correta</span> |
| D5 | Termodinâmica 1 e créditos de Energia | 5º semestre em 1º | 5º semestre; 251 créditos | F23 | <span class="selo selo--verde">correta</span> |
| D6 | Disciplina do mestrado (PPGEB) | Página "aluno de graduação" em 1º e 2º | Passo a passo completo | F26 | <span class="selo selo--verde">correta</span> |
| D7 | Wifi da biblioteca | Nenhum trecho responde | "Não encontrei essa informação nas fontes da base." | — | <span class="selo selo--verde">recusa correta</span> |
| D8 | Preço **e** horário (pergunta composta) | Horário recuperado; preço não | Horário certo, mas sem citação; diz que não encontrou o preço | — | <span class="selo selo--laranja">parcial</span> |

<p class="legenda">Tabela 2. Resultado das 8 consultas: 6 corretas (incluindo a recusa), 2 parciais e nenhuma com valor inventado.</p>

**O que funcionou**

- Os valores e datas das respostas estão todos nos trechos (o verificador não deu alerta nesta rodada).
- Quando faltou base (D7) ou a busca não trouxe o trecho (preço em D8), o modelo **disse que não encontrou**, em vez de inventar.
- Os casos que dependem de identificador exato (data em D2, código em D4) acertaram graças à busca híbrida.

**O que ainda falha e como vamos tratar**

A **Tabela 3** detalha as limitações identificadas nas consultas parciais (`D3` e `D8`) e as correções previstas para a próxima etapa.

| Caso | Problema | Correção planejada |
|---|---|---|
| D3 | O LLM usou só 1 dos 5 trechos e deixou de fora a lista do Grupo I da Resolução CAD 37/2025, que estava no contexto | Instrução para "considerar todos os trechos relevantes"; comparar com um modelo maior via API na Semana 3 |
| D8 | "Sem auxílio" puxa documentos do auxílio, e o chunk de preço não entra no top 8; o horário veio sem citação | Reescrita da consulta pelo LLM antes da busca (tirar a negação, separar as perguntas); exigir citação em toda frase factual |

<p class="legenda">Tabela 3. Falhas observadas e correções planejadas para a Semana 3.</p>

!!! info "Histórico das rodadas"
    Numa rodada anterior, com o mesmo modelo 7B mas antes das últimas correções, a D8 respondeu "R$ 10,00" e "R$ 12,00", valores que não existem em nenhuma fonte, e ainda citou um trecho. Foi esse caso que levou à criação do **verificador de fidelidade**. Ao rodar o verificador sobre aquela resposta, ele marca exatamente esses dois valores. Com o modelo de 1,5B, a primeira versão errava também D1, D2 e D4.

**Tempo:** a busca leva de 0,04 a 0,1 s. A primeira consulta (D1) inclui o carregamento do modelo de embedding (cerca de 11 s). A geração leva de 3 a 26 s por resposta na RTX 4060.
