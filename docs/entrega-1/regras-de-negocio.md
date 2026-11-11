# Regras de negócio

Os requisitos dizem o que o RUmo faz. As regras de negócio dizem o que ele **nunca pode deixar
de fazer**, qualquer que seja o modelo, o prompt ou a fonte da semana. O código já seguia estas
regras desde a Entrega 2, mas elas não estavam escritas em lugar nenhum, e regra não escrita é
regra que alguém quebra sem perceber. Quebrar uma delas é bug de produto, não questão de estilo.

Cada regra abaixo aponta para o requisito que a originou, para o trecho de código que a garante
e para o teste automático que acusa quando ela deixa de valer.

!!! abstract "Resumo"
    O RUmo só usa documento oficial (RN-01), cita a fonte de cada afirmação (RN-02), recusa o
    que não está na base (RN-03), não manda pergunta para fora da máquina por padrão (RN-04) e
    não coleta dado pessoal (RN-05). Há uma sexta regra em discussão, sobre não prescrever dieta.

## As regras

| ID | Regra | Por que existe | Origem |
|---|---|---|---|
| RN-01 | Só entra na base documento oficial e público, da UnB ou de órgão do governo federal, registrado no catálogo com URL e data de coleta | É o que separa o RUmo de um chatbot genérico: a resposta vale o que vale a fonte | RNF01 |
| RN-02 | Toda afirmação da resposta cita o trecho usado, e cada citação leva a documento, página e URL | Resposta sem fonte não é verificável pelo estudante | RF03 |
| RN-03 | Quando os trechos não trazem a resposta, o RUmo diz "Não encontrei essa informação nas fontes da base." e não inventa valor, data, código nem pré-requisito | Inventar o preço de uma refeição ou um pré-requisito causa dano real a quem perguntou | RF04 |
| RN-04 | Por padrão, nenhuma pergunta sai da máquina: LLM e embeddings rodam localmente, e API externa só é usada se alguém configurar isso de propósito | Privacidade de quem pergunta e independência de serviço pago | RNF02 |
| RN-05 | O RUmo não coleta dado pessoal: não pede login, não acessa o SIGAA e não associa pergunta a pessoa | LGPD e escopo do produto | RNF06 |

<p class="legenda">Tabela 1. Regras de negócio do RUmo e o requisito de onde cada uma vem (<a href="../escopo/">Escopo e requisitos</a>).</p>

!!! note "Mudança em relação à proposta da issue #9"
    A proposta original dizia "só fonte oficial **da UnB**". Na conferência com o catálogo, três
    fontes são oficiais mas não da UnB: a Lei nº 14.914/2024 do PNAES (F10, Planalto), o Guia
    Alimentar para a População Brasileira (F11, Ministério da Saúde) e o guia de alergênicos da
    ANVISA (F12). Por isso a RN-01 passou a dizer "da UnB ou de órgão do governo federal". Se o
    grupo preferir a versão restrita, essas três fontes saem da base.

## O que garante cada regra

| Regra | Comportamento do código que a garante | Onde | Teste |
|---|---|---|---|
| RN-01 | O catálogo é a única porta de entrada: `extracao.baixar` só baixa o que está em `catalogo.yaml`, e cada documento tem órgão, URL e a data de coleta do catálogo. `chunking.dividir` copia título, órgão e URL do catálogo para todo chunk, então nenhum trecho existe sem a fonte | `rag/catalogo.yaml`, `extracao.py`, `chunking.py` | `RN01FonteOficial` |
| RN-02 | A regra 2 do prompt exige `[n]` depois de cada afirmação. `montar_contexto` entrega ao LLM cada trecho numerado com documento, órgão e página. `citacoes_usadas` transforma cada `[n]` em documento, página e URL. `resposta_sem_citacao` acusa a resposta que não cita nada, e a linha de comando mostra o alerta | `geracao.py`, `__main__.py` | `RN02CitaFonte` |
| RN-03 | A frase de recusa é uma constante só, `RECUSA`, usada pelo prompt e pelo código. A regra 3 do prompt manda usá-la exatamente e proíbe inventar valores. Sem trechos, `gerar` recusa sem chamar o LLM; o modo extrativo recusa quando nenhuma frase casa com a pergunta. `valores_sem_fonte` alerta quando a resposta traz preço, data, horário ou código que não está nos trechos | `geracao.py` | `RN03RecusaForaDaBase` |
| RN-04 | O backend padrão é `hf`: Qwen2.5-7B em 4 bits pela biblioteca `transformers`, na própria máquina. O Ollama aponta para `localhost`. `_gerar_openai` só é chamado com `RUMO_LLM_BACKEND=openai` e uma chave em `RUMO_OPENAI_KEY`. Os embeddings (bge-m3) também rodam localmente. O `demo_offline.sh --prova` roda com a rede externa bloqueada | `config.py`, `geracao.py`, `indice.py`, `demo_offline.sh` | `RN04NadaSaiPorPadrao` |
| RN-05 | `gerar` recebe só a pergunta e os trechos, nada sobre quem perguntou. A saída de `responder` não tem campo de identidade. Nenhuma fonte é o próprio SIGAA (F34 é o manual público do portal). Nenhum módulo pede senha ou credencial | `geracao.py`, `__main__.py`, `catalogo.yaml` | `RN05SemDadoPessoal` |

