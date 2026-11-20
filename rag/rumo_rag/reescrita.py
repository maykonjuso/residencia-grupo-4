"""Pipeline em dois estágios para classificação e decomposição de consultas compostas.

Estágio 1: Classificador discriminativo System-1 (LiquidAI/d1-omni-600M) em GPU
           (CUDA ou Apple Silicon MPS em float16), sem geração autoregressiva de tokens.
Estágio 2: Reescrita e decomposição contextual via LLM local (Ollama ou HuggingFace), acionada apenas
           quando o classificador indica pergunta múltipla (com fallback sintático).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from functools import lru_cache
from typing import Any

from . import config

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

# Pré-filtro determinístico (< 0,1 ms): consultas sem conjunções nem múltiplas frases
# são simples e não precisam acionar o decisor nem o LLM.
_CONECTIVOS = re.compile(
    r"\b(?:e|ou|nem|mas|porém|além disso|também|ademais)\b|[;.]\s+\S",
    re.I,
)

_QUESTAO_COMPOSTA = {
    "query_structure": {
        "type": "choice",
        "instructions": "Does this student query ask a single question or multiple distinct questions/topics?",
        "criteria": {
            "single": "Only one question or comparison about one topic, even if it uses words like 'and' or 'or'",
            "multiple": "Two or more distinct questions or intents that require separate answers",
        },
    }
}

_DOMINIO_AGENTE = {
    "dominio": {
        "type": "choice",
        "instructions": "Which university domain does this student question belong to?",
        "criteria": {
            "ru": (
                "University dining hall / cafeteria (RU): meal prices, menu, lunch, dinner, breakfast, "
                "food allergies, milk/gluten, vegetarian, food assistance/scholarship, access turnstile."
            ),
            "fluxo": (
                "Academic courses and curriculum (FCTE/UnB): classes, prerequisites, credits, semesters, "
                "internship, dropping a class, enrollment, graduate courses."
            ),
        },
    }
}

_GATILHOS_FALLBACK = (
    r"(?:quanto|quanta|quantos|quantas|qual|quais|quem|como|quando|onde|"
    r"que horas|até que|em que|de que|o que|posso|preciso|tem direito|abre)"
)

_SYSTEM_DECOMPOSICAO = (
    "Você é o módulo de reescrita e decomposição de consultas do sistema RAG acadêmico RUmo "
    "(FCTE/UnB - campus Gama, cobrindo Restaurante Universitário/RU e fluxo de cursos).\n"
    "Domínios disponíveis para o campo eixo:\n"
    '- "ru": Restaurante Universitário (cardápio, refeições, preços, alergênicos/leite, auxílio/bolsa alimentação, horários, catraca).\n'
    '- "fluxo": fluxo de disciplinas, cursos de engenharia da FCTE, pré-requisitos, créditos, estágio, trancamento/desistência, matrícula, pós-graduação.\n'
    '- "ambos": somente quando uma subpergunta indivisível exigir os dois domínios.\n'
    "Sua tarefa é quebrar uma pergunta composta do estudante em 2 ou mais subperguntas independentes, diretas e autocontidas.\n"
    "Regras críticas:\n"
    "1. Explicite o sujeito/domínio implícito em cada subpergunta (ex.: se falar de 'almoço', 'jantar', 'refeição', "
    "'café da manhã' ou 'carteirinha', inclua 'no RU'; se citar um curso ou campus em uma parte, mantenha onde fizer sentido).\n"
    "2. Nunca junte duas perguntas ou assuntos distintos na mesma subpergunta (mesmo que venham ligados por 'e' ou vírgula sem novo pronome interrogativo, como 'e funciona aos sábados?'). Separe cada intenção em um item próprio.\n"
    "3. Não invente informações nem responda à pergunta; apenas reescreva as subperguntas com o seu eixo.\n"
    '4. Retorne APENAS JSON no formato: {"subperguntas": [{"pergunta": "subpergunta 1?", "eixo": "ru"}, {"pergunta": "subpergunta 2?", "eixo": "fluxo"}, {"pergunta": "subpergunta 3?", "eixo": "ru"}]}.'
)


def dispositivo_gpu() -> tuple[str, Any]:
    """Seleciona GPU sempre que disponível (CUDA > MPS em float16), com fallback em CPU."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda", torch.float16
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps", torch.float16
        return "cpu", torch.float32
    except ImportError:
        return "cpu", None


