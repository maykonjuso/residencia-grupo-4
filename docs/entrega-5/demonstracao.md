# Demonstração multimodal

Esta página reúne as evidências práticas do funcionamento de **pelo menos duas modalidades** integradas ao sistema multiagente do RUmo, mostrando como informações extraídas de **PDF + Imagem** e de **PDF efêmero + Texto** se transformam em respostas verificáveis e seguras.

---

## 1. Fluxo 1 — Texto + PDF institucional + Imagem (ícones de alergênicos do RU Gama)

O primeiro fluxo multimodal em produção combina **leitura tabular de PDF** (`coleta/cardapio.py`) e **classificação visual dos 10 ícones de alergênicos da ANVISA** (`alergenos.py`) para responder a consultas em linguagem natural sobre restrições alimentares e montagem de prato.

### Como a informação multimodal é utilizada

1. **PDF + Imagem → JSON estruturado:** ao processar o PDF oficial do cardápio semanal do RU Gama, o sistema recorta os ícones de referência do rodapé da página, segmenta os ícones das células em imagens `24×24 px` (`300 dpi`) e vincula cada alergênico identificado à opção exata de prato (`[Alergênicos: ...]`), estruturando o resultado no arquivo `cardapio_semanal.json` (`F56`).
2. **Consulta em Texto → Resposta com rastreabilidade:** quando o estudante pergunta sobre opções veganas, alergênicos específicos ou montagem de prato, o `AgenteRU` aciona `cardapio_do_dia` ou `montar_prato`, filtrando opções incompatíveis sem inventar ingredientes nem calorias.

```bash
cd rag
RUMO_BUSCA=bm25 RUMO_USAR_D1=0 ../.venv/bin/python -m rumo_rag perguntar \
  "Quais pratos do almoço de quarta-feira têm leite ou lactose?" \
  --agentes --trace --backend extrativo
```

