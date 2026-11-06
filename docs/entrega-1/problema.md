# Problema

## Contexto

A FCTE (antiga FGA, campus Gama da UnB) oferece cinco engenharias de graduação (Aeroespacial, Automotiva, Eletrônica, Energia e Software) e o mestrado em Engenharia Biomédica (PPGEB). O campus tem um Restaurante Universitário próprio, no prédio do MESP, que serve café da manhã, almoço e jantar de segunda a sexta.

O ingresso nas engenharias é feito por **Área Básica de Ingresso (ABI)**: o estudante indica, em ordem de preferência, os cursos da ABI Engenharia ou o curso da área de Computação (Resolução FCTE nº 01/2025). Os primeiros semestres têm disciplinas comuns, e as grades se separam depois.

## O problema

As informações de que o estudante precisa para decidir **o que comer** e **o que cursar** existem e são oficiais, mas:

| Dificuldade | Exemplo real da base |
|---|---|
| Espalhadas em muitos órgãos | Preço do RU (CAD), regimento do RU (DAC), Auxílio Alimentação (DDS), calendário (SAA), trancamento (CEPE), grades (cada coordenação) |
| Em formatos difíceis | Cardápio em PDF com tabela por dia; fluxogramas de Software e Energia **só em imagem**; grade da Automotiva em abas de página web |
| Longas | PPC da Aeroespacial com mais de 450 mil caracteres; PPC da Eletrônica com 263 mil |
| Mudam com frequência | Cardápio novo toda semana; preços mudaram em dezembro de 2025 (CAD 37/2025); duas grades vigentes na Automotiva (antes e depois de 2027) |
| Dependem do perfil | O valor da refeição depende do grupo (I, II, III ou IV); a grade depende do curso e do ano de ingresso |

<p class="legenda">Tabela 1. Por que é difícil achar a resposta hoje.</p>

O resultado é que o estudante pergunta em grupos de WhatsApp, recebe respostas desatualizadas ou erradas, ou desiste de procurar. Um chatbot genérico (LLM sem acesso aos documentos) piora o quadro: ele **inventa** valores, cardápios e pré-requisitos com aparência de verdade.

!!! example "Alucinação observada no próprio projeto"
    No primeiro teste do protótipo, com um modelo pequeno (Qwen2.5-1.5B), o sistema respondeu que o almoço custava "R$ 10,00" e que o prato vegetariano de quarta era "risoto de brócolis". Os valores reais nos documentos são R$ 4,50 (Grupo II) e "abobrinha recheada com lentilha ao sugo". Isso motivou a troca do modelo e as regras de citação obrigatória ([demonstração](../entrega-2/demonstracao.md)).

## Decisões que o RUmo apoia

1. **Alimentação.** Onde e quando comer no campus, quanto vou pagar, se tenho direito à gratuidade e como pedir, o que tem no cardápio e se há opção vegetariana.
2. **Percurso acadêmico.** O que cursar no próximo semestre, o que vem antes de cada disciplina, quantos créditos o curso exige, prazos de matrícula e trancamento, e se posso cursar disciplinas do mestrado.

## Ligação com a Big Idea

Comer bem e com regularidade e manter o curso em dia, sem reprovações por falta de planejamento, são fatores diretos de **qualidade de vida e permanência** do estudante. A própria Lei nº 14.914/2024 (PNAES) trata a alimentação como ação de permanência estudantil.
