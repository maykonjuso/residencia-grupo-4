# Base de conhecimento

A base tem **36 documentos-fonte**, todos públicos e de órgãos oficiais, coletados em **06/11/2026**. O catálogo completo, com metadados, está em [`rag/catalogo.yaml`](https://github.com/maykonjuso/residencia-grupo-4/blob/main/rag/catalogo.yaml); cada documento tem um ID estável (F01 a F36), usado nas citações das respostas.

## Critérios de curadoria

A seleção e validação das fontes seguiram os seis critérios descritos na **Tabela 1**.

| Critério | Regra aplicada |
|---|---|
| Autoridade | Só fontes oficiais: UnB (CAD, CEPE, DAC, DDS, DRU, SAA, DEG, FCTE, coordenações), Presidência da República, Ministério da Saúde, ANVISA |
| Pertinência | O documento responde a pelo menos uma pergunta típica do RU ou do fluxo de disciplinas do campus Gama |
| Atualidade | Versão vigente mais recente encontrada; documentos antigos só quando ainda estão em vigor (ex.: CEPE 93/2018) |
| Rastreabilidade | URL original, órgão e data guardados no catálogo e copiados para cada chunk |
| Legibilidade | O texto precisa ser extraível; o que só existe em imagem foi transcrito e marcado como transcrição |
| Sem duplicata | Uma cópia por documento (a Resolução CAD 37/2025 aparecia em dois sites; ficou a do RU) |

<p class="legenda">Tabela 1. Critérios de curadoria.</p>

## Documentos da base

As tabelas a seguir (divididas nos eixos **RU**, **Fluxo de disciplinas** e **Apoio**) são geradas automaticamente a partir do catálogo e do índice (`rag/gerar_tabela_fontes.py`).

--8<-- "includes/tabela_fontes.md"

## Cobertura por curso do campus Gama

A **Tabela 2** detalha como os documentos cobrem os cinco cursos de graduação da FCTE, o mestrado em Engenharia Biomédica (PPGEB) e as normas acadêmicas comuns.

| Curso | Nível | Fontes na base | Grade disponível como |
|---|---|---|---|
| Engenharia Aeroespacial | Graduação | PPC 2025 (F17), apresentação out/2026 (F18) | Texto do PPC |
| Engenharia Automotiva | Graduação | Estrutura curricular (F19), informações gerais (F20) | Página com abas (duas grades: até 2026 e a partir de 2027) |
| Engenharia Eletrônica | Graduação | PPC 2023 (F21) | Texto do PPC |
| Engenharia de Energia | Graduação | Informações gerais (F22), matriz (F23) | Imagem → transcrição do grupo |
| Engenharia de Software | Graduação | Matriz e créditos (F15), fluxograma (F16) | Imagem → transcrição do grupo |
| Engenharia Biomédica (PPGEB) | Mestrado | Apresentação, matriz, aluno de graduação, linhas, edital (F24–F28) | Página do programa |
| Comum a todos | — | ABI (F14), calendário (F29, F30), trancamento (F31), matrícula (F32–F34), regimentos (F35, F36) | Texto |

<p class="legenda">Tabela 2. Cobertura das engenharias e do PPGEB.</p>

## Documentos avaliados e não incluídos

Durante o levantamento, alguns materiais foram analisados e descartados desta versão da base pelos motivos registrados na **Tabela 3**.

| Documento | Motivo |
|---|---|
| TACO (Tabela Brasileira de Composição de Alimentos, NEPA/Unicamp) | Tabela de várias colunas que vira sequência de números sem rótulo na extração; entra na Semana 5 como dado estruturado, não como texto |
| RDC 429/2020 e IN 75/2020 (rotulagem nutricional, ANVISA) | Relevantes para a leitura de rótulos (multimodal, Semana 5), não para as perguntas desta entrega |
| Matéria "O que você precisa saber sobre o RU da UnB" (Quero Bolsa) | Fonte secundária e com preços antigos |
| Regimento do RU de 2020 | Substituído pela Resolução DAC 002/2024 (F02) |
| PPC de Engenharia de Software (SIGAA) | Link oficial não respondeu durante a coleta; a grade veio do fluxograma oficial (F16) |
| Guia de Atividade Física (Ministério da Saúde) | Fora do escopo do RU e do fluxo |

<p class="legenda">Tabela 3. Exclusões justificadas.</p>

## Transcrições curadas

Dois cursos publicam a grade **só como imagem**. O grupo transcreveu as duas para texto estruturado, mantendo a fonte, a data e um aviso de que a referência final é o SIGAA:

- **F16 · Fluxograma de Engenharia de Software:** 10 semestres, 235 créditos, códigos, créditos T-P-E-Total, códigos antigos e uma linha de pré-requisito por disciplina, lida das setas (setas tracejadas marcadas como tais).
- **F23 · Matriz de Engenharia de Energia:** 10 semestres, 251 créditos, ciclo de cada disciplina (básico, profissionalizante, específico, PI, TCC/estágio).
