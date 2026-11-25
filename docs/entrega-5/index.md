# Entrega 5 · Assistente de IA Multimodal

**Semana 5 do Challenge 2.** Foco desta etapa, segundo o enunciado: *integração de diferentes modalidades de entrada no sistema (texto, PDF e imagem), documentação clara de limitações e casos de falha com estratégias de mitigação, e demonstração funcional de ponta a ponta*, com envio para a pasta da equipe no Teams (canal **Segundo Desafio**) até **segunda-feira, às 8h00**.

---

## 1. Escopo e checklist do que foi pedido

A Entrega 5 consolida a dimensão multimodal do **RUmo** sobre a base multiagente da [Entrega 4](../entrega-4/index.md) e estabelece a **postura obrigatória de privacidade (LGPD)** para o tratamento de documentos pessoais do estudante no âmbito do Épico `#59` (*"Minha Semana"*).

### Modalidades suportadas

- [x] **Texto + documentos estruturados:** linguagem natural para consultas ao RU e ao fluxo acadêmico, integradas ao índice híbrido e ao grafo curricular (`grafo_curricular.json`). ([Ver modalidades](modalidades.md))
- [x] **PDF + Imagem incorporada (base oficial):** leitura programática de tabelas de cardápios semanais do RU Gama (`coleta/cardapio.py`) combinada à extração visual pixel a pixel dos ícones de alergênicos no rodapé e corpo da tabela (`alergenos.py`), além das transcrições curadas de fluxogramas em imagem (`F16`, `F23`). ([Ver modalidades](modalidades.md))
- [x] **PDF pessoal do estudante (`#59` — extrator calibrado no SIGAA; pendente de integração de UI):** arquitetura de privacidade, parser efêmero calibrado para o layout oficial de **Comprovante de Solicitação de Matrícula** do SIGAA/UnB (filtrando apenas turmas `DEFERIDA`/`MATRICULADO`), sanitizador de 4 campos (`codigo`, `turma`, `horario`, `sala`), decodificador contínuo de horários e bloqueio de LLM externo implementados em `privacidade.py`, `ferramentas.py` e `api.py`. ([Ver privacidade e LGPD](privacidade-documentos.md))

### Documentação e governança

- [x] **Modalidades suportadas:** matriz completa de entradas, mecanismos de extração, agentes de destino e garantias por modalidade. ([Ver modalidades](modalidades.md))
- [x] **Decisão bloqueante de privacidade (LGPD / `#59`):** especificação auditável do aviso pré-upload, descarte em memória, descarte de PII e bloqueio de envio a LLMs externos (OpenRouter). ([Ver privacidade e LGPD](privacidade-documentos.md))
- [x] **Limitações conhecidas, casos de falha e mitigações:** inventário técnico por modalidade e protocolo de degradação/recusa segura. ([Ver limitações e falhas](limitacoes-e-falhas.md))
- [x] **Demonstração multimodal:** fluxos reproduzíveis cobrindo Texto + PDF/Imagem institucional e Texto + PDF sintético efêmero. ([Ver demonstração](demonstracao.md))

---

## 2. Resumo técnico das modalidades e garantias

| Dimensão | Implementação no RUmo |
|---|---|
| **Modalidades integradas** | **Texto** (perguntas e base normativa/curricular), **PDF** (cardápios/normas oficiais + comprovante pessoal efêmero em RAM) e **Imagem** (ícones de alergênicos no PDF oficial + fluxogramas transcritos `F16`/`F23`) |
| **Leitura visual de alergênicos (`#55`)** | Comparação pixel a pixel (`24×24 px`, `300 dpi`) dos 10 ícones da ANVISA contra a legenda da própria página; `0` erros em 306 opções comparáveis, etiqueta *"a conferir na distribuição"* em caso ambíguo |
| **Privacidade de documento pessoal (`#59`)** | Processamento preferencial no navegador; fallback em RAM (`io.BytesIO`, máx. `5 MB`) sem disco nem banco; retenção estrita de `4` campos (`codigo`, `turma`, `horario`, `sala`) |
| **Bloqueio de LLM externo (`RNF02` / `LGPD`)** | Ferramentas com dados do perfil (`minha_agenda`) ficam impedidas de acionar `openai`/`openrouter` em `redigir_com_ferramenta()`, respondendo deterministicamente |
| **Contrato de transparência (`API`)** | `GET /privacidade/documento` expõe o texto oficial de aviso antes do seletor de arquivo e o schema permitido; `POST /perguntar` aplica allowlist automática em `contexto.perfil` |
| **Limitação pendente** | Ausência de front-end próprio no repositório do Grupo 04 (consumo previsto no portal do [Grupo 09](../visao/escopo-grupos.md)) e dependência de camada de texto em PDFs do SIGAA |

<p class="legenda">Tabela 1. Síntese técnica e de conformidade da Entrega 5.</p>

---

## 3. Navegação da Entrega 5

1. [Modalidades suportadas](modalidades.md): Como Texto, PDF e Imagem (ícones de alergênicos e fluxogramas) entram no pipeline multiagente sem misturar fontes oficiais e dados locais.
2. [Privacidade e documentos pessoais (LGPD)](privacidade-documentos.md): Política bloqueante da issue `#59`, os quatro campos permitidos, aviso pré-upload, bloqueio de OpenRouter e critérios de aceite verificáveis.
3. [Limitações e casos de falha](limitacoes-e-falhas.md): Limitações conhecidas de cada modalidade, matriz de falhas previstas e estratégias de mitigação.
4. [Demonstração multimodal](demonstracao.md): Evidências reproduzíveis de Texto + PDF/Imagem oficial (alergênicos no cardápio) e de processamento efêmero de PDF sintético em memória.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 25/11/2026 | 1.0 | Estrutura inicial da Entrega 5 (Multimodalidade e política bloqueante de privacidade LGPD de #59) | Grupo 04 |
