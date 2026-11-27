# Privacidade e documentos pessoais (LGPD · #59)

Para habilitar a jornada **"Minha Semana"** (Épico `#59`), o estudante precisa informar suas disciplinas matriculadas para consultar horários e salas de aula sem redigitar grade por grade. Documentos acadêmicos do SIGAA carregam **dados pessoais e sensíveis** — nome completo, número de registro acadêmico, CPF, notas, menções, IRA e histórico de reprovações — enquanto o RUmo precisa exclusivamente de **quatro campos operacionais**.

Esta página formaliza a **decisão arquitetural e regulatória bloqueante**: nenhum fluxo de upload de documento pessoal entra em produção sem cumprir integralmente os controles abaixo, em coerência com `RNF02`, `RNF06` e a regra de negócio [`RN-05`](../entrega-1/regras-de-negocio.md) (e alinhado à postura de privacidade adotada pelo grupo parceiro no app de coleta).

---

## 1. Postura obrigatória adotada

1. **Processar no navegador sempre que possível:** o módulo de entrada do front-end integrador ([Grupo 09 / FcteMapping](../visao/escopo-grupos.md)) deve ler o PDF localmente no dispositivo do estudante antes de qualquer chamada à API.
2. **Quando houver processamento no servidor: extrair, usar, descartar.** Em fallback de servidor, o PDF trafega apenas em `io.BytesIO` na memória RAM, com limite rígido de `5 MB` (`MAX_BYTES_PDF`), **sem uso de arquivos temporários em disco (`tempfile`) e sem gravação em banco de dados**.
3. **Guardar apenas os quatro campos:** somente **`codigo`**, **`turma`**, **`horario`** e **`sala`** podem sobreviver ao extrator e ao sanitizador (`CAMPOS_PERMITIDOS_DOCUMENTO`). Nome, CPF, matrícula, notas, menções, IRA e reprovações são descartados na origem.
4. **Avisar antes do seletor de arquivo:** toda interface de seleção de arquivo deve exibir o aviso em linguagem simples **antes** de o estudante abrir o seletor do sistema operacional.
5. **Nenhum trecho do documento vai para LLM externo:** serviços externos como **OpenRouter** (`backend="openai"` / `"openrouter"`) ficam tecnicamente bloqueados para qualquer ferramenta que receba o perfil derivado (`minha_agenda`). A resposta é gerada deterministicamente em código Python (ou, no máximo, por modelo local sob execução controlada).
6. **O perfil derivado fica no navegador:** nenhuma tabela de usuários ou sessão persistente é mantida no backend do RUmo (`armazenamento_servidor = False`). O portal guarda os 4 campos apenas no `localStorage` do estudante e envia somente o mínimo sanitizado em `contexto.perfil` quando o usuário consulta sua agenda.

---

## 2. Decisão de escopo sobre os tipos de documento

| Documento do SIGAA | Decisão | Justificativa técnica e de privacidade |
|---|---|---|
| **Comprovante / Atestado / Solicitação de Matrícula** | **Aceito** | Reúne a tabela `TURMAS SELECIONADAS` (filtrada para manter somente situações `DEFERIDA`/`MATRICULADO`) e a grade `Horários Seg..Sáb`, permitindo derivar exatamente `codigo`, `turma`, código de `horario` SIGAA e `sala` sem expor histórico de notas ou reprovações |
| **Histórico Escolar** | **Recusado com orientação explícita** | Concentra todas as notas, menções, IRA e reprovações do curso inteiro e **não informa horário nem sala** das turmas atuais — risco máximo com utilidade zero para a agenda |

<p class="legenda">Tabela 1. Política de aceitação de documentos do SIGAA na entrada da issue #59.</p>

!!! note "Calibragem no layout real do SIGAA e integração de interface"
    O repositório do RUmo (Grupo 04) disponibiliza atualmente a **API HTTP** e esta **GitPage documental**, sem aplicação front-end própria de upload (esta GitPage não hospeda envio de PDFs pessoais). O extrator efêmero (`privacidade.py`) já foi calibrado sobre o layout oficial do **Comprovante de Solicitação de Matrícula do SIGAA/UnB** — recompondo títulos em small-caps extraídos pelo `pypdf`, filtrando apenas turmas `DEFERIDA`/`MATRICULADO` na tabela `TURMAS SELECIONADAS`, cruzando com a grade `Horários Seg..Sáb` e mesclando faixas contíguas entre turnos (ex.: `24M5 24T1` → `12:00-13:50`). Nenhum documento real é versionado no repositório: a suíte `pytest` reproduz o mesmo layout com dados 100% fictícios.

---

## 3. Fluxo de dados e barreiras técnicas

A **Figura 1** ilustra o caminho preferencial (100% no navegador) e o caminho alternativo (efêmero em memória no servidor), destacando onde os dados sensíveis são descartados e onde a chamada a LLM externo é interceptada.

