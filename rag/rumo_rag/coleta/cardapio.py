"""Cardápio estruturado por compartimento: o JSON de montagem de prato (issue #54, RF01).

Lê os chunks de cardápio (um chunk = uma refeição de um dia, gerado por
``extracao._ler_cardapio`` + ``chunking.dividir``) e transforma cada linha
"- Componente: valor" em um compartimento da bandeja com suas opções.

Decisões de parsing (resumidas em docs/entrega-4/index.md; issue #54):

- Alternativas: " OU ", " ou ", " / " e " OPÇÃO: " separam opções. "Leite integral OU
  Bebida de soja" vira 2 opções; "Alho e limão" continua 1 opção (o "e" não separa).
- "Arroz branco e integral Feijão carioca": o PDF mescla duas células. Vira dois
  compartimentos — ``arroz`` (Arroz branco, Arroz integral; max 2) e ``feijao``.
- As trilhas padrão / ovolactovegetariano / vegetariano estrito viram o campo
  ``trilha`` (padrao, ovolacto, vegano) dentro do mesmo compartimento; o resto é "todas".
- Cardápio malformado (ou solto no fim, rótulo desconhecido, célula vazia) gera
  aviso em ``avisos`` e nunca exceção: a interface precisa de algo para mostrar.
- Toda opção carrega ``fonte`` (doc_id, pagina, chunk_id): a citação é obrigatória (RF03).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import config

SCHEMA = Path(__file__).with_name("schema_cardapio.json")

REFEICOES = {"cafe": "Café da manhã", "almoco": "Almoço", "jantar": "Jantar"}

TRILHAS = {
    "padrão": "padrao", "padrao": "padrao",
    "ovolactovegetariano": "ovolacto",
    "vegetariano estrito": "vegano",
}

# rótulo do PDF (sem a trilha) -> (slot, título exibido, máximo de escolhas)
COMPARTIMENTOS = {
    "salada": ("salada", "Salada", 2),
    "molho para salada": ("molho", "Molho para salada", 1),
    "prato principal": ("principal", "Prato principal", 1),
    "guarnição": ("guarnicao", "Guarnição", 1),
    "sopa": ("sopa", "Sopa", 1),
    "torrada": ("torrada", "Torrada", 1),
    "acompanhamentos": ("acompanhamentos", "Acompanhamentos", 2),  # normalmente dividido em arroz/feijão
    "sobremesa": ("sobremesa", "Sobremesa", 1),
    "bebida (refresco de)": ("bebida", "Refresco", 1),
    "bebidas": ("bebida", "Bebida", 1),
    "panificação": ("panificacao", "Panificação", 1),
    "opção extra": ("extra", "Opção extra", 1),
    "gordura": ("gordura", "Gordura", 1),
    "complemento": ("complemento", "Complemento", 1),
    "fruta": ("fruta", "Fruta", 1),
}

SEPARADORES = re.compile(r"\s+OU\s+|\s+ou\s+|\s*/\s*|\s+OPÇÃO:\s*", re.I)
ACOMPANHAMENTOS = re.compile(r"^(?P<arroz>arroz\b.*?)\s+(?P<feijao>feij[ãa]o\b.*)$", re.I)
LINHA = re.compile(r"^-\s*(?P<rotulo>[^:]+):\s*(?P<valor>.*)$")
_TAG_ALERGENICOS = re.compile(r"\s*\[alerg[eê]nicos?\s*:\s*([^\]]+)\]\s*$", re.I)

ALERGENICOS_OFICIAIS: tuple[tuple[str, str], ...] = (
    ("cogumelo", "Cogumelo"),
    ("leite", "Leite e derivados"),
    ("mel", "Mel"),
    ("pimenta", "Pimenta"),
    ("soja", "Soja"),
    ("gluten", "Trigo/Glúten"),
    ("amendoim", "Amendoim"),
    ("oleaginosa", "Oleaginosa"),
    ("ovo", "Ovo"),
    ("suino", "Suíno"),
)

_SINONIMOS_ALERGENICO: dict[str, str] = {
    "cogumelo": "cogumelo",
    "cogumelos": "cogumelo",
    "leite": "leite",
    "leite e derivados": "leite",
    "lactose": "leite",
    "mel": "mel",
    "pimenta": "pimenta",
    "soja": "soja",
    "gluten": "gluten",
    "trigo": "gluten",
    "trigo/gluten": "gluten",
    "amendoim": "amendoim",
    "oleaginosa": "oleaginosa",
    "oleaginosas": "oleaginosa",
    "ovo": "ovo",
    "ovos": "ovo",
    "suino": "suino",
    "carne suina": "suino",
}


# ----------------------------------------------------------------------------- utilidades

def slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "item"


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def normalizar_refeicao(valor: str) -> str:
    v = _sem_acento(valor).replace(" ", "_")
    if v.startswith("cafe"):
        return "cafe"
    if v.startswith("almoco"):
        return "almoco"
    if v.startswith("jantar"):
        return "jantar"
    raise ValueError(f"refeição desconhecida: {valor!r} (use cafe, almoco ou jantar)")


def _separar_trilha(rotulo: str) -> tuple[str, str]:
    """'Prato principal ovolactovegetariano' -> ('prato principal', 'ovolacto')."""
    r = rotulo.strip().lower()
    for chave, trilha in TRILHAS.items():
        if r.endswith(" " + chave):
            return r[: -len(chave) - 1].strip(), trilha
    r = re.sub(r"\s+\d+$", "", r)   # "salada 1" -> "salada"
    return r, "todas"


def _alternativas(valor: str, avisos: list[str], contexto: str) -> list[str]:
    bruto = valor.strip()
    if re.search(r"\s(ou|OU|/)\s*$", bruto):
        avisos.append(f"{contexto}: separador solto no fim de {bruto!r} — alternativa vazia ignorada")
        bruto = re.sub(r"\s(ou|OU|/)\s*$", "", bruto)
    # Protege anotações "[Alergênicos: Trigo/Glúten]" para que "/" dentro dos colchetes não divida a opção
    anotacoes: list[str] = []
    mascarado = re.sub(
        r"\[[^\]]+\]",
        lambda m: f"__ANOT_{len(anotacoes) - (anotacoes.append(m.group(0)) is not None and 0)}__",
        bruto,
    )
    partes = []
    for p in SEPARADORES.split(mascarado):
        for idx, anot in enumerate(anotacoes):
            p = p.replace(f"__ANOT_{idx}__", anot)
        p = p.strip(" .;,")
        if p:
            partes.append(p)
    if not partes:
        avisos.append(f"{contexto}: célula vazia")
    return partes


def _mesa_apoio(texto: str) -> list[str]:
    m = re.search(r"Mesa de apoio:\s*(.*?)\.(?:\s|$)", texto)
    if not m:
        return []
    itens = re.split(r",\s*|\s+e\s+", m.group(1))
    return [i.strip() for i in itens if i.strip()]


def _extrair_alergenicos(nome: str, avisos: list[str], contexto: str) -> tuple[str, list[str]]:
    """Extrai anotação opcional '[Alergênicos: ...]' mantendo o nome limpo."""
    m = _TAG_ALERGENICOS.search(nome)
    if not m:
        return nome, []
    limpo = nome[: m.start()].strip()
    ids: list[str] = []
    for bruto in re.split(r"[,;]+", m.group(1)):
        chave = _sem_acento(bruto).strip()
        if not chave:
            continue
        aid = _SINONIMOS_ALERGENICO.get(chave)
        if not aid:
            avisos.append(f"{contexto}: alergênico desconhecido {bruto.strip()!r} ignorado")
            continue
        if aid not in ids:
            ids.append(aid)
    return limpo, ids


# ----------------------------------------------------------------------------- parser

def estruturar_chunk(chunk: dict) -> dict:
    """Transforma um chunk de cardápio (uma refeição de um dia) no esquema de montagem."""
    avisos: list[str] = []
    secao = chunk.get("secao") or chunk["texto"].splitlines()[0].lstrip("# ")
    m = re.match(r"(?P<ref>.+?)\s*·\s*\S+\s+(?P<data>\d{2}/\d{2}/\d{4})", secao)
    if m:
        refeicao = normalizar_refeicao(m.group("ref"))
        data_iso = datetime.strptime(m.group("data"), "%d/%m/%Y").date().isoformat()
    else:
        avisos.append(f"seção sem refeição/data reconhecível: {secao!r}")
        refeicao, data_iso = "almoco", chunk.get("data", "")

    fonte_opcao = {"doc_id": chunk["doc_id"], "pagina": chunk.get("pagina"), "chunk_id": chunk["chunk_id"]}
    compartimentos: dict[str, dict] = {}

    def opcao(slot: str, nome: str, trilha: str, contexto: str = ""):
        nome_limpo, alergenicos = _extrair_alergenicos(nome, avisos, contexto or chunk["chunk_id"])
        comp = compartimentos[slot]
        base = slug(nome_limpo)
        ids = {o["id"] for o in comp["opcoes"]}
        oid, n = base, 2
        while oid in ids:
            oid, n = f"{base}-{n}", n + 1
        comp["opcoes"].append({
            "id": oid,
            "nome": nome_limpo,
            "trilha": trilha,
            "alergenicos": alergenicos,
            "fonte": dict(fonte_opcao),
        })

    def garantir(slot: str, titulo: str, maximo: int):
        compartimentos.setdefault(slot, {"slot": slot, "titulo": titulo, "max": maximo, "opcoes": []})

    for linha in chunk["texto"].splitlines():
        lm = LINHA.match(linha.strip())
        if not lm:
            continue
        rotulo, valor = lm.group("rotulo").strip(), lm.group("valor").strip()
        base, trilha = _separar_trilha(rotulo)
        contexto = f"{chunk['chunk_id']} · {rotulo}"

        if base == "acompanhamentos":
            am = ACOMPANHAMENTOS.match(valor)
            if am:
                arroz = am.group("arroz")
                tipos = [t.strip() for t in re.split(r"\s+e\s+", re.sub(r"(?i)^arroz\s+", "", arroz))]
                garantir("arroz", "Arroz", 2)
                for t in tipos:
                    if t:
                        opcao("arroz", f"Arroz {t.lower()}", trilha)
                garantir("feijao", "Feijão", 1)
                for f in _alternativas(am.group("feijao"), avisos, contexto):
                    opcao("feijao", f, trilha)
                continue
            avisos.append(f"{contexto}: acompanhamento fora do padrão 'Arroz … Feijão …', mantido inteiro")

        if base in COMPARTIMENTOS:
            slot, titulo, maximo = COMPARTIMENTOS[base]
        else:
            slot, titulo, maximo = slug(base).replace("-", "_"), rotulo.strip(), 1
            avisos.append(f"{contexto}: rótulo desconhecido, compartimento genérico '{slot}' criado")
        garantir(slot, titulo, maximo)
        for nome in _alternativas(valor, avisos, contexto):
            opcao(slot, nome, trilha)

    vazios = [s for s, c in compartimentos.items() if not c["opcoes"]]
    for s in vazios:
        avisos.append(f"{chunk['chunk_id']}: compartimento '{s}' sem opções, removido")
        del compartimentos[s]
    if not compartimentos:
        avisos.append(f"{chunk['chunk_id']}: nenhuma linha de cardápio reconhecida")

    unidade = "gama" if "gama" in (chunk.get("titulo", "") + chunk["texto"]).lower() else "desconhecida"
    tem_alergenicos = any(
        o["alergenicos"]
        for c in compartimentos.values()
        for o in c["opcoes"]
    )
    return {
        "unidade": unidade,
        "data": data_iso,
        "refeicao": refeicao,
        "compartimentos": list(compartimentos.values()),
        "mesa_apoio": _mesa_apoio(chunk["texto"]),
        "alergenicos": {
            "disponivel": tem_alergenicos,
            "legenda": [{"id": aid, "nome": rotulo} for aid, rotulo in ALERGENICOS_OFICIAIS],
            "observacao": (
                ""
                if tem_alergenicos
                else "Notações de alergênicos por prato no PDF oficial são ícones (imagens) não extraídos como texto."
            ),
        },
        "fonte": {"doc_id": chunk["doc_id"], "pagina": chunk.get("pagina"),
                  "chunk_id": chunk["chunk_id"], "url": chunk.get("url", "")},
        "avisos": avisos,
    }


# ----------------------------------------------------------------------------- consulta

def carregar_chunks_cardapio(caminho: Path = config.CHUNKS) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [c for c in map(json.loads, f) if c.get("tipo") == "cardapio"]


def _data_do_chunk(chunk: dict) -> str | None:
    m = re.search(r"(\d{2}/\d{2}/\d{4})", chunk.get("secao", ""))
    return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat() if m else None


def buscar(data: str, refeicao: str | None = None, doc_id: str | None = None,
           chunks: list[dict] | None = None) -> list[dict]:
    """Cardápios estruturados da data (e refeição, se dada). Lista vazia se não houver."""
    date.fromisoformat(data)  # valida o formato AAAA-MM-DD
    ref = normalizar_refeicao(refeicao) if refeicao else None
    chunks = carregar_chunks_cardapio() if chunks is None else chunks
    saida = []
    for c in chunks:
        if doc_id and c["doc_id"] != doc_id:
            continue
        if _data_do_chunk(c) != data:
            continue
        if ref and not _sem_acento(c.get("secao", "")).startswith(_sem_acento(REFEICOES[ref])):
            continue
        saida.append(estruturar_chunk(c))
    return saida


def semana(inicio: str) -> list[str]:
    d = date.fromisoformat(inicio)
    return [(d + timedelta(days=i)).isoformat() for i in range(7)]


# ----------------------------------------------------------------------------- validação

def validar(cardapio: dict) -> None:
    """Valida contra schema_cardapio.json. Levanta jsonschema.ValidationError se inválido."""
    import jsonschema
    with open(SCHEMA, encoding="utf-8") as f:
        jsonschema.validate(cardapio, json.load(f))
