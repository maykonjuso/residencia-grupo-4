# Riscos e limitações

## Matriz de riscos

Probabilidade (P) e impacto (I) em escala de 1 a 3. Exposição = P × I.

| ID | Risco | P | I | Exposição | Mitigação | Situação na Entrega 2 |
|---|---|---|---|---|---|---|
| R01 | **Alucinação:** o LLM inventa valores, pratos ou pré-requisitos | 3 | 3 | 9 | RAG com regra de citação obrigatória; resposta "não encontrei" quando falta base; modelo maior (7B) | Observado no modelo 1,5B; o 7B parou de inventar nas perguntas da demo |
| R02 | **Informação desatualizada:** cardápio, preços e editais mudam | 3 | 3 | 9 | Catálogo com data de coleta; data no cabeçalho de cada chunk; atualização semanal (Semana 6) | Base com cardápios de 02/11 a 15/11/2026 |
| R03 | **Extração ruim de PDF/imagem:** tabelas achatadas, ligaduras perdidas, fluxogramas só em imagem | 3 | 2 | 6 | Leitor de tabela para cardápio; correção de ligadura; transcrição curada dos fluxogramas | Tratado; fluxogramas transcritos à mão podem conter erro de leitura |
| R04 | **Pergunta composta ou ambígua** recupera só parte da resposta | 2 | 2 | 4 | Decomposição em subperguntas; reescrita de consulta pelo LLM (Semana 3) | Parcial; caso D8 documentado |
| R05 | **Pré-requisito errado** leva o estudante a planejar mal o semestre | 2 | 3 | 6 | Aviso fixo: a fonte final é o SIGAA; mostrar a fonte de cada pré-requisito | Aviso nas transcrições |
| R06 | **Integração com o Grupo 09 atrasa as entregas** (alerta do mentor) | 2 | 3 | 6 | Sistemas independentes; contrato simples; integração só na Semana 6 | Contrato proposto; nenhuma dependência criada |
| R07 | **Hardware limitado** (GPU de 8 GB) | 2 | 2 | 4 | Quantização em 4 bits; opção de Ollama ou API externa | 7B em 4 bits funcionando |
| R08 | **Dados pessoais / LGPD** | 1 | 3 | 3 | Sem login; sem acesso ao SIGAA; perguntas não ficam associadas a pessoas | Atendido |
| R09 | **Viés de cobertura:** cursos com documentos melhores recebem respostas melhores | 2 | 2 | 4 | Medir acerto por curso; completar fontes (Energia e Software têm grade só em imagem) | A medir na Semana 3 |
| R10 | **Direitos de uso das fontes** | 1 | 2 | 2 | Só documentos públicos de órgãos oficiais, sempre citados | Atendido |

<p class="legenda">Tabela 1. Riscos, mitigação e situação atual.</p>

## Limitações conhecidas

- O RUmo **não substitui** o SIGAA, a SAA nem a Diretoria do RU. Pré-requisitos e grades devem ser confirmados no SIGAA.
- Os ícones de alergênicos do cardápio do RU (leite, glúten, ovo etc.) **são imagens** no PDF e não foram extraídos. Isso fica para a etapa multimodal (Semana 5).
- As transcrições dos fluxogramas de Software e Energia foram feitas pelo grupo a partir de imagens; setas tracejadas foram marcadas como tais.
- As respostas dependem da data de coleta (06/11/2026). Fora desse período, o cardápio na base deixa de valer.
