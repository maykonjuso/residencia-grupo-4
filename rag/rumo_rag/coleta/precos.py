"""Tabela de preços do RU por grupo de subsídio, estruturada a partir da base (issue #66).

O perfil no navegador guarda o grupo da pessoa e escolhe o valor *no navegador*.
Por isso o servidor devolve a tabela inteira, igual para todo mundo, sem saber quem
perguntou: nada do perfil precisa trafegar (RNF06).

Fonte: F04 ("Valores das refeições e grupos de acesso"). Cada valor carrega doc_id,
página e chunk_id, porque a resposta personalizada continua citando a fonte (RF03).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config

DOC_PRECOS = "F04"
GRUPOS = ("I", "II", "III", "IV")
REFEICOES = ("cafe", "almoco", "jantar")

_GRUPO = re.compile(r"Grupo\s+(IV|III|II|I)\b")
_CAFE = re.compile(r"Caf[ée] da manh[ãa]:\s*R\$\s*([\d.,]+)", re.I)
_ALMOCO_JANTAR = re.compile(r"Almo[çc]o e jantar:\s*R\$\s*([\d.,]+)", re.I)
_ALMOCO = re.compile(r"Almo[çc]o:\s*R\$\s*([\d.,]+)(?!\s*/)", re.I)
_JANTAR = re.compile(r"Jantar:\s*R\$\s*([\d.,]+)", re.I)


def _valor(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _grupo_do_chunk(chunk: dict) -> str | None:
    m = _GRUPO.search(chunk.get("secao", ""))
    if m:
        return m.group(1)
    m = re.search(r"^###\s*Grupo\s+(IV|III|II|I)\s*$", chunk["texto"], re.M)
    return m.group(1) if m else None


def estruturar(chunks: list[dict]) -> dict:
    """{'grupos': {'II': {'cafe': {...}, 'almoco': {...}, 'jantar': {...}}, ...}, 'avisos': [...]}"""
    grupos: dict[str, dict] = {}
    avisos: list[str] = []
    for c in chunks:
        if c["doc_id"] != DOC_PRECOS:
            continue
        g = _grupo_do_chunk(c)
        if g is None:
            continue
        fonte = {"doc_id": c["doc_id"], "pagina": c.get("pagina"), "chunk_id": c["chunk_id"],
                 "titulo": c.get("titulo", ""), "url": c.get("url", "")}
        precos = grupos.setdefault(g, {})

        def pos(ref: str, valor: float):
            precos.setdefault(ref, {"valor": valor, "fonte": fonte})

        if g == "I" and re.search(r"refei[çc][õo]es gratuitas", c["texto"], re.I):
            for ref in REFEICOES:
                pos(ref, 0.0)
        if m := _CAFE.search(c["texto"]):
            pos("cafe", _valor(m.group(1)))
        if m := _ALMOCO_JANTAR.search(c["texto"]):
            pos("almoco", _valor(m.group(1)))
            pos("jantar", _valor(m.group(1)))
        if m := _ALMOCO.search(c["texto"]):
            pos("almoco", _valor(m.group(1)))
        if m := _JANTAR.search(c["texto"]):
            pos("jantar", _valor(m.group(1)))

    for g in GRUPOS:
        faltando = [r for r in REFEICOES if r not in grupos.get(g, {})]
        if faltando:
            avisos.append(f"Grupo {g}: sem valor na base para {', '.join(faltando)}")
    return {"grupos": {g: grupos[g] for g in GRUPOS if g in grupos}, "avisos": avisos}


def carregar(caminho: Path = config.CHUNKS) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return estruturar([c for c in map(json.loads, f) if c.get("doc_id") == DOC_PRECOS])
