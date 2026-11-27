# Limitações conhecidas, casos de falha e mitigações

Esta página registra as **limitações técnicas conhecidas** das modalidades integradas ao RUmo e consolida os **casos de falha identificados** junto às respectivas estratégias de mitigação, conforme exigido pelo entregável de Multimodalidade da Semana 5.

---

## 1. Limitações conhecidas por modalidade

### Texto e consultas estruturadas
- **Vocabulário não literal no BM25/híbrido:** termos específicos fora do texto oficial (ex.: perguntar *"doença celíaca"* quando a página `F37` usa *"dietas especializadas"*) dependem da formulação da consulta, conforme medido na Entrega 2/3.
- **Lacunas nas grades sem códigos SIGAA:** as fontes disponíveis para Engenharia de Energia (`F23`) e Engenharia Automotiva (`F19`) não listam pré-requisitos completos ou códigos SIGAA em todas as entradas; o sistema recusa a inferência de dependências nesses casos em vez de estimar.
- **Setas tracejadas no fluxograma:** ligações tracejadas em `F16` representam ambiguidade na fonte visual original entre pré-requisito e correquisito e permanecem sinalizadas com *"confirme no SIGAA"*.

### PDF e Imagem (base institucional — RU e fluxogramas)
- **Ausência de tabela nutricional e calorias:** o Restaurante Universitário não publica Fichas Técnicas de Preparação no site (confirmado por resposta formal da DRU em 23/11/2026); portanto, o sistema não estima calorias nem macronutrientes.
- **Peixe e frutos do mar sem ícone na legenda do RU Gama:** a legenda do cardápio oficial do Gama contempla 10 alergênicos, mas não inclui ícone de peixe/frutos do mar (`Filé de peixe ao molho de ervas` aparece sem ícone no PDF).
- **Ausência de garantia de isenção cruzada:** segundo a própria DRU, os ícones indicam presença intencional de ingredientes, mas insumos industrializados e preparo compartilhado impedem garantir isenção absoluta de traços.
- **Fluxogramas em imagem sem leitor automático online:** `F16` e `F23` usam transcrição auditada versionada em vez de OCR/VLM dinâmico em produção, para evitar erro estrutural silencioso em setas finas e rótulos sobrepostos.

### PDF pessoal do estudante (Épico `#59`)
- **PDFs escaneados como imagem:** o extrator efêmero (`privacidade.py`) processa apenas PDFs com camada de texto selecionável (`pypdf` / `pdfplumber`). Documentos fotografados ou escaneados sem texto embutido são recusados para evitar OCR pesado no servidor serverless.
- **Sensibilidade a variações futuras de layout do SIGAA:** o extrator foi calibrado sobre o **Comprovante de Solicitação de Matrícula** atual da UnB (duas seções: `TURMAS SELECIONADAS` e grade semanal `Horários Seg..Sáb`) e também suporta o formato inline simples; mudanças estruturais futuras no PDF gerado pelo SIGAA podem exigir ajuste de regex ou parser dedicado.
- **Ausência de front-end próprio no repositório do Grupo 04:** a tela com aviso pré-upload e seletor local de arquivo será executada no portal integrador do [Grupo 09](../visao/escopo-grupos.md) ou em módulo estático acoplável (`rag/web/`), mantendo a GitPage livre de upload pessoal.

---

## 2. Casos de falha identificados e estratégias de mitigação

A **Tabela 1** lista os cenários de falha mapeados nas modalidades ativas, como o sistema reage e qual mecanismo garante recuperação segura ou recusa transparente.

