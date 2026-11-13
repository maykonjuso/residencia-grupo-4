"""Pipeline em dois estágios para classificação e decomposição de consultas compostas.

Estágio 1: Classificador discriminativo System-1 (LiquidAI/d1-omni-600M) em GPU
           (CUDA ou Apple Silicon MPS em float16), sem geração autoregressiva de tokens.
Estágio 2: Reescrita e decomposição contextual via LLM local (Ollama), acionada apenas
           quando o classificador indica pergunta múltipla (com fallback sintático).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from functools import lru_cache

import torch

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

_GATILHOS_FALLBACK = (
    r"(?:quanto|quanta|quantos|quantas|qual|quais|quem|como|quando|onde|"
    r"que horas|até que|em que|de que|o que|posso|preciso|tem direito|abre)"
)

_SYSTEM_DECOMPOSICAO = (
    "Você é o módulo de reescrita e decomposição de consultas do sistema RAG acadêmico RUmo "
    "(FCTE/UnB - campus Gama, cobrindo Restaurante Universitário/RU e fluxo de cursos).\n"
    "Sua tarefa é quebrar uma pergunta composta do estudante em 2 ou mais subperguntas independentes, diretas e autocontidas.\n"
    "Regras críticas:\n"
    "1. Explicite o sujeito/domínio implícito em cada subpergunta (ex.: se falar de 'almoço', 'jantar', 'refeição', "
    "'café da manhã' ou 'carteirinha', inclua 'no RU'; se citar um curso ou campus em uma parte, mantenha onde fizer sentido).\n"
    "2. Não invente informações nem responda à pergunta; apenas reescreva as subperguntas.\n"
    '3. Retorne APENAS JSON no formato: {"subperguntas": ["subpergunta 1?", "subpergunta 2?"]}.'
)


def dispositivo_gpu() -> tuple[str, torch.dtype]:
    """Seleciona GPU sempre que disponível (CUDA > MPS em float16), com fallback em CPU."""
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


@lru_cache(maxsize=1)
def _carregar_decisor():
    from transformers import AutoModel

    device, dtype = dispositivo_gpu()
    return (
        AutoModel.from_pretrained(
            config.MODELO_DECISAO,
            trust_remote_code=True,
            dtype=dtype,
        )
        .to(device)
        .eval()
    )


def classificar_composta(pergunta: str) -> tuple[bool, float]:
    """Estágio 1 (System-1 em GPU): retorna (eh_composta, probabilidade_multipla)."""
    q = pergunta.strip()
    if not q:
        return False, 0.0
    if q.count("?") >= 2:
        return True, 0.95
    if not _CONECTIVOS.search(q):
        return False, 0.0

    modelo = _carregar_decisor()
    res = modelo.system_one(q, _QUESTAO_COMPOSTA)
    probs = res["answers"]["query_structure"]["probabilities"]
    prob_multi = float(probs["multiple"])
    return prob_multi >= config.LIMIAR_COMPOSTA, round(prob_multi, 4)


@lru_cache(maxsize=256)
def _decompor_llm(pergunta: str) -> tuple[str, ...]:
    """Estágio 2: desmembra e contextualiza subperguntas via Ollama em JSON estrito."""
    corpo = {
        "model": config.MODELO_DECOMPOSITOR,
        "messages": [
            {"role": "system", "content": _SYSTEM_DECOMPOSICAO},
            {"role": "user", "content": pergunta},
        ],
        "format": "json",
        "keep_alive": "10m",
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 140},
    }
    req = urllib.request.Request(
        f"{config.OLLAMA_URL}/api/chat",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    conteudo = json.loads(dados["message"]["content"])
    subs = conteudo.get("subperguntas", [])
    limpas = [s.strip() for s in subs if isinstance(s, str) and len(s.strip()) > 5]
    return tuple(limpas)


def _decompor_fallback(pergunta: str) -> list[str]:
    """Fallback sintático usado apenas se o endpoint Ollama não responder."""
    partes = re.split(
        rf"[?!.;]\s+|,?\s+e\s+(?={_GATILHOS_FALLBACK}\b)",
        pergunta.strip(),
        flags=re.I,
    )
    partes = [p.strip(" ?.") for p in partes if len(p.split()) >= 3]
    if len(partes) < 2:
        return []
    eh_pergunta = re.compile(rf"(?:\b{_GATILHOS_FALLBACK}\b|\?$)", re.I)
    contexto = ""
    perguntas = []
    for idx, p in enumerate(partes):
        if idx == 0 and not eh_pergunta.search(p) and ("estudante" in p.lower() or "graduação" in p.lower()):
            contexto = p
        else:
            perguntas.append(p)
    if len(perguntas) < 2:
        return []
    return [f"{contexto}. {p}" if contexto else p for p in perguntas]


def decompor(pergunta: str) -> list[str]:
    """Executa Estágio 1 (d1-omni-600M em GPU) e, se composta, Estágio 2 (LLM / fallback)."""
    eh_composta, _ = classificar_composta(pergunta)
    if not eh_composta:
        return []
    try:
        subs = list(_decompor_llm(pergunta.strip()))
        if len(subs) >= 2:
            return subs
    except Exception:
        pass
    return _decompor_fallback(pergunta)
