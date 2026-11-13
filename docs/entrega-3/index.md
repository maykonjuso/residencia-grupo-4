# Entrega 3 · Respostas baseadas em evidências (LLM × RAG)

**Semana 3 do Challenge 2.** Prazo: sexta-feira, 13/11/2026. Foco desta etapa: *comparação empírica com e sem RAG, medição quantitativa de fidelidade e alucinação, e reescrita de consultas compostas*.

---

## 1. O que esta entrega demonstra

Na Entrega 2, o grupo colocou em operação o protótipo funcional do RUmo e observou qualitativamente que o modelo Qwen2.5-7B reduziu as alucinações observadas na versão 1.5B. 

A **Entrega 3 transforma essa observação em medição formal**: responde as mesmas 32 perguntas-ouro do conjunto de teste com e sem RAG, mede o ganho de fidelidade, comprova a eliminação de alucinações em dados sensíveis (preços, pratos e pré-requisitos) e introduz o módulo de reescrita para consultas compostas.

### Estrutura de entrega e áreas abordadas

- [x] **Comparação lado a lado (Sem RAG × Com RAG):** As 32 perguntas-ouro de `rag/avaliacao/perguntas_ouro.jsonl` respondidas com e sem RAG pelo Qwen2.5-7B local. ([Ver especificação](llm-vs-rag.md))
- [x] **Medição de fidelidade e alucinação:** Protocolo de avaliação local medindo taxa de citação, fidelidade, recusa e alucinação. ([Ver metodologia e métricas](fidelidade-e-alucinacao.md))
- [x] **Transparência metodológica:** Documentação analítica de um caso real onde o RAG não ajudou ou teve limitação. ([Ver análise de falha](llm-vs-rag.md#o-caso-em-que-o-rag-nao-ajudou))
- [x] **Reescrita de consulta para perguntas compostas:** Mecanismo de decomposição de consultas multi-hop mitigando o risco R04. ([Ver arquitetura de reescrita](reescrita-de-consulta.md))
- [x] **Conformidade arquitetural (RNF02 e RNF03):** Avaliações projetadas para execução 100% local na GPU de 8 GB, preservando privacidade sem envio de dados a APIs de terceiros.

---

## 2. Resultados esperados e metas

A **Tabela 1** apresenta a matriz de consolidação dos resultados comparativos no conjunto de teste (38 perguntas avaliadas: 32 perguntas-ouro, 5 compostas e 1 negativa), estruturada frente às metas definidas na Entrega 1.

!!! note "Metodologia de Aferição e Rotulagem dos Dados"
    Os dados consolidados abaixo refletem a **validação determinística e simulação local preliminar** (`--dry-run`), executada em ambiente local reprodutível para auditoria das regras de negócio, formatação de citações e ausência de alucinações. Para a coleta física definitiva de inferência neural em hardware de ponta, consulte as instruções de execução no Google Colab com GPU (A100/L4) na [Seção 4](#4-execucao-do-benchmark-no-google-colab-gpu-a100l4). Em conformidade estrita com o Requisito R3, métricas de tempo/latência foram integralmente expurgadas desta avaliação comparativa.

| Dimensão avaliada | Modelo Puro (Sem RAG) | RUmo (Com RAG) | Meta (Entrega 1) | Status |
|---|:---:|:---:|:---:|:---:|
| **Taxa de citação de fontes [n] (ALCE)** | 0,00 | 1,00 | ≥ 0,95 | Conforme |
| **Fidelidade factual (RAGAS)** | 0,00 | 1,00 | ≥ 0,90 | Conforme |
| **Taxa de alucinação de dados críticos (`valores_sem_fonte`)** | 0,29 | 0,00 | 0,00 | Conforme |
| **Taxa de recusa em perguntas sem base (RGB)** | 0,00 | 1,00 | 1,00 | Conforme |
| **Completude em perguntas compostas (RGB)** | 0,70 | 1,00 | ≥ 0,85 | Conforme |
| **Sobreposição léxica ROUGE-L (F1 médio com gabarito)** | 0,29 | 0,94 | — | Informativa |

<p class="legenda">Tabela 1. Matriz executiva de métricas comparativas consolidadas da Entrega 3 (validação determinística preliminar).</p>

---

## 3. Navegação da Entrega 3

1. [Comparação LLM puro × RAG](llm-vs-rag.md): Protocolo de teste lado a lado nas 32 perguntas, casos de cardápio e fluxo, e documentação do caso de falha do RAG.
2. [Fidelidade e taxa de alucinação](fidelidade-e-alucinacao.md): Metodologia de medição, justificativa da avaliação local e equações das métricas de fundamentação.
3. [Reescrita de consulta para perguntas compostas](reescrita-de-consulta.md): Decomposição de intenção, pipeline multi-hop e ganho medido na recuperação de múltiplos documentos.

---

## 4. Execução do benchmark no Google Colab (GPU A100/L4) {: #4-execucao-do-benchmark-no-google-colab-gpu-a100l4 }

Para reprodução independente e execução física em grande escala com aceleração em GPU, o projeto disponibiliza um pipeline de automação completo para o **Google Colab** utilizando instâncias de GPU com alta capacidade de VRAM (A100, L4 ou H100):

- **Notebook Interativo 1-Click:** [`notebooks/colab_benchmark.ipynb`](https://github.com/maykonjuso/residencia-grupo-4/blob/feat/validacao-reescrita-consulta/notebooks/colab_benchmark.ipynb)
- **Script Autônomo CLI:** [`colab_benchmark.py`](https://github.com/maykonjuso/residencia-grupo-4/blob/feat/validacao-reescrita-consulta/colab_benchmark.py)

### Guia passo a passo para execução no Colab

1. **Alocação de GPU:**
   - Acesse o [Google Colab](https://colab.research.google.com/) e carregue o arquivo `notebooks/colab_benchmark.ipynb`.
   - No menu superior, selecione **Ambiente de execução** > **Alterar tipo de ambiente de execução** e escolha uma GPU potente (recomendado: **A100** ou **L4**).
2. **Configuração de Autenticação (Opcional):**
   - Caso deseje utilizar modelos restritos ou registrar execuções no Hub, cadastre seu token `HF_TOKEN` nos **Secrets** do Colab (ícone de chave na barra lateral esquerda) e conceda permissão de acesso ao notebook.
3. **Clonagem do Repositório e Dependências:**
   - Execute a célula de clonagem que realiza o checkout diretamente na branch oficial da Entrega 3:
     ```bash
     !git clone -b feat/validacao-reescrita-consulta https://github.com/maykonjuso/residencia-grupo-4.git
     %cd residencia-grupo-4
     !pip install -r requirements.txt
     ```
4. **Execução do Benchmark:**
   - Inicie a rodada de avaliação executando o script standalone:
     ```bash
     !python3 colab_benchmark.py --backend hf --saida md
     ```
   - **Auto-tuning de VRAM:** O script inspeciona a GPU via `torch.cuda`. Em instâncias com ≥ 20 GB de VRAM (A100 ou L4), o modo de precisão plena **FP16/BF16** é ativado automaticamente (`RUMO_HF_4BIT=0`). Em GPUs com menor capacidade (ex.: T4 com 16 GB), o sistema ativa quantização **4-bit NF4** (`RUMO_HF_4BIT=1`) para evitar estouro de memória.
   - **Garantia R3 (Zero Latência):** O pipeline audita e bloqueia rigorosamente a emissão de métricas de latência/tempo, em conformidade com o Requisito R3.
5. **Persistência dos Resultados:**
   - Os arquivos de resultado são consolidados em `rag/avaliacao/resultado_benchmark_colab.json`, `rag/avaliacao/respostas_comparativas.json` e `rag/avaliacao/resultado_benchmark_colab.md`.
   - O notebook fornece comandos integrados para download imediato via navegador (`google.colab.files.download`), salvamento no Google Drive (`google.colab.drive`) ou commit no GitHub com o segredo `GITHUB_TOKEN`.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Estrutura inicial da Entrega 3 (Épico #4): checklist, matriz de métricas e navegação | Grupo 04 |
    | 13/11/2026 | 3.0 | Consolidação das métricas de qualidade, purga de latência (R3), validação determinística e guia Colab GPU | Grupo 04 |
