"""API HTTP do RUmo, no contrato combinado com o Grupo 09 (docs/visao/escopo-grupos.md).

  uvicorn rumo_rag.api:app --port 8002      # dentro de rag/

  GET  /            saudação e status da API multiagente
  GET  /saude       backend de geração, modo de busca, chunks e status multiagente
  POST /perguntar   {"pergunta": "...", "contexto": {"campus": "gama", "data": "2026-11-20"}, "max_trechos": 5}

O orquestrador do portal (FcteMapping) e o OpenClaw chamam esta rota. A base, o índice e os
prompts dos agentes continuam exclusivos do Grupo 04.
"""
import logging
import os
import re
import secrets
import time
from datetime import date

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from . import config, indice
from .agentes import AgenteFluxo, AgenteRU, Orquestrador
from .coleta import cardapio

log = logging.getLogger("rumo.api")
DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
SEM_BASE = "Não encontrei essa informação nas fontes da base."
AGENTES_ATIVOS = ("Agente RU", "Agente Fluxo", "Agente Validador", "Sintetizador")
# Publicada na internet, a API gastaria a cota do LLM de quem chamasse. Com RUMO_API_TOKEN definido,
# /perguntar exige "Authorization: Bearer <token>" (o mesmo valor em RUMO_API_TOKEN no FcteMapping).
TOKEN = os.getenv("RUMO_API_TOKEN", "").strip()
_CORS_ORIGINS = [
    o.strip() for o in os.getenv("RUMO_CORS_ORIGINS", "*").split(",") if o.strip()
] or ["*"]

app = FastAPI(title="RUmo · Grupo 04", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


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
    trace: bool = False
    incluir_trace: bool = False


def com_data(pergunta: str, contexto: Contexto) -> str:
    """'hoje' e 'amanhã' viram a data: o cardápio é indexado por dia (dd/mm), e o BM25 acha a data exata."""
    if not contexto.data or not re.search(r"\b(hoje|amanh[ãa])\b", pergunta, re.I):
        return pergunta
    d = contexto.data
    if re.search(r"\bamanh[ãa]\b", pergunta, re.I):
        d = date.fromordinal(d.toordinal() + 1)
    return f"{pergunta} ({DIAS[d.weekday()]}, {d:%d/%m/%Y})"


def _criar_orquestrador() -> Orquestrador:
    modo = config.BUSCA if config.BUSCA in ("denso", "bm25", "hibrido") else "bm25"
    return Orquestrador(
        agente_ru=AgenteRU(modo=modo),
        agente_fluxo=AgenteFluxo(modo=modo),
    )


def _pagina_int(valor: object) -> int:
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    return 1


def _executar_com_fallback(
    orq: Orquestrador,
    pergunta: str,
    max_trechos: int,
    backend: str,
) -> tuple[dict, str]:
    try:
        resultado = orq.executar(pergunta, k=max_trechos, backend=backend)
        if backend != "extrativo" and any(
            p.get("erro") for p in resultado.get("partes", [])
        ):
            raise RuntimeError("Falha de geração em parte multiagente")
        return resultado, backend
    except Exception as exc:
        if backend == "extrativo":
            raise
        log.warning(
            "Execução multiagente com %s falhou (%s); usando o modo extrativo.",
            backend,
            type(exc).__name__,
        )
        resultado = orq.executar(pergunta, k=max_trechos, backend="extrativo")
        return resultado, "extrativo"


@app.get("/")
def raiz():
    return {
        "servico": "RUmo · Grupo 04",
        "status": "ok",
        "multiagente": True,
        "rotas": ["/saude", "/perguntar"],
    }


@app.get("/saude")
def saude():
    chunks, _ = indice._bm25()
    dados_semana, _ = cardapio.carregar_semana_atual()
    return {
        "status": "ok",
        "grupo": "grupo04",
        "busca": config.BUSCA,
        "backend": config.BACKEND,
        "token": bool(TOKEN),
        "modelo": {
            "hf": config.MODELO_HF,
            "ollama": config.MODELO_OLLAMA,
            "openai": config.OPENAI_MODEL,
        }.get(config.BACKEND),
        "chunks": len(chunks),
        "multiagente": True,
        "agentes": list(AGENTES_ATIVOS),
        "cardapio_semanal": dados_semana is not None,
    }


def exigir_token(authorization: str | None) -> None:
    if not TOKEN:
        return
    esquema, _, valor = (authorization or "").partition(" ")
    if esquema.lower() != "bearer" or not secrets.compare_digest(valor.strip().encode(), TOKEN.encode()):
        raise HTTPException(401, "Token ausente ou inválido.", headers={"WWW-Authenticate": "Bearer"})


@app.post("/perguntar")
def perguntar(
    entrada: Pergunta,
    trace: bool = False,
    authorization: str | None = Header(default=None),
):
    exigir_token(authorization)
    inicio = time.monotonic()
    pergunta = com_data(entrada.pergunta.strip(), entrada.contexto)
    if entrada.contexto.curso and entrada.contexto.curso.lower() not in pergunta.lower():
        pergunta += f" (curso: {entrada.contexto.curso})"

    orq = _criar_orquestrador()
    resultado, backend = _executar_com_fallback(
        orq,
        pergunta=pergunta,
        max_trechos=entrada.max_trechos,
        backend=config.BACKEND,
    )

    fontes_v1 = [
        {
            "n": int(f.get("n") or idx),
            "doc_id": f.get("doc_id") or "",
            "titulo": f.get("titulo") or "",
            "orgao": f.get("orgao") or "",
            "pagina": _pagina_int(f.get("pagina")),
            "url": f.get("url") or "",
        }
        for idx, f in enumerate(resultado.get("fontes_citadas", []), start=1)
    ]
    resposta = resultado.get("resposta") or SEM_BASE
    encontrou = bool(fontes_v1) and not resposta.strip().startswith(SEM_BASE)
    corpo = {
        "grupo": "grupo04",
        "resposta": resposta,
        "encontrou_base": encontrou,
        "fontes": fontes_v1,
        "valores_sem_fonte": resultado.get("valores_sem_fonte", []),
        "backend": backend,
        "tempo_ms": int((time.monotonic() - inicio) * 1000),
    }
    if entrada.trace or entrada.incluir_trace or trace:
        corpo["trace"] = {
            "subperguntas": resultado.get("subperguntas", []),
            "etapas": resultado.get("trace", []),
            "interacoes": resultado.get("interacoes", []),
            "degradado": resultado.get("degradado", False),
            "avisos": resultado.get("avisos", []),
        }
    return corpo
