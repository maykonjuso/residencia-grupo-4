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
_ROTULO_ALERGENICO: dict[str, str] = dict(ALERGENICOS_OFICIAIS)

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


def _dividir_preservando_anotacoes(texto: str, padrao: re.Pattern[str] | str) -> list[str]:
    """Divide ``texto`` por ``padrao`` sem quebrar anotações entre colchetes ``[Alergênicos: ...]``."""
    anotacoes: list[str] = []
    mascarado = re.sub(
        r"\[[^\]]+\]",
        lambda m: f"__ANOT_{len(anotacoes) - (anotacoes.append(m.group(0)) is not None and 0)}__",
        texto,
    )
    partes = re.split(padrao, mascarado) if isinstance(padrao, str) else padrao.split(mascarado)
    saida: list[str] = []
    for p in partes:
        for idx, anot in enumerate(anotacoes):
            p = p.replace(f"__ANOT_{idx}__", anot)
        saida.append(p)
    return saida


def _alternativas(valor: str, avisos: list[str], contexto: str) -> list[str]:
    bruto = valor.strip()
    if re.search(r"\s(ou|OU|/)\s*$", bruto):
        avisos.append(f"{contexto}: separador solto no fim de {bruto!r} — alternativa vazia ignorada")
        bruto = re.sub(r"\s(ou|OU|/)\s*$", "", bruto)
    partes = []
    for p in _dividir_preservando_anotacoes(bruto, SEPARADORES):
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
                sem_prefixo = re.sub(r"(?i)^arroz\s+", "", arroz)
                tipos = [t.strip() for t in _dividir_preservando_anotacoes(sem_prefixo, r"\s+e\s+")]
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
                else "Nenhum ícone de alergênico identificado no PDF oficial para esta refeição. Confirme na linha de distribuição."
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
    if chunks is None:
        if config.CARDAPIO_SEMANAL_JSON.exists():
            dados = json.loads(config.CARDAPIO_SEMANAL_JSON.read_text(encoding="utf-8"))
            semanais = [
                r for r in dados.get("refeicoes", [])
                if r.get("data") == data
                and (not ref or r.get("refeicao") == ref)
                and (not doc_id or (r.get("fonte") or {}).get("doc_id") == doc_id)
            ]
            if semanais:
                return semanais
        if not config.CHUNKS.exists():
            return []
        chunks = carregar_chunks_cardapio()
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


# ----------------------------------------------------------------------------- cardápio semanal (.json)

_DIAS_SEMANA_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
_RE_PAGINA = re.compile(r"\[\[PAGINA (\d+)\]\]\s*\n(## [^\n]+)")


def estruturar_semana(resultado_coleta: dict, doc_id: str = "F99") -> dict:
    """Converte a coleta semanal (`scraper.coletar`) no JSON único `cardapio_semanal.json`."""
    sem = resultado_coleta["semana"]
    texto = resultado_coleta.get("texto", "")
    blocos = re.split(r"(?=\[\[PAGINA \d+\]\])", texto)
    refeicoes: list[dict] = []
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        m = _RE_PAGINA.match(bloco)
        pagina = int(m.group(1)) if m else 1
        secao = m.group(2).lstrip("# ").strip() if m else ""
        chunk = {
            "chunk_id": f"{doc_id}-{len(refeicoes) + 1:04d}",
            "doc_id": doc_id,
            "pagina": pagina,
            "titulo": f"Cardápio semanal do RU Gama — {sem.inicio:%d/%m} a {sem.fim:%d/%m/%Y}",
            "url": sem.url,
            "secao": secao,
            "texto": bloco,
        }
        est = estruturar_chunk(chunk)
        if est["compartimentos"]:
            refeicoes.append(est)
    return {
        "unidade": "gama",
        "semana": {"inicio": sem.inicio.isoformat(), "fim": sem.fim.isoformat()},
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {
            "doc_id": doc_id,
            "url": sem.url,
            "pagina_listagem": "https://ru.unb.br/cardapio-gama/",
        },
        "alergenicos": {
            "disponivel": any(r["alergenicos"]["disponivel"] for r in refeicoes),
            "legenda": [{"id": aid, "nome": rotulo} for aid, rotulo in ALERGENICOS_OFICIAIS],
        },
        "refeicoes": refeicoes,
    }


def salvar_semana_json(
    resultado_coleta: dict,
    doc_id: str,
    destino: Path | None = None,
) -> Path:
    """Valida cada refeição no schema e grava `cardapio_semanal.json` atomicamente."""
    from .scraper import gravar_atomico

    destino = destino or config.CARDAPIO_SEMANAL_JSON
    dados = estruturar_semana(resultado_coleta, doc_id=doc_id)
    for refeicao in dados["refeicoes"]:
        validar(refeicao)
    gravar_atomico(destino, json.dumps(dados, ensure_ascii=False, indent=2) + "\n")
    return destino


