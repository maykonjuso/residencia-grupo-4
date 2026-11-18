"""API HTTP do RUmo, no contrato combinado com o Grupo 09 (docs/visao/escopo-grupos.md).

  uvicorn rumo_rag.api:app --port 8001      # dentro de rag/

  POST /perguntar   {"pergunta": "...", "contexto": {"campus": "gama", "data": "2026-11-11"}, "max_trechos": 5}
  GET  /saude       backend de geração, modo de busca e quantidade de chunks
  GET  /precos      tabela de preços por grupo, com fonte (o perfil escolhe o valor no navegador, #66)
  GET  /cardapio?data=2026-11-09&refeicao=almoco   cardápio por compartimento (#54)
  GET  /web/...     módulo do perfil (rumo-perfil.js) e página de demonstração

O orquestrador do portal (FcteMapping) e o OpenClaw chamam esta rota. A base, o índice e o
prompt continuam só do Grupo 04.
"""
import logging
import os
import re
import secrets
import time
from datetime import date

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import config, geracao, indice
from .coleta import cardapio as cardapio_estruturado
from .coleta import precos as tabela_precos

log = logging.getLogger("rumo.api")
DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
SEM_BASE = "Não encontrei essa informação nas fontes da base."
# Publicada na internet, a API gastaria a cota do LLM de quem chamasse. Com RUMO_API_TOKEN definido,
# /perguntar exige "Authorization: Bearer <token>" (o mesmo valor em RUMO_API_TOKEN no FcteMapping).
TOKEN = os.getenv("RUMO_API_TOKEN", "").strip()

app = FastAPI(title="RUmo · Grupo 04", version="1.0.0")
WEB = Path(__file__).resolve().parent.parent / "web"
if WEB.is_dir():
    app.mount("/web", StaticFiles(directory=WEB, html=True), name="web")


class Contexto(BaseModel):
    model_config = ConfigDict(extra="ignore")
    campus: str = "gama"
    data: date | None = None
    curso: str | None = Field(default=None, max_length=60)


class Pergunta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pergunta: str = Field(min_length=1, max_length=1000)
    contexto: Contexto = Field(default_factory=Contexto)
    max_trechos: int = Field(default=config.TOP_K, ge=1, le=config.MAX_TRECHOS)


def com_data(pergunta: str, contexto: Contexto) -> str:
    """'hoje' e 'amanhã' viram a data: o cardápio é indexado por dia (dd/mm), e o BM25 acha a data exata."""
    if not contexto.data or not re.search(r"\b(hoje|amanh[ãa])\b", pergunta, re.I):
        return pergunta
    d = contexto.data
    if re.search(r"\bamanh[ãa]\b", pergunta, re.I):
        d = date.fromordinal(d.toordinal() + 1)
    return f"{pergunta} ({DIAS[d.weekday()]}, {d:%d/%m/%Y})"


@app.get("/saude")
def saude():
    chunks, _ = indice._bm25()
    return {"status": "ok", "grupo": "grupo04", "busca": config.BUSCA, "backend": config.BACKEND, "token": bool(TOKEN),
            "modelo": {"hf": config.MODELO_HF, "ollama": config.MODELO_OLLAMA,
                       "openai": config.OPENAI_MODEL}.get(config.BACKEND), "chunks": len(chunks)}


def exigir_token(authorization: str | None) -> None:
    if not TOKEN:
        return
    esquema, _, valor = (authorization or "").partition(" ")
    if esquema.lower() != "bearer" or not secrets.compare_digest(valor.strip().encode(), TOKEN.encode()):
        raise HTTPException(401, "Token ausente ou inválido.", headers={"WWW-Authenticate": "Bearer"})


@app.post("/perguntar")
def perguntar(entrada: Pergunta, authorization: str | None = Header(default=None)):
    exigir_token(authorization)
    inicio = time.monotonic()
    pergunta = com_data(entrada.pergunta.strip(), entrada.contexto)
    if entrada.contexto.curso and entrada.contexto.curso.lower() not in pergunta.lower():
        pergunta += f" (curso: {entrada.contexto.curso})"
    trechos = indice.buscar(pergunta, k=entrada.max_trechos, modo=config.BUSCA)
    backend = config.BACKEND
    try:
        resposta = geracao.gerar(pergunta, trechos, backend)
    except Exception as exc:  # LLM fora do ar ou cota estourada: responde com as frases das fontes
        log.warning("Geração com %s falhou (%s); usando o modo extrativo.", backend, type(exc).__name__)
        backend = "extrativo"
        resposta = geracao.gerar(pergunta, trechos, backend)
    fontes = geracao.citacoes_usadas(resposta, trechos)
    encontrou = bool(fontes) and not resposta.startswith(SEM_BASE)
    return {
        "grupo": "grupo04",
        "resposta": resposta,
        "encontrou_base": encontrou,
        "fontes": [{k: f[k] for k in ("n", "doc_id", "titulo", "orgao", "pagina", "url")} for f in fontes],
        "valores_sem_fonte": geracao.valores_sem_fonte(resposta, trechos),
        "backend": backend,
        "tempo_ms": int((time.monotonic() - inicio) * 1000),
    }


# Rotas de dados para a interface (#58). Só leitura e iguais para todo mundo: não recebem
# nada do perfil, que fica no navegador (#66). Sem LLM, então não gastam cota nem pedem token.

@app.get("/precos")
def precos():
    return tabela_precos.carregar()


@app.get("/cardapio")
def cardapio(data: date, refeicao: str = Query(pattern="^(cafe|almoco|jantar)$")):
    resultado = cardapio_estruturado.buscar(data.isoformat(), refeicao)
    if not resultado:
        raise HTTPException(404, SEM_BASE)
    return resultado[0]
