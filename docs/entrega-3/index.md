# Entrega 3 · Respostas baseadas em evidências (LLM × RAG)

**Semana 3 do Challenge 2.** Foco: *comparação empírica com e sem RAG, medição quantitativa de fidelidade e alucinação, e reescrita de consultas compostas*.

---

## 1. Escopo da entrega

A Entrega 2 colocou em operação o protótipo funcional do RUmo com o modelo Qwen2.5-7B. A **Entrega 3 formaliza essa validação**:

1. Submete as 32 perguntas-ouro aos regimes com e sem RAG;
2. Mede a fidelidade factual e a precisão de citações;
3. Elimina alucinações em dados sensíveis (preços, cardápios e pré-requisitos);
4. Decompõe consultas compostas em múltiplos eixos informacionais.

### Checklist de entregáveis

- [x] **Comparação lado a lado (Sem RAG × Com RAG):** 32 perguntas avaliadas com o Qwen2.5-7B local. ([Ver comparação](llm-vs-rag.md))
- [x] **Métricas de fidelidade e alucinação:** Protocolo local para taxas de citação, fidelidade, recusa e alucinação. ([Ver metodologia](fidelidade-e-alucinacao.md))
- [x] **Transparência metodológica:** Análise de falha em encadeamento transitivo onde o RAG não bastou. ([Ver caso de falha](llm-vs-rag.md#o-caso-em-que-o-rag-nao-ajudou))
- [x] **Reescrita de consultas compostas:** Decomposição multi-hop em dois estágios contra recuperação parcial (**R04**). ([Ver arquitetura](reescrita-de-consulta.md))
- [x] **Privacidade local (RNF02 e RNF03):** Execução sem tráfego de dados para APIs de terceiros.

---

## 2. Resultados consolidados

A **Tabela 1** resume o desempenho do sistema nas 38 perguntas de teste (32 ouro, 5 compostas e 1 negativa) frente às metas do projeto.

!!! note "Ambiente de execução em GPU NVIDIA L4 (Google Colab)"
    Medições físicas em GPU NVIDIA L4 (24 GB VRAM) com precisão plena **FP16/BF16**. O pipeline integra o classificador leve `LiquidAI/d1-omni-600M` calibrado (limiar `0.3891`) e o gerador `Qwen/Qwen2.5-7B-Instruct`. Em conformidade com o Requisito R3, o relatório exclui métricas temporais ou de latência.

| Dimensão avaliada | Pra que serve (Justificativa Prática) | Modelo Puro (Sem RAG) | RUmo (Com RAG) | Meta (Entrega 1) | Status |
|---|---|:---:|:---:|:---:|:---:|
| **Taxa de citação de fontes [n] (ALCE)** | **Auditabilidade:** Permite ao aluno auditar resoluções e editais diretamente no documento oficial. | 0,00 | 0,92 | ≥ 0,95 | Ajustar (tolerância) |
| **Fidelidade factual (RAGAS)** | **Integridade:** Garante que a resposta sintetize fielmente os trechos, sem extrapolações conceituais. | 0,00 | 0,97 | ≥ 0,90 | Conforme |
| **Taxa de alucinação numérica extrínseca (`valores_sem_fonte`)** | **Prevenção de danos materiais:** Evita invenção de tarifas (R$), datas de calendário e códigos de matéria. | 0,26 | 0,00 | 0,00 | Conforme (zero valores sem lastro) |
| **Taxa de recusa em perguntas sem base (RGB)** | **Honestidade intelectual (RF04):** Impede invenção de respostas fora de domínio (senhas de Wi-Fi, boatos). | 0,00 | 0,00 | 1,00 | Ajustar (D7) |
| **Completude em perguntas compostas (RGB)** | **Atendimento integral:** Garante que ambos os tópicos de perguntas multi-hop sejam respondidos. | 1,00 | 0,90 | ≥ 0,85 | Conforme |
| **Sobreposição léxica ROUGE-L (F1 médio com gabarito)** | **Alinhamento institucional:** Mede a proximidade vocabular com os gabaritos formais da FCTE. | 0,24 | 0,42 | — | Informativa |

<p class="legenda">Tabela 1. Matriz executiva de métricas comparativas consolidadas da Entrega 3 (medidas em GPU NVIDIA L4 via Google Colab). *Nota: A taxa de alucinação de 0,00 refere-se estritamente à ausência de números, moedas e códigos arbitrários; a fidelidade conceitual completa é dada pelo RAGAS (0,97) e pela análise qualitativa de recusa (D7). Ver [Fidelidade e Alucinação](fidelidade-e-alucinacao.md#tipologia-de-alucinacoes-e-transparencia-metodologica-analise-critica).*</p>

---

## 3. Navegação da Entrega 3

1. [Comparação LLM puro × RAG](llm-vs-rag.md): Protocolo de teste lado a lado nas 32 perguntas, casos de cardápio e fluxo, e documentação do caso de falha do RAG.
2. [Fidelidade e taxa de alucinação](fidelidade-e-alucinacao.md): Metodologia de medição, justificativa da avaliação local e equações das métricas de fundamentação.
3. [Reescrita de consulta para perguntas compostas](reescrita-de-consulta.md): Decomposição de intenção, pipeline multi-hop e ganho medido na recuperação de múltiplos documentos.

---

## 4. Reprodução do benchmark no Google Colab {: #4-execucao-do-benchmark-no-google-colab-gpu-a100l4 }

O repositório disponibiliza dois caminhos para reproduzir a avaliação em GPU:

- **Notebook interativo:** [`notebooks/colab_benchmark.ipynb`](https://github.com/maykonjuso/residencia-grupo-4/blob/feat/validacao-reescrita-consulta/notebooks/colab_benchmark.ipynb)
- **Script CLI direto:** [`colab_benchmark.py`](https://github.com/maykonjuso/residencia-grupo-4/blob/feat/validacao-reescrita-consulta/colab_benchmark.py)

### Passo a passo de execução

1. **Alocação de GPU:**
   - Abra o notebook no [Google Colab](https://colab.research.google.com/).
   - Em **Ambiente de execução** > **Alterar tipo de ambiente de execução**, selecione GPU **L4** ou **A100**.
2. **Autenticação (Opcional):**
   - Para baixar modelos do Hugging Face sem restrição de taxa, cadastre seu `HF_TOKEN` nos **Secrets** do Colab.
3. **Ambiente e dependências:**
   ```bash
   !git clone -b feat/validacao-reescrita-consulta https://github.com/maykonjuso/residencia-grupo-4.git
   %cd residencia-grupo-4
   !pip install -r requirements.txt
   ```
4. **Execução do benchmark:**
   ```bash
   !python3 colab_benchmark.py --backend hf --saida md
   ```
   - **Precisão adaptativa:** Com ≥ 20 GB de VRAM (A100/L4), o script opera em **FP16/BF16** (`RUMO_HF_4BIT=0`). Em GPUs menores (ex.: T4), ativa quantização **NF4 de 4 bits** (`RUMO_HF_4BIT=1`).
   - **Conformidade R3:** O script audita as estruturas exportadas e barra qualquer métrica de tempo.
5. **Arquivos gerados:**
   - Resultados exportados em `rag/avaliacao/resultado_benchmark_colab.json`, `respostas_comparativas.json` e `resultado_benchmark_colab.md`.

---

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Estrutura inicial da Entrega 3 (Épico #4): checklist, matriz de métricas e navegação | Grupo 04 |
    | 13/11/2026 | 3.0 | Consolidação das métricas de qualidade, purga de latência (R3), validação determinística e guia Colab GPU | Grupo 04 |
