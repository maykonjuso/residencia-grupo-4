"""Geração da resposta fundamentada nos chunks recuperados, com citação das fontes.

Este módulo garante duas regras de negócio (docs/entrega-1/regras-de-negocio.md):

- RN-02 · toda afirmação cita documento, página e URL: a regra 2 do prompt exige [n] depois
  de cada afirmação; `citacoes_usadas` resolve cada [n] em documento, página e URL; e
  `resposta_sem_citacao` acusa a resposta que não cita nada.
- RN-03 · fora da base, recusa: a regra 3 do prompt e o atalho de `gerar` sem trechos usam a
  mesma frase, `RECUSA`; `valores_sem_fonte` alerta quando aparece valor que não está nos trechos.
"""
import json
import re
import urllib.request
from functools import lru_cache

from . import config

# RN-03: a frase de recusa é uma só no sistema inteiro. Mudar aqui muda o prompt e o código.
RECUSA = "Não encontrei essa informação nas fontes da base."

# Regras 2 (RN-02) e 3 (RN-03) do prompt. Mexeu no texto? Rode a avaliação (CLAUDE.md).
INSTRUCOES = f"""Você é o RUmo, assistente dos estudantes da FCTE/UnB (campus Gama) para dúvidas sobre o \
Restaurante Universitário e sobre o fluxo de disciplinas dos cursos.
Regras:
1. Responda em português, de forma direta, usando SOMENTE as informações dos trechos numerados abaixo.
2. Depois de cada afirmação, cite o trecho usado entre colchetes, por exemplo [1] ou [2][3].
3. Se os trechos não trazem a resposta, diga exatamente: "{RECUSA}" \
e sugira o órgão responsável. Não invente valores, datas, códigos ou pré-requisitos.
4. Se a informação depende do perfil do estudante (grupo de pagamento, curso, ano de ingresso), diga isso.
5. Seja conciso: no máximo 120 palavras. Copie valores, datas, códigos e nomes exatamente como estão nos trechos."""


def montar_contexto(trechos: list[dict]) -> str:
    partes = []
    for i, t in enumerate(trechos, start=1):
        secao = f" · seção: {t['secao']}" if t.get("secao") else ""
        partes.append(f"[{i}] Fonte {t['doc_id']} — {t['titulo']} ({t['orgao']}), p. {t['pagina']}{secao}\n{t['texto']}")
    return "\n\n".join(partes)


def montar_mensagens(pergunta: str, trechos: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": INSTRUCOES},
        {"role": "user", "content": f"Trechos recuperados:\n\n{montar_contexto(trechos)}\n\nPergunta: {pergunta}"},
    ]


@lru_cache(maxsize=1)
def _hf():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(config.MODELO_HF)
    extra = {}
    if config.HF_4BIT and torch.cuda.is_available():
        # 4 bits (NF4): o Qwen2.5-7B cabe em ~5,5 GB de VRAM (RTX 4060 de 8 GB)
        from transformers import BitsAndBytesConfig
        extra["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)
    modelo = AutoModelForCausalLM.from_pretrained(
        config.MODELO_HF, dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map={"": 0} if torch.cuda.is_available() else "cpu", **extra)
    return tok, modelo


def _gerar_hf(msgs):
    tok, modelo = _hf()
    entrada = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                      return_dict=True).to(modelo.device)
    saida = modelo.generate(**entrada, max_new_tokens=512, do_sample=False, repetition_penalty=1.05)
    return tok.decode(saida[0][entrada["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def _post(url, corpo, cabecalhos=None):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json", **(cabecalhos or {})})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def _gerar_ollama(msgs):
    r = _post(f"{config.OLLAMA_URL}/api/chat",
              {"model": config.MODELO_OLLAMA, "messages": msgs, "stream": False, "options": {"temperature": 0}})
    return r["message"]["content"].strip()


def _gerar_openai(msgs):
    import os
    r = _post(f"{config.OPENAI_URL}/chat/completions",
              {"model": config.OPENAI_MODEL, "messages": msgs, "temperature": 0},
              {"Authorization": f"Bearer {os.environ['RUMO_OPENAI_KEY']}"})
    return r["choices"][0]["message"]["content"].strip()


def _gerar_extrativo(pergunta, trechos):
    """Sem LLM: devolve as frases dos trechos que mais compartilham termos com a pergunta."""
    from .indice import tokenizar
    termos = set(tokenizar(pergunta))
    candidatas = []
    for i, t in enumerate(trechos, start=1):
        for frase in re.split(r"(?<=[.;!?])\s+|\n", t["texto"]):
            sobreposicao = len(termos & set(tokenizar(frase)))
            if sobreposicao and len(frase) > 25:
                candidatas.append((sobreposicao, i, frase.strip()))
    candidatas.sort(key=lambda x: -x[0])
    if not candidatas:
        return RECUSA
    return "\n".join(f"- {f} [{i}]" for _, i, f in candidatas[:4])


def gerar(pergunta: str, trechos: list[dict], backend: str = config.BACKEND) -> str:
    if not trechos:                     # RN-03: sem trecho recuperado, nem chama o LLM
        return RECUSA
    msgs = montar_mensagens(pergunta, trechos)
    if backend == "hf":
        return _gerar_hf(msgs)
    if backend == "ollama":
        return _gerar_ollama(msgs)
    if backend == "openai":
        return _gerar_openai(msgs)
    return _gerar_extrativo(pergunta, trechos)


def _numeros_citados(resposta: str, n_trechos: int) -> list[int]:
    """Os [n] da resposta que apontam para um trecho que existe (de 1 a n_trechos)."""
    return sorted({int(n) for n in re.findall(r"\[(\d+)\]", resposta) if 0 < int(n) <= n_trechos})


def citacoes_usadas(resposta: str, trechos: list[dict]) -> list[dict]:
    """Lista as fontes efetivamente citadas na resposta (rastreabilidade)."""
    nums = _numeros_citados(resposta, len(trechos))
    return [{"n": n, **{k: trechos[n - 1][k] for k in ("doc_id", "titulo", "orgao", "pagina", "url", "chunk_id")}}
            for n in nums]


def eh_recusa(resposta: str) -> bool:
    """RN-03: a resposta é (ou contém) a recusa padrão."""
    return RECUSA.rstrip(".").lower() in resposta.lower()


def resposta_sem_citacao(resposta: str, trechos: list[dict]) -> bool:
    """RN-02: True quando a resposta afirma algo sem citar nenhum trecho válido.
    A recusa não cita fonte de propósito, então não conta como violação."""
    if eh_recusa(resposta):
        return False
    return not _numeros_citados(resposta, len(trechos))


PADRAO_VALOR = re.compile(r"R\$\s?\d+(?:[.,]\d+)?|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{1,2}h(?:\d{2})?\b|\b[A-Z]{3}\d{4}\b|\b\d+(?:[.,]\d+)?\s?(?:créditos|horas|vagas|semestres)\b")


def _normalizar(v: str) -> str:
    return re.sub(r"\s+", "", v.lower()).replace(",00", "")


def valores_sem_fonte(resposta: str, trechos: list[dict]) -> list[str]:
    """Verificador de fidelidade: todo preço, data, horário, código de disciplina ou quantidade
    citado na resposta precisa aparecer em algum trecho recuperado. Os que não aparecem
    são devolvidos para o sistema alertar o estudante (possível alucinação)."""
    base = _normalizar(" ".join(t["texto"] + " " + t.get("secao", "") for t in trechos))
    faltando = []
    for v in PADRAO_VALOR.findall(resposta):
        if _normalizar(v) not in base and v not in faltando:
            faltando.append(v)
    return faltando