@lru_cache(maxsize=1)
def _carregar_decisor():
    from transformers import AutoModel

    device, dtype = dispositivo_gpu()
    kw = {"torch_dtype": dtype} if dtype is not None else {}
    return (
        AutoModel.from_pretrained(
            config.MODELO_DECISAO,
            trust_remote_code=True,
            **kw,
        )
        .to(device)
        .eval()
    )


def probabilidade_multipla(pergunta: str) -> float:
    """Probabilidade bruta de 'múltiplas questões' do d1-omni-600M (sem pré-filtro; propaga erros)."""
    modelo = _carregar_decisor()
    res = modelo.system_one(pergunta.strip(), _QUESTAO_COMPOSTA)
    return float(res["answers"]["query_structure"]["probabilities"]["multiple"])


def classificar_composta(pergunta: str) -> tuple[bool, float]:
    """Estágio 1 (System-1 em GPU): retorna (eh_composta, probabilidade_multipla)."""
    q = pergunta.strip()
    if not q:
        return False, 0.0
    if q.count("?") >= 2:
        return True, 0.95
    if not _CONECTIVOS.search(q):
        return False, 0.0
    if not config.USAR_D1:
        return False, 0.0

    try:
        prob_multi = probabilidade_multipla(q)
        return prob_multi >= config.LIMIAR_COMPOSTA, round(prob_multi, 4)
    except Exception:
        # RUMO_STRICT_REWRITE=1 propaga o erro (usado no benchmark/Colab para não mascarar falhas).
        if os.getenv("RUMO_STRICT_REWRITE") == "1":
            raise
        # Fallback gracioso, mas nunca silencioso: o erro é registrado uma vez no stderr.
        _avisar_falha_classificador()
        return False, 0.0


_AVISO_EMITIDO = False


def _avisar_falha_classificador() -> None:
    global _AVISO_EMITIDO
    if _AVISO_EMITIDO:
        return
    _AVISO_EMITIDO = True
    import sys
    import traceback

    print(
        "[reescrita] AVISO: Estágio 1 (d1-omni-600M) falhou; consultas serão tratadas como simples.",
        file=sys.stderr,
    )
    traceback.print_exc(file=sys.stderr)


def _extrair_itens_subperguntas_json(texto: str) -> list[dict[str, str]]:
    """Extrai lista normalizada [{'pergunta': ..., 'eixo': ...}] de JSON retornado pelo LLM."""
    if not texto or not isinstance(texto, str):
        return []
    texto_limpo = texto.strip()
    match_dict = re.search(r"\{.*\}", texto_limpo, re.DOTALL)
    if match_dict:
        texto_limpo = match_dict.group(0)
    else:
        match_lista = re.search(r"\[.*\]", texto_limpo, re.DOTALL)
        if match_lista:
            texto_limpo = match_lista.group(0)
    try:
        dados = json.loads(texto_limpo)
    except Exception:
        return []
    if isinstance(dados, dict):
        subs = dados.get("subperguntas", [])
    elif isinstance(dados, list):
        subs = dados
    else:
        return []
    if not isinstance(subs, list):
        return []

    itens: list[dict[str, str]] = []
    for item in subs:
        if isinstance(item, str):
            p = item.strip()
            eixo = ""
        elif isinstance(item, dict):
            p = str(item.get("pergunta") or item.get("subpergunta") or "").strip()
            eixo_raw = str(item.get("eixo") or "").strip().lower()
            eixo = eixo_raw if eixo_raw in ("ru", "fluxo", "ambos") else ""
        else:
            continue
        if len(p) > 5:
            itens.append({"pergunta": p, "eixo": eixo})
    return itens


def _extrair_subperguntas_json(texto: str) -> list[str]:
    """Extrai e valida a lista de subperguntas a partir de JSON retornado pelo LLM."""
    return [item["pergunta"] for item in _extrair_itens_subperguntas_json(texto)]