| ID | Caso de falha | Causa provável | Comportamento do sistema | Estratégia de mitigação |
|---|---|---|---|---|
| **F01** | **Envio de Histórico Escolar no lugar do Atestado** | Estudante confunde o documento no SIGAA e envia histórico cheio de notas/IRA e sem horário | `detectar_tipo_documento` identifica histórico sem horários SIGAA e recusa (`historico_escolar_nao_suportado`) | Exibe `MENSAGEM_RECUSA_HISTORICO` orientando a baixar o Comprovante/Atestado de Matrícula; nada é salvo |
| **F02** | **PDF escaneado (só imagem), vazio ou corrompido** | Usuário envia captura de tela convertida em PDF, arquivo truncado ou formato diferente (`.docx`/`.jpg`) | `validar_pdf_em_memoria` rejeita cabeçalho inválido ou arquivo vazio/`> 5 MB`; PDF sem texto cai em `sem_disciplinas_validas` | Validação prévia do header `%PDF-` e limite de `5 MB` em RAM; mensagem orientando enviar PDF original emitido pelo SIGAA |
| **F03** | **Tentativa de envio de PII em `contexto.perfil`** | Front-end ou chamador externo envia JSON contendo `nome`, `cpf`, `matricula`, `notas` ou CPF dentro de campo de texto | `sanitizar_perfil_contexto()` descarta chaves fora da allowlist e anula valores que casem padrões de CPF, matrícula (`XX/XXXXXXX`) ou e-mail | Sanitização defensiva na borda da API (`POST /perguntar`), dentro de `minha_agenda` e na seleção de chamada (`extrair_chamada_fluxo`) |
| **F04** | **Vazamento acidental para LLM externo em consultas pessoais** | Ambiente de nuvem (`RUMO_LLM_BACKEND=openai` via OpenRouter) ativo durante pergunta sobre a agenda pessoal | `redigir_com_ferramenta()` bloqueia a chamada quando a ferramenta pertence a `FERRAMENTAS_DADOS_PESSOAIS` e o backend é externo | Devolve a saída determinística da própria ferramenta com alerta explícito e zero chamada externa |
| **F05** | **Ícone de alergênico ambíguo ou alterado no PDF do RU** | Novo layout do cardápio semanal do RU Gama muda tamanho/posição do ícone ou funde vários símbolos com baixa separação | Em `alergenos.py`, se `distancia > 0,06` ou razão entre 2º e 1º melhor candidato `< 1,25`, o algoritmo não escolhe alergênico | Substitui por etiqueta `"a conferir na distribuição"`, registra aviso no JSON (`cardapio_semanal.json`) e instrui os prompts a manter o alerta |
| **F06** | **Mudança semanal ou falha de coleta do cardápio** | Site do RU indisponível no deploy ou semana fora da janela coberta pelo arquivo local | `carregar_semana_atual()` sinaliza indisponibilidade ou defasagem temporal da fonte | `AgenteRU` registra alerta no `trace`, não responde com cardápio vencido de outra semana e aplica recusa honesta (`RN-03`) |
| **F07** | **Erro ou indisponibilidade do LLM em pergunta mista (RU + Fluxo)** | Limite de cota no OpenRouter ou timeout de geração na rede | `_executar_com_fallback()` em `api.py` ou `Sintetizador` detecta falha em parte multiagente | Cai automaticamente para resposta extrativa determinística mantendo os trechos e citações válidos |
| **F08** | **Turmas indeferidas, em rematrícula aguardando ou repetidas no comprovante** | O comprovante do SIGAA lista todas as solicitações (`INDEFERIDA`, `AGUARDANDO PROCESSAMENTO`, `DEFERIDA`), às vezes com a mesma disciplina em duas turmas | `_extrair_turmas_selecionadas()` ignora solicitações não efetivadas e só cruza com a grade turmas `DEFERIDA`/`MATRICULADO` | Evita que sala indeferida ou turma pendente polua a agenda semanal do estudante |

<p class="legenda">Tabela 1. Casos de falha identificados nas modalidades do RUmo e estratégias de mitigação implementadas.</p>

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 25/11/2026 | 1.0 | Documentação das limitações conhecidas por modalidade, matriz de falhas e mitigações | Grupo 04 |