def carregar_semana_atual(
    hoje: date | None = None,
    caminho: Path = config.CARDAPIO_SEMANAL_JSON,
) -> tuple[dict | None, str | None]:
    """Carrega `cardapio_semanal.json` e valida se a semana bate com a data atual."""
    ref = hoje or date.today()
    if not caminho.exists():
        return None, "Cardápio semanal (.json) não encontrado."
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        sem = dados.get("semana") or {}
        inicio = date.fromisoformat(sem["inicio"])
        fim = date.fromisoformat(sem["fim"])
    except Exception:
        return None, "Cardápio semanal (.json) inválido ou sem intervalo de semana."
    if not (inicio <= ref <= fim):
        return None, (
            f"Cardápio semanal desatualizado ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}) "
            f"para a data atual ({ref:%d/%m/%Y})."
        )
    return dados, None


def _datas_da_pergunta(pergunta: str, inicio: date, fim: date, hoje: date) -> set[str]:
    q = _sem_acento(pergunta)
    datas: set[str] = set()
    if re.search(r"\bhoje\b", q):
        datas.add(hoje.isoformat())
    if re.search(r"\bamanha\b", q):
        datas.add((hoje + timedelta(days=1)).isoformat())
    for idx, nome in enumerate(("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")):
        if re.search(rf"\b{nome}(?:-feira)?\b", q):
            d = inicio + timedelta(days=(idx - inicio.weekday()) % 7)
            if inicio <= d <= fim:
                datas.add(d.isoformat())
    for d_str, m_str in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", q):
        try:
            d = date(inicio.year, int(m_str), int(d_str))
            if inicio <= d <= fim:
                datas.add(d.isoformat())
        except ValueError:
            pass
    return datas


def _refeicoes_da_pergunta(pergunta: str) -> set[str]:
    q = _sem_acento(pergunta)
    refs: set[str] = set()
    if re.search(r"\b(?:cafe|desjejum)\b", q):
        refs.add("cafe")
    if re.search(r"\b(?:almoco|meio-dia)\b", q):
        refs.add("almoco")
    if re.search(r"\b(?:jantar|janta|noite)\b", q):
        refs.add("jantar")
    return refs


def _formatar_refeicao_texto(r: dict) -> str:
    d_iso = r.get("data", "")
    try:
        dt = date.fromisoformat(d_iso)
        dia_nome = _DIAS_SEMANA_PT[dt.weekday()]
        data_br = f"{dt:%d/%m/%Y}"
    except ValueError:
        dia_nome, data_br = "", d_iso
    nome_ref = REFEICOES.get(r.get("refeicao", ""), r.get("refeicao", ""))
    linhas = [f"Cardápio do RU Gama (FCTE) — {nome_ref} de {dia_nome}, {data_br}:"]
    for comp in r.get("compartimentos", []):
        for o in comp.get("opcoes", []):
            trilha = f" ({o['trilha']})" if o.get("trilha") not in (None, "todas") else ""
            nomes_alerg = [_ROTULO_ALERGENICO.get(aid, aid) for aid in o.get("alergenicos", [])]
            alerg = f" [Alergênicos: {', '.join(nomes_alerg)}]" if nomes_alerg else ""
            linhas.append(f"- {comp['titulo']}{trilha}: {o['nome']}{alerg}")
    if r.get("mesa_apoio"):
        linhas.append(f"Mesa de apoio: {', '.join(r['mesa_apoio'])}.")
    if any("a conferir" in a.lower() for a in r.get("avisos", [])):
        linhas.append("Aviso: há item(ns) com ícone de alergênico ambíguo — conferir na linha de distribuição.")
    return "\n".join(linhas)


_ORDEM_REFEICAO = {"cafe": 0, "almoco": 1, "jantar": 2}
_STOPWORDS_CARDAPIO = frozenset({
    "qual", "quais", "que", "tem", "semana", "esta", "essa", "este", "esse",
    "cardapio", "prato", "pratos", "dia", "dias", "almoco", "jantar", "cafe",
    "manha", "desjejum", "ru", "unb", "gama", "fcte", "com", "sem", "para",
    "por", "dos", "das", "nos", "nas", "uma", "uns", "umas", "hoje", "amanha",
    "segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo",
    "feira", "alimentacao", "alergenico", "alergenicos", "opcao", "opcoes",
    "servido", "servida", "servem", "vai", "ter", "possui", "contem", "existe",
    "comer", "algum", "alguma", "alguns", "algumas",
})
_SINONIMOS_EXTRA_PERGUNTA = {
    "celiac": "gluten",
    "porco": "suino",
    "castanha": "oleaginosa",
    "nozes": "oleaginosa",
    "amendoa": "oleaginosa",
}