def _decompor_ollama_bruto(pergunta: str) -> str:
    """Executa chamada ao Ollama para decomposição e retorna o conteúdo bruto."""
    corpo = {
        "model": config.MODELO_DECOMPOSITOR,
        "messages": [
            {"role": "system", "content": _SYSTEM_DECOMPOSICAO},
            {"role": "user", "content": pergunta},
        ],
        "format": "json",
        "keep_alive": "10m",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 220},
    }
    req = urllib.request.Request(
        f"{config.OLLAMA_URL}/api/chat",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    return dados.get("message", {}).get("content", "")


def _decompor_ollama(pergunta: str) -> list[str]:
    """Estágio 2 via Ollama HTTP: desmembra e contextualiza subperguntas em JSON estrito."""
    return _extrair_subperguntas_json(_decompor_ollama_bruto(pergunta))


def _decompor_hf_bruto(pergunta: str) -> str:
    """Executa chamada ao modelo HuggingFace local e retorna o conteúdo bruto."""
    from . import geracao

    tok, modelo = geracao._hf()
    msgs = [
        {"role": "system", "content": _SYSTEM_DECOMPOSICAO},
        {"role": "user", "content": pergunta},
    ]
    entrada = tok.apply_chat_template(
        msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True
    ).to(modelo.device)
    saida = modelo.generate(
        **entrada,
        max_new_tokens=220,
        do_sample=False,
        repetition_penalty=1.05,
    )
    return tok.decode(saida[0][entrada["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def _decompor_hf(pergunta: str) -> list[str]:
    """Estágio 2 via HuggingFace Transformers: desmembra e contextualiza subperguntas."""
    return _extrair_subperguntas_json(_decompor_hf_bruto(pergunta))


def _decompor_openai_bruto(pergunta: str) -> str:
    """Executa chamada à API compatível com OpenAI/OpenRouter e retorna o conteúdo bruto."""
    from . import geracao

    msgs = [
        {"role": "system", "content": _SYSTEM_DECOMPOSICAO},
        {"role": "user", "content": pergunta},
    ]
    return geracao._gerar_openai(msgs)


def _decompor_openai(pergunta: str) -> list[str]:
    """Estágio 2 via API OpenAI/OpenRouter: desmembra e contextualiza subperguntas."""
    return _extrair_subperguntas_json(_decompor_openai_bruto(pergunta))


@lru_cache(maxsize=256)
def _decompor_llm_com_eixo(pergunta: str, backend: str = "auto") -> tuple[tuple[str, str], ...]:
    """Estágio 2 (Teste 1): desmembra e já rotula o eixo de cada subpergunta no mesmo JSON."""
    def _parse(bruto: str) -> tuple[tuple[str, str], ...]:
        return tuple((i["pergunta"], i["eixo"]) for i in _extrair_itens_subperguntas_json(bruto))

    if backend == "ollama":
        return _parse(_decompor_ollama_bruto(pergunta))
    if backend == "hf":
        return _parse(_decompor_hf_bruto(pergunta))
    if backend == "openai":
        return _parse(_decompor_openai_bruto(pergunta))
    if backend == "auto":
        if config.BACKEND == "openai":
            tentativas = [_decompor_openai_bruto]
        elif config.BACKEND == "hf":
            tentativas = [_decompor_hf_bruto, _decompor_ollama_bruto]
        else:
            tentativas = [_decompor_ollama_bruto, _decompor_hf_bruto]
        erros = []
        for fn in tentativas:
            try:
                itens = _parse(fn(pergunta))
                if len(itens) >= 2:
                    return itens
            except Exception as e:
                erros.append(e)
        if erros and len(erros) == len(tentativas):
            raise RuntimeError(f"Todos os backends de decomposição LLM falharam: {erros}")
        return ()
    raise ValueError(f"Backend desconhecido para decomposição: {backend}")


@lru_cache(maxsize=256)
def _decompor_llm(pergunta: str, backend: str = "auto") -> tuple[str, ...]:
    """Estágio 2: desmembra e contextualiza subperguntas via LLM (Ollama, HF ou OpenAI)."""
    if backend == "ollama":
        return tuple(_decompor_ollama(pergunta))
    if backend == "hf":
        return tuple(_decompor_hf(pergunta))
    if backend == "openai":
        return tuple(_decompor_openai(pergunta))
    if backend == "auto":
        if config.BACKEND == "openai":
            tentativas = [_decompor_openai]
        elif config.BACKEND == "hf":
            tentativas = [_decompor_hf, _decompor_ollama]
        else:
            tentativas = [_decompor_ollama, _decompor_hf]
        erros = []
        for fn in tentativas:
            try:
                subs = fn(pergunta)
                if len(subs) >= 2:
                    return tuple(subs)
            except Exception as e:
                erros.append(e)
        if erros and len(erros) == len(tentativas):
            raise RuntimeError(f"Todos os backends de decomposição LLM falharam: {erros}")
        return ()
    raise ValueError(f"Backend desconhecido para decomposição: {backend}")


def classificar_dominio_d1(subpergunta: str, limiar_confianca: float = 0.60) -> list[str]:
    """Teste 2 (System-1 zero-shot): classifica subpergunta ambígua entre 'ru' e 'fluxo' via d1-omni."""
    if not config.USAR_D1:
        return ["ru", "fluxo"]
    try:
        modelo = _carregar_decisor()
        res = modelo.system_one(subpergunta.strip(), _DOMINIO_AGENTE)
        probs = res["answers"]["dominio"]["probabilities"]
        p_ru = float(probs.get("ru", 0.0))
        p_fluxo = float(probs.get("fluxo", 0.0))
        if max(p_ru, p_fluxo) < limiar_confianca:
            return ["ru", "fluxo"]
        return ["ru"] if p_ru >= p_fluxo else ["fluxo"]
    except Exception:
        return ["ru", "fluxo"]


def _decompor_fallback(pergunta: str) -> list[str]:
    """Fallback sintático usado apenas se nenhum backend LLM responder."""
    partes = re.split(
        rf"(?<=[?!.;])\s+|,?\s+e\s+(?={_GATILHOS_FALLBACK}\b)",
        pergunta.strip(),
        flags=re.I,
    )
    eh_pergunta = re.compile(rf"(?:\b{_GATILHOS_FALLBACK}\b|\?$)", re.I)
    contexto = ""
    perguntas = []
    for idx, p in enumerate(partes):
        p_limpa = p.strip(" ?.")
        if len(p_limpa.split()) < 3:
            continue
        if idx == 0 and not eh_pergunta.search(p.strip()) and ("estudante" in p.lower() or "graduação" in p.lower()):
            contexto = p_limpa
        else:
            perguntas.append(p_limpa)
    if len(perguntas) < 2:
        return []
    return [f"{contexto}. {p}" if contexto else p for p in perguntas]


def decompor(pergunta: str, backend: str = "auto") -> list[str]:
    """Executa Estágio 1 (d1-omni-600M em GPU) e, se composta, Estágio 2 (LLM / fallback)."""
    eh_composta, _ = classificar_composta(pergunta)
    if not eh_composta:
        return []
    if backend == "fallback":
        return _decompor_fallback(pergunta)
    try:
        subs = list(_decompor_llm(pergunta.strip(), backend=backend))
        if len(subs) >= 2:
            return subs
    except Exception:
        pass
    return _decompor_fallback(pergunta)


def decompor_com_roteamento(pergunta: str, backend: str = "auto") -> list[dict[str, str]]:
    """Decompõe consulta composta retornando subperguntas e eixo sugerido [{'pergunta', 'eixo'}]."""
    if backend == "fallback":
        return [{"pergunta": s, "eixo": ""} for s in _decompor_fallback(pergunta)]
    try:
        itens = _decompor_llm_com_eixo(pergunta.strip(), backend=backend)
        if len(itens) >= 2:
            return [{"pergunta": p, "eixo": e} for p, e in itens]
    except Exception:
        pass
    return [{"pergunta": s, "eixo": ""} for s in _decompor_fallback(pergunta)]
