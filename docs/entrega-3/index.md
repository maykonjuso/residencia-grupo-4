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

!!! note "Metodologia de Aferição e Dados Reais em GPU L4 (Google Colab)"
    Os resultados consolidados na Tabela 1 representam as medições empíricas físicas executadas em hardware de alta capacidade (**Google Colab - GPU NVIDIA L4 de 24 GB**, precisão total **FP16/BF16**, sem quantização de 4 bits). O pipeline utilizou o classificador leve `LiquidAI/d1-omni-600M` calibrado (limiar `0.3891`) para detecção em 2 estágios e o modelo gerador `Qwen/Qwen2.5-7B-Instruct` sobre as 38 perguntas do benchmark. Em cumprimento ao Requisito R3, todas as métricas de latência e tempo de execução foram integralmente expurgadas da avaliação.

| Dimensão avaliada | Modelo Puro (Sem RAG) | RUmo (Com RAG) | Meta (Entrega 1) | Status |
|---|:---:|:---:|:---:|:---:|
| **Taxa de citação de fontes [n] (ALCE)** | 0,00 | 0,92 | ≥ 0,95 | Ajustar (tolerância) |
| **Fidelidade factual (RAGAS)** | 0,00 | 0,97 | ≥ 0,90 | Conforme |
| **Taxa de alucinação de dados críticos (`valores_sem_fonte`)** | 0,26 | 0,00 | 0,00 | Conforme (100% livre) |
| **Taxa de recusa em perguntas sem base (RGB)** | 0,00 | 0,00 | 1,00 | Ajustar (D7) |
| **Completude em perguntas compostas (RGB)** | 1,00 | 0,90 | ≥ 0,85 | Conforme |
| **Sobreposição léxica ROUGE-L (F1 médio com gabarito)** | 0,24 | 0,42 | — | Informativa |

<p class="legenda">Tabela 1. Matriz executiva de métricas comparativas consolidadas da Entrega 3 (medidas em GPU NVIDIA L4 via Google Colab).</p>

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
