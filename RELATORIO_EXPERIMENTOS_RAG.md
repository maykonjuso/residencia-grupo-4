# Relatório de Experimentos: LLM vs RAG e Bateria de Testes (RUmo)

> **Data:** 11/11/2026  
> **Projeto:** RUmo — Assistente com RAG para o Restaurante Universitário e Fluxo da FCTE/UnB  
> **Contexto:** Residência em IA · Challenge 2 · Grupo 04  

---

## 1. Resumo da Sessão e Objetivos Alcançados

Nesta sessão, realizamos um estudo experimental comparativo completo para fundamentar as decisões de arquitetura do RUmo, diagnosticar o ambiente de execução e aprimorar a recuperação:

1. **Diagnóstico do CLI e Ambiente:**
   - Correção da ordem dos parâmetros na linha de comando (`--backend` após o subcomando).
   - Diagnóstico do ChromaDB local vazio (`denso hit@1=0.000`), explicando o porquê de estar no `.gitignore`.
   - Instalação e configuração de modelos locais no Ollama (`qwen2.5:7b` e `llama3.2`).
2. **Avaliação e Aprimoramento da Recuperação (Perguntas Compostas):**
   - Teste de 7 perguntas compostas reais.
   - Identificação e correção de gargalos na função `decompor()` em [`rag/rumo_rag/indice.py`](rag/rumo_rag/indice.py) (ampliação da regex `GATILHOS` e prevenção de descarte de subperguntas por stopwords).
3. **Atendimento ao Critério de Pronto (4 Configurações):**
   - Desenvolvimento de scripts automatizados para executar 4 configurações distintas e escolher formalmente a melhor para o produto.

---

## 2. Scripts Criados e Prontos para Uso

Dois scripts autônomos foram criados e salvos dentro da pasta `rag/`:

### A. [`rag/testar_4_configuracoes.py`](rag/testar_4_configuracoes.py) (Critério de Pronto)
Executa as 4 configurações contra perguntas canônicas de preço, fluxo acadêmico e recusa fora da base, gerando a tabela consolidada de métricas.

**Como rodar na próxima sessão:**
```bash
cd ~/residencia-grupo-4-1/rag
source ../.venv/bin/activate
export RUMO_OLLAMA_MODEL=qwen2.5:7b
python testar_4_configuracoes.py
```

### B. [`rag/comparativo_rag.py`](rag/comparativo_rag.py)
Benchmark comparativo triplo focado em: LLM Pura vs RAG Extrativo vs RAG Generativo.

**Como rodar na próxima sessão:**
```bash
cd ~/residencia-grupo-4-1/rag
source ../.venv/bin/activate
export RUMO_OLLAMA_MODEL=qwen2.5:7b
python comparativo_rag.py
```

---

## 3. O que muda e por que muda: Análise das 4 Configurações

| # | Configuração | Tempo | Rastreabilidade / Fontes | Alucinações | Recusa Fora da Base | Veredito |
|---|---|:---:|:---:|:---:|:---:|---|
| **1** | **LLM Pura (Zero-shot)** | ~3–5s | ❌ 0% (sem fontes) | 🔴 Alta (inventa preços e disciplinas) | ❌ Falha (tenta adivinhar) | **Descartada:** Viola RF03 e RNF01 |
| **2** | **RAG Extrativo (Sem LLM)** | ⚡ <0.1s | 🟢 100% (trecho literal) | 🟢 Zero em números | ❌ Falha (recupera termos parecidos) | **Descartada:** Respostas truncadas e sem síntese |
| **3** | **RAG Generativo Simples ($k=3$)** | ~2–4s | 🟢 Alta (`[1]`, `[2]`) | 🟡 Baixa | 🟢 Acerta | **Insuficiente:** Perde regras em listas extensas |
| **4** | **RAG Generativo Completo ($k=5$ + Verificador)** | ~3–6s | 🟢 Total (`[1]` a `[5]`) | 🟢 Auditada por validador | 🟢 Acerta ("Não encontrei...") | 🏆 **ESCOLHIDA PARA O PRODUTO** |

### Justificativa da Escolha da Configuração 4 para o Produto:
- **Garante os Requisitos Centrais:** Atende integralmente a **RNF01** (Só fonte oficial), **RF03** (Citação obrigatória de documento, página e URL) e **RF04** (Recusa estrita fora da base).
- **Cobertura de Contexto ($k=5$):** Atinge $Hit@5 = 1,000$ no benchmark com o modelo `bge-m3`, garantindo que listas longas de isenção de RU e fluxos de disciplinas estejam no contexto do LLM.
- **Camada Dupla de Segurança:** O verificador pós-geração (`geracao.valores_sem_fonte`) audita a resposta e detecta qualquer número, data ou código que não constava nos documentos de origem.

---

## 4. Alterações Realizadas no Código-Fonte

### [`rag/rumo_rag/indice.py`](rag/rumo_rag/indice.py)
- **Ampliação da regex `GATILHOS`:**
  Adicionados os termos interrogativos faltantes: `quem`, `quantos`, `quantas`, `em que`, `de que`:
  ```python
  GATILHOS = r"(?:quanto|quanta|quantos|quantas|qual|quais|quem|como|quando|onde|que horas|até que|em que|de que|o que|posso|preciso)"
  ```
- **Ajuste no filtro de tamanho das subperguntas (`decompor`):**
  Evita que subperguntas legítimas como *"e como solicito?"* ou *"e quando começam as aulas?"* sejam descartadas por terem suas palavras convertidas em stopwords:
  ```python
  partes = [p.strip(" ?.") for p in partes if len(tokenizar(p)) >= 2 or len(p.split()) >= 3]
  ```

---

## 5. Próximos Passos Recomendados para a Próxima Sessão

1. **Popular o ChromaDB local:**
   Se desejar que a busca vetorial (`denso`) opere junto com o BM25 nas avaliações locais do Mac:
   ```bash
   cd ~/residencia-grupo-4-1/rag
   python -c '
   import json
   from rumo_rag import indice, config
   chunks = [json.loads(l) for l in open(config.CHUNKS, encoding="utf-8")]
   print(f"Indexando {len(chunks)} chunks no ChromaDB...")
   indice.indexar(chunks)
   '
   ```
2. **Atualizar a Documentação Oficial:**
   Inserir a tabela comparativa das 4 configurações na página de avaliação ([`docs/entrega-2/avaliacao.md`](docs/entrega-2/avaliacao.md)) ou de arquitetura ([`docs/entrega-2/arquitetura.md`](docs/entrega-2/arquitetura.md)).
3. **Commitar as Mudanças na sua Branch de Trabalho:**
   ```bash
   git checkout -b feat/comparativo-llm-rag
   git add rag/comparativo_rag.py rag/testar_4_configuracoes.py rag/rumo_rag/indice.py RELATORIO_EXPERIMENTOS_RAG.md
   git commit -m "feat(avaliacao): adiciona suite comparativa LLM vs RAG e aprimora decomposicao de consultas"
   ```
