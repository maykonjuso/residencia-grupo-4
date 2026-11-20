# Base de conhecimento

A base tem **37 documentos-fonte**, todos públicos e de órgãos oficiais, coletados em **06/11/2026**. Na Entrega 2 eram 36; a página "Serviço alimentação" do RU (F37) entrou pela Issue #55 (18/11/2026). O catálogo completo, com metadados, está em [`rag/catalogo.yaml`](https://github.com/maykonjuso/residencia-grupo-4/blob/main/rag/catalogo.yaml); cada documento tem um ID estável (F01 a F37), usado nas citações das respostas.

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

## Alergênicos e informação nutricional (Issue #55)

Perguntas como *"a lasanha tem glúten?"* ou *"qual o prato menos calórico?"* dependem de dados por prato. A **Tabela 4** resume o que o RU publica, conferido em 18/11/2026 no site do RU e nos PDFs dos cardápios do Gama.

| Informação | O RU publica? | Onde |
|---|---|---|
| Calorias e nutrientes por prato | **Não** | Nem no site nem no PDF do cardápio |
| Alergênicos por prato | **Sim**, por ícones | PDF do cardápio semanal, com legenda no rodapé de cada página |
| Atendimento a dietas especiais | **Não**, por declaração oficial | Página "Serviço alimentação" (F37) |

<p class="legenda">Tabela 4. Informação nutricional e de alergênicos publicada pelo RU.</p>

A página do RU (F37) diz que *"preparações que contenham leite de origem animal, ovos, glúten, cogumelo, mel, soja, pimenta, sementes oleaginosas, carne suína e/ou frutos do mar em seus ingredientes estão identificadas no cardápio e na distribuição aos usuários"* e que *"não há previsão de atendimento para usuários com necessidade de dietas especializadas e/ou individualizadas"*.

**Decisões tomadas:**

- **Calorias não entram na base.** O RU não publica calorias, e nenhum valor é estimado. Para *"qual o prato menos calórico?"*, o RUmo recusa. Declarar a limitação é aceitável; inventar um número é defeito.
- **Alergênicos vêm dos ícones do cardápio oficial, sem inferência pelo nome do prato.** O cardápio marca cada preparação com ícones (Cogumelo, Leite e derivados, Mel, Pimenta, Soja, Trigo/Glúten, Amendoim, Oleaginosa, Ovo, Suíno). O módulo `rag/rumo_rag/alergenos.py` compara cada ícone da tabela com os da legenda da própria página e o liga à **opção de prato** dentro da célula, e não à célula inteira: em *"Rosé / Limão"*, os ícones de leite e ovo são do Rosé. Inferir pelo nome teria errado: o *Requeijão de ervas* (vegetariano estrito) não tem ícone de leite no cardápio oficial.
- **Um formato só, o do cardápio estruturado (#54).** No texto do cardápio, cada opção ganha a etiqueta logo depois do nome, por exemplo *"Rosé [Alergênicos: Leite e derivados, Ovo] / Limão"*. O RUmo responde citando o cardápio, e `rag/rumo_rag/coleta/cardapio.py` transforma a etiqueta no campo `alergenicos` de cada opção do JSON de montagem de prato, usado pelo monta-prato (#63) e pela interface.
- **Ícone duvidoso não vira afirmação.** Se a comparação com a legenda não for clara, a etiqueta diz *"a conferir na distribuição"*, o alergênico duvidoso não é afirmado e o JSON registra um aviso. Nas semanas da base, nenhum ícone ficou duvidoso.

**Como foi conferido.** As 6 páginas dos cardápios da base (F08 e F09) foram conferidas à mão contra a imagem, opção por opção. Os casos conferidos viraram teste automático (`rag/testes/test_alergenos.py`). A primeira versão da leitura de ícones, que anotava a célula inteira, errava 87 das 306 opções comparáveis; a versão atual erra 0. Uma terceira semana, fora da base (16 a 20/11/2026), foi usada só como prova: no almoço e no jantar, todos os ícones bateram com a imagem.

**Limitações declaradas:**

- A legenda do RU Gama **não tem ícone de peixe nem de frutos do mar**, embora a página do RU cite frutos do mar. O *Filé de peixe ao molho de ervas* (04/11) não tem nenhum ícone.
- O cardápio está sujeito a alterações sem aviso prévio. Os ícones valem para o cardápio publicado, não para o que foi servido.
- "Leite e derivados" é a categoria do RU. O cardápio não diz se há opção sem lactose.
- Na busca só por palavras (BM25, o modo usado em produção), *"o RU tem opção para quem tem doença celíaca?"* não recupera a F37, porque a página fala em *"dietas especializadas"* e não em *celíaca*. A medição com a busca híbrida está pendente (ver [Avaliação](avaliacao.md#alergenicos-por-prato-issue-55)).

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 09/11/2026 | 1.0 | Base com 36 documentos-fonte (Entrega 2) | Grupo 04 |
    | 18/11/2026 | 1.1 | 37 documentos: F37 (serviço de alimentação do RU), alergênicos por prato lidos dos ícones do cardápio, calorias declaradas como lacuna (Issue #55) | Grupo 04 |