Saída verificada do protótipo (detalhada no Caso 7 da [Entrega 4](../entrega-4/demonstracao.md#caso-7-consulta-composta-com-cardapio-semanal-estruturado-alergenicos-e-fluxo)):

```text
--- Parte 1 · Agente RU ---
- Cardápio do RU Gama (FCTE) — Almoço de quarta-feira, 18/11/2026: [1]
- Prato principal (ovolacto): Risoto de ervilha com queijo [Alergênicos: Leite e derivados, Trigo/Glúten] [1]
Fonte: [1] F56 · Cardápio semanal do RU Gama (16/11 a 22/11/2026) · p. 2
```

> A suíte [`test_alergenos.py`](https://github.com/maykonjuso/residencia-grupo-4/blob/main/rag/testes/test_alergenos.py) confere opção por opção contra a imagem original das páginas dos cardápios da base (`0` erros de associação nas 306 opções comparáveis após a ligação por posição dentro da célula).

---

## 2. Fluxo 2 — Texto + PDF pessoal efêmero (comprovante sintético `#59`)

O segundo fluxo multimodal demonstra o pipeline de privacidade para documentos acadêmicos (**#59 · Minha Semana**), executado integralmente em memória e verificado por suíte automatizada (`rag/testes/test_privacidade_documentos.py`).

### Etapa A — Descoberta da política antes do seletor (`GET /privacidade/documento`)

Antes de exibir o seletor de arquivo ao estudante, a interface consulta o contrato oficial:

```bash
curl -s http://localhost:8002/privacidade/documento
```

```json
{
  "versao": "1.0",
  "epico": "#59",
  "aviso_antes_upload": "Antes de selecionar o arquivo: envie preferencialmente o Comprovante ou Atestado de Matrícula do SIGAA...",
  "campos_permitidos": ["codigo", "turma", "horario", "sala"],
  "documentos_aceitos": ["comprovante_solicitacao_matricula", "comprovante_matricula", "atestado_matricula"],
  "documentos_recusados": ["historico_escolar"],
  "processamento_preferencial": "navegador",
  "fallback_servidor": "memoria_efemera_sem_disco",
  "armazenamento_servidor": false,
  "armazenamento_perfil": "navegador_localStorage",
  "envio_llm_externo": false,
  "tamanho_maximo_bytes": 5242880
}
```

### Etapa B — Extração em RAM com descarte de PII (layout real SIGAA)

Quando um PDF reproduzindo o layout oficial de **Comprovante de Solicitação de Matrícula** do SIGAA (`TURMAS SELECIONADAS` com linhas `INDEFERIDA`, `AGUARDANDO PROCESSAMENTO`, `DEFERIDA` e grade `Horários Seg..Sáb`, preenchido nos testes apenas com nome `ESTUDANTE FICTICIO DA SILVA` e matrícula `99/9999999`) passa por `privacidade.processar_comprovante_em_memoria(pdf_bytes)`:

- **Em disco / banco:** nenhum arquivo é criado (`NamedTemporaryFile` e `mkstemp` não são chamados; diretório temporário permanece vazio).
- **Filtro e compactação SIGAA:** solicitações indeferidas ou aguardando processamento são descartadas, mantendo apenas turmas `DEFERIDA` cruzadas com a grade semanal (`FGA0160` às `12:00-12:55` e `12:55-13:50` em Seg/Qua vira `24M5 24T1`).
- **Saída devolvida para armazenamento local no navegador:**

```json
{
  "sucesso": true,
  "recusado": false,
  "tipo_documento": "comprovante_matricula",
  "disciplinas": [
    {"codigo": "FGA0210", "turma": "01", "horario": "35T45", "sala": "FCTE - S4"},
    {"codigo": "FGA0160", "turma": "01", "horario": "24M5 24T1", "sala": "FCTE - I9"}
  ],
  "campos_mantidos": ["codigo", "turma", "horario", "sala"],
  "persistido_em_servidor": false,
  "enviado_llm_externo": false
}
```

Se o mesmo pipeline receber um **Histórico Escolar** com menções (`SS`, `II`, `IRA`) e sem grade de horários, retorna `recusado: true` com `motivo: "historico_escolar_nao_suportado"` e instrução para enviar o Atestado/Comprovante de Matrícula.

### Etapa C — Consulta textual à agenda com sanitização e bloqueio de OpenRouter

Ao enviar uma pergunta em texto acompanhada do perfil armazenado no navegador (mesmo que um cliente tente injetar `cpf`, `nome` ou `notas` no payload):

```bash
POST /perguntar
{
  "pergunta": "Quais minhas aulas de segunda-feira?",
  "contexto": {
    "campus": "gama",
    "perfil": {
      "nome": "Estudante Ficticio",
      "cpf": "123.456.789-00",
      "disciplinas": [
        {"codigo": "FGA0160", "turma": "01", "horario": "24M5 24T1", "sala": "FCTE - I9"}
      ]
    }
  }
}
```

1. `api.py` e `privacidade.sanitizar_perfil_contexto()` removem `nome`, `cpf` e qualquer chave não listada nos 4 campos antes que o dado chegue ao `Orquestrador`.
2. `minha_agenda` decodifica `24M5 24T1`, mescla faixas contíguas entre turnos (`12:00-12:55` + `12:55-13:50` → `12:00-13:50` na `segunda-feira`) e resolve o nome oficial da disciplina localmente via `grafo_curricular`.
3. Mesmo que o ambiente esteja com `RUMO_LLM_BACKEND=openai` (OpenRouter), `redigir_com_ferramenta()` bloqueia qualquer envio ao LLM externo e responde diretamente:

```text
Suas aulas em segunda-feira [1]:
- 12:00-13:50 · Métodos Numéricos para Engenharia (FGA0160 · Turma 01) — Sala FCTE - I9 [1]
```

---

## 3. Verificação automatizada e privacidade de repositório

```bash
cd rag
../.venv/bin/python -m pytest testes/test_privacidade_documentos.py testes/test_alergenos.py -v
```

!!! info "Calibragem em exemplar real sem exposição no Git"
    O extrator efêmero (`privacidade.py`) foi calibrado contra o layout real de **Comprovante de Solicitação de Matrícula** do SIGAA/UnB exclusivamente em memória durante o desenvolvimento. Em conformidade com a RN-05 e a LGPD, **nenhum documento real de estudante é salvo ou versionado no repositório**: a suíte automatizada verifica o mesmo layout usando um PDF sintético com dados fictícios.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 25/11/2026 | 1.0 | Registro dos dois fluxos multimodais demonstráveis (RU PDF+Imagem e Comprovante PDF sintético+Texto com proteção LGPD) | Grupo 04 |