<p class="legenda">Tabela 2. Comportamento que garante cada regra. Os arquivos ficam em <code>rag/rumo_rag/</code>, salvo indicação; os testes, em <code>rag/testes/test_regras_negocio.py</code>.</p>

Os testes não carregam LLM nem modelo de embedding, então rodam em menos de um segundo, sem GPU
e sem internet:

```bash
cd rag
python -m unittest discover -s testes -v
```

Na versão desta página são 22 testes, todos passando. Aplicado às oito respostas reais da
[demonstração](../entrega-2/demonstracao.md), o verificador da RN-02 encontrou sete respostas
com citação e uma recusa (D7, a pergunta sobre o wifi), nenhuma resposta sem fonte.

## Lacunas encontradas na conferência

Conferir regra contra código serve justamente para achar onde a garantia é mais fraca do que
parece. Estas são as lacunas encontradas; só a última foi resolvida nesta mudança, porque as
outras estão em componentes de outras pessoas.

| Regra | O que falta | Proposta | Componente |
|---|---|---|---|
| RN-03 | A busca sempre devolve *k* trechos, porque não há limiar mínimo de relevância. O atalho "sem trechos, recusa" só dispara com índice vazio; na prática a recusa depende de o LLM obedecer à regra 3 do prompt, como aconteceu em D7 | Limiar de relevância calibrado com perguntas sem resposta na base, antes de chamar o LLM | Recuperação, com a Avaliação (#18) |
| RN-01 | A data de coleta só existe no catálogo (campo `coleta`). Não chega ao chunk nem à citação: o campo `data` do chunk é a data do documento. Para cardápio isso importa (risco R02) | Levar a data de coleta para o metadado do chunk e mostrá-la na citação | Base de conhecimento |
| RN-01 | F36 (Regimento Interno da FCTE) está com URL `http://` | Trocar por `https://` e rodar a ingestão de novo | Base de conhecimento |
| RN-04 | O cliente do Chroma é criado sem desligar a telemetria. Na versão instalada (1.5.9) o envio já vem desativado no pacote e os eventos não levam texto, mas o `requirements.txt` aceita qualquer `chromadb>=1.0`, e só o `demo_offline.sh` desliga por variável de ambiente | Passar `Settings(anonymized_telemetry=False)` em `indice.colecao` | Recuperação |
| RN-04 | A primeira execução baixa os pesos dos modelos do Hugging Face. Nenhuma pergunta sai, mas a máquina acessa a internet | Registrar em [Como executar](../entrega-2/como-executar.md) que, depois do primeiro download, `HF_HUB_OFFLINE=1` deixa tudo local | GitPage |
| RN-02 | Nada acusava uma resposta sem citação | **Resolvido aqui:** `resposta_sem_citacao` e o alerta na linha de comando | Geração |

<p class="legenda">Tabela 3. Lacunas entre as regras e o código, com proposta e componente responsável.</p>

## Candidata a RN-06: cardápio sim, dieta não

> **RN-06 (proposta).** O RUmo informa o cardápio e o que dizem os guias oficiais, mas não
> prescreve dieta nem recomendação nutricional individual.

A base tem o Guia Alimentar (F11) e o guia da ANVISA (F12) para perguntas gerais de
alimentação, e a fronteira entre "o que o guia diz" e "o que você deve comer" é fácil de cruzar
sem perceber. Hoje essa regra está só na lista de [fora do escopo](escopo.md#fora-do-escopo-nesta-fase):
não há instrução no prompt nem teste que a cubra.

Se o grupo aprovar, o caminho é acrescentar ao prompt uma regra como *"Não prescreva dieta nem
recomendação nutricional individual; informe o cardápio ou o que o guia diz, cite a fonte e
sugira procurar um nutricionista"*, incluir perguntas desse tipo no conjunto de avaliação e,
como muda o prompt, rodar a avaliação no mesmo PR. Fica em discussão até a próxima planning.

## Como as regras entram no processo

Para a regra valer, ela precisa ser cobrada em todo PR, não só lembrada. A proposta para o
Definition of Done (#8) é que o item sobre RF03, RF04 e RNF passe a ser este:

- [ ] Nenhuma regra de negócio foi quebrada: `python -m unittest discover -s testes` passa

E mais um combinado: PR que muda uma regra muda também esta página e o teste correspondente,
no mesmo PR. Regra que muda só no código volta a ser regra não escrita.

??? abstract "Histórico de revisão"

    | Data | Versão | Descrição | Autor |
    | :---: | :---: | --- | --- |
    | 11/11/2026 | 1.0 | Formaliza RN-01 a RN-05, liga cada regra ao código e aos testes, registra as lacunas e a candidata RN-06 (issue #9) | Kyara Esteves |