def _alergenicos_da_pergunta(pergunta_norm: str) -> set[str]:
    ids: set[str] = set()
    for termo, aid in _SINONIMOS_ALERGENICO.items():
        if re.search(rf"\b{re.escape(termo)}\b", pergunta_norm):
            ids.add(aid)
    for prefixo, aid in _SINONIMOS_EXTRA_PERGUNTA.items():
        if re.search(rf"\b{re.escape(prefixo)}", pergunta_norm):
            ids.add(aid)
    return ids


def _ranquear_refeicoes(candidatas: list[dict], pergunta: str, ref_hoje: date) -> list[dict]:
    if len(candidatas) <= config.TOP_K:
        return candidatas
    q_norm = _sem_acento(pergunta)
    alerg_q = _alergenicos_da_pergunta(q_norm)
    tokens = [
        t for t in re.findall(r"[a-z0-9]{3,}", q_norm)
        if t not in _STOPWORDS_CARDAPIO
    ]

    pontuadas: list[tuple[int, str, int, dict]] = []
    for r in candidatas:
        alerg_r = {
            aid
            for comp in r.get("compartimentos", [])
            for o in comp.get("opcoes", [])
            for aid in o.get("alergenicos", [])
        }
        texto_r = _sem_acento(_formatar_refeicao_texto(r))
        score = 2 * len(alerg_q & alerg_r) + sum(
            1 for tok in tokens if re.search(rf"\b{re.escape(tok)}", texto_r)
        )
        pontuadas.append((
            score,
            r.get("data", ""),
            _ORDEM_REFEICAO.get(r.get("refeicao", ""), 9),
            r,
        ))

    com_match = [item for item in pontuadas if item[0] > 0]
    if com_match:
        com_match.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [item[3] for item in com_match[:config.TOP_K]]

    hoje_iso = ref_hoje.isoformat()
    pontuadas.sort(key=lambda item: (0 if item[1] >= hoje_iso else 1, item[1], item[2]))
    return [item[3] for item in pontuadas[:config.TOP_K]]


def trechos_da_semana(dados: dict, pergunta: str, hoje: date | None = None) -> list[dict]:
    """Filtra as refeições relevantes de `cardapio_semanal.json` e devolve trechos padronizados."""
    ref_hoje = hoje or date.today()
    inicio = date.fromisoformat(dados["semana"]["inicio"])
    fim = date.fromisoformat(dados["semana"]["fim"])
    datas_alvo = _datas_da_pergunta(pergunta, inicio, fim, ref_hoje)
    refs_alvo = _refeicoes_da_pergunta(pergunta)
    fonte_sem = dados.get("fonte") or {}

    candidatas = [
        r for r in dados.get("refeicoes", [])
        if (not datas_alvo or r.get("data") in datas_alvo)
        and (not refs_alvo or r.get("refeicao") in refs_alvo)
    ]
    selecionadas = _ranquear_refeicoes(candidatas, pergunta, ref_hoje)

    trechos: list[dict] = []
    for r in selecionadas:
        f = r.get("fonte") or {}
        d_iso = r.get("data", "")
        try:
            dt = date.fromisoformat(d_iso)
            secao = f"{REFEICOES.get(r['refeicao'], r['refeicao'])} · {_DIAS_SEMANA_PT[dt.weekday()]} {dt:%d/%m/%Y}"
        except ValueError:
            secao = r.get("refeicao", "")
        trechos.append({
            "chunk_id": f.get("chunk_id") or "",
            "doc_id": f.get("doc_id") or fonte_sem.get("doc_id") or "CARDAPIO",
            "titulo": f"Cardápio semanal do RU Gama ({inicio:%d/%m} a {fim:%d/%m/%Y})",
            "orgao": "UnB · Diretoria do RU",
            "pagina": f.get("pagina") or 1,
            "secao": secao,
            "url": f.get("url") or fonte_sem.get("url") or "",
            "texto": _formatar_refeicao_texto(r),
            "similaridade": 1.0,
        })
    return trechos


# ----------------------------------------------------------------------------- validação

def validar(cardapio: dict) -> None:
    """Valida contra schema_cardapio.json. Levanta jsonschema.ValidationError se inválido."""
    import jsonschema
    with open(SCHEMA, encoding="utf-8") as f:
        jsonschema.validate(cardapio, json.load(f))