```mermaid
sequenceDiagram
    autonumber
    actor E as Estudante
    participant F as Front-end (Portal / FcteMapping)
    participant API as API RUmo (api.py / privacidade.py)
    participant Ag as Agente Fluxo (minha_agenda)
    participant Ext as LLM Externo (OpenRouter)

    F->>API: GET /privacidade/documento
    API-->>F: Aviso pré-upload + schema permitido (4 campos)
    E->>F: Lê aviso ANTES do seletor e escolhe PDF do Atestado
    alt Caminho preferencial (Navegador)
        Note over F: Extrai em JS no navegador, descarta PDF e PII<br/>Grava só [codigo, turma, horario, sala] em localStorage
    else Fallback no servidor (stateless)
        F->>API: Envia bytes (somente RAM, máx. 5 MB)
        Note over API: io.BytesIO sem disco/temp;<br/>recusa Histórico Escolar;<br/>sanitiza para 4 campos e descarta buffer
        API-->>F: Retorna apenas [{codigo, turma, horario, sala}]
    end
    E->>F: "Quais minhas aulas hoje?"
    F->>API: POST /perguntar (contexto.perfil sanitizado)
    API->>Ag: sanitizar_perfil_contexto() -> minha_agenda()
    Ag--xExt: Bloqueado em redigir_com_ferramenta() se backend for openai/openrouter
    Ag-->>E: Resposta determinística com horário decodificado e sala [1]
```

<p class="legenda">Figura 1. Fluxo de privacidade ponta a ponta para documentos pessoais na issue #59.</p>

---

## 4. Aviso obrigatório antes do seletor de arquivo

Qualquer interface que integre esta funcionalidade deve buscar ou espelhar o campo `aviso_antes_upload` publicado por `GET /privacidade/documento`, exibindo-o visivelmente **acima do botão de seleção de arquivo**:

> *"Antes de selecionar o arquivo: envie preferencialmente o Comprovante ou Atestado de Matrícula do SIGAA (e não o Histórico Escolar). Sempre que possível, a leitura ocorre no seu próprio navegador, sem enviar o PDF ao servidor. Caso o processamento ocorra no servidor, o arquivo é lido apenas em memória e descartado imediatamente — nada é gravado em disco ou banco. Extraímos somente quatro campos (código da disciplina, turma, horário e sala) e descartamos nome, CPF, registro acadêmico, notas e reprovações. Nenhum trecho do documento é enviado a LLM externo (como OpenRouter), e o perfil derivado fica salvo apenas no navegador."*

### Contrato exposto em `GET /privacidade/documento`

- **`campos_permitidos`:** `["codigo", "turma", "horario", "sala"]`
- **`documentos_aceitos`:** `["comprovante_solicitacao_matricula", "comprovante_matricula", "atestado_matricula"]`
- **`documentos_recusados`:** `["historico_escolar"]`
- **`processamento_preferencial`:** `"navegador"`
- **`fallback_servidor`:** `"memoria_efemera_sem_disco"`
- **`armazenamento_servidor`:** `false`
- **`armazenamento_perfil`:** `"navegador_localStorage"`
- **`envio_llm_externo`:** `false`
- **`tamanho_maximo_bytes`:** `5242880` (`5 MB`)

---

## 5. Rastreabilidade dos critérios de aceite

A **Tabela 2** vincula cada critério de aceite da issue `#59` ao componente de código que o garante e ao teste automático correspondente em `rag/testes/test_privacidade_documentos.py`.

| Critério de aceite | Garantia no código | Arquivo / Símbolo | Verificação automatizada |
|---|---|---|---|
| **Nenhum arquivo permanece em disco ou banco após o uso** | Leitura exclusivamente via `io.BytesIO` com limpeza em `finally`; nenhum uso de `tempfile`, `open(..., "w")` ou banco | `privacidade.extrair_texto_pdf_em_memoria`, `privacidade.processar_comprovante_em_memoria` | `test_processar_comprovante_em_memoria_nao_grava_em_disco_nem_expoe_pii` (bloqueia `tempfile` por mock e audita `tmp_path` vazio) |
| **Persistência e tráfego restritos a código, turma, horário e sala** | Allowlist estrita de saída + detector de PII (CPF, matrícula UnB `XX/XXXXXXX`, e-mail e rótulos sensíveis) na entrada do extrator e em `POST /perguntar` | `privacidade.sanitizar_registro_disciplina`, `privacidade.sanitizar_perfil_contexto`, `api.perguntar` | `test_sanitizacao_estrita_descarta_pii_e_mantem_quatro_campos`, `test_api_expoe_politica_e_sanitiza_perfil_em_perguntar` |
| **Aviso aparece antes do seletor de arquivo** | Texto oficial e flags de postura publicados por rota dedicada da API antes de qualquer seleção de arquivo | `privacidade.AVISO_PRIVACIDADE_UPLOAD`, `GET /privacidade/documento` | `test_api_expoe_politica_e_sanitiza_perfil_em_perguntar` |
| **Nenhuma chamada de LLM externo recebe trecho do documento** | Barreira explícita que impede `redigir_com_ferramenta()` de chamar `geracao.gerar_com_instrucoes()` quando `ferramenta == "minha_agenda"` e `backend` é `openai` / `openrouter` | `ferramentas.FERRAMENTAS_DADOS_PESSOAIS`, `ferramentas.BACKENDS_LLM_EXTERNOS`, `ferramentas.redigir_com_ferramenta` | `test_dados_pessoais_nunca_vao_para_llm_externo` |
| **Decisão documentada na GitPage** | Especificação formal na Entrega 5 vinculada às regras `RN-04` e `RN-05` e ao risco `R08` | `docs/entrega-5/privacidade-documentos.md`, `docs/entrega-1/regras-de-negocio.md`, `docs/entrega-1/riscos.md` | Build estrito `mkdocs build --strict` sem alertas |

<p class="legenda">Tabela 2. Vínculo entre critérios de aceite, código-fonte, testes automáticos e documentação.</p>

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 25/11/2026 | 1.0 | Formalização da política LGPD de documentos pessoais (#59), schema de 4 campos e garantias verificáveis | Grupo 04 |
