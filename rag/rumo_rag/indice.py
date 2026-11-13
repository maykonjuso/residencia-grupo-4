"""Etapas 4 e 5 da ingestão (embeddings + banco vetorial) e a busca híbrida."""
import json
import re
from functools import lru_cache

from rank_bm25 import BM25Okapi

from . import config

STOPWORDS = set("""a o as os de da do das dos e é em no na nos nas um uma para por com que se ao à
às como mais ou qual quais quando onde ser sua seu meu minha eu tem há""".split())


TOKEN = re.compile(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|[a-z]{2,4}\d{3,4}|[a-z0-9à-ú]+")


def tokenizar(t: str) -> list[str]:
    """Datas (11/11/2026) e códigos de disciplina (FGA0314) viram um termo só:
    são exatamente o que a busca vetorial tem dificuldade de distinguir."""
    toks = []
    for w in TOKEN.findall(t.lower()):
        if w in STOPWORDS:
            continue
        if "/" in w:                       # normaliza 11/11/2026 e 11/11 para o mesmo termo extra
            partes = w.split("/")
            toks.append(f"{int(partes[0]):02d}/{int(partes[1]):02d}")
        toks.append(w)
    return toks


GATILHOS = r"(?:quanto|quanta|qual|quais|como|quando|onde|que horas|até que|o que|posso|preciso)"


def decompor(pergunta: str) -> list[str]:
    """Quebra perguntas compostas ("Quanto pago ... e até que horas ...?") em subperguntas."""
    partes = re.split(rf"[?!.;]\s+|,?\s+e\s+(?={GATILHOS}\b)", pergunta.strip(), flags=re.I)
    partes = [p.strip(" ?.") for p in partes if len(tokenizar(p)) >= 3]
    # frases sem palavra interrogativa ("Sou estudante de graduação...") são contexto:
    # vão junto de cada subpergunta em vez de virar uma busca própria
    eh_pergunta = re.compile(rf"\b{GATILHOS}\b", re.I)
    contexto = " ".join(p for p in partes if not eh_pergunta.search(p))
    perguntas = [p for p in partes if eh_pergunta.search(p)]
    if len(perguntas) < 2:
        return []
    return [f"{contexto}. {p}" if contexto else p for p in perguntas]


@lru_cache(maxsize=1)
def modelo_embedding():
    import torch
    from sentence_transformers import SentenceTransformer
    # fp16 na GPU: metade da memória (bge-m3 ~1,1 GB), sobra espaço para o LLM de 7B na mesma placa de 8 GB
    kw = {"model_kwargs": {"dtype": torch.float16}} if torch.cuda.is_available() else {}
    return SentenceTransformer(config.MODELO_EMBEDDING, **kw)


def embed_passagens(textos: list[str]):
    pre = "passage: " if config.PREFIXOS_E5 else ""
    return modelo_embedding().encode([pre + t for t in textos], batch_size=16,
                                     normalize_embeddings=True, show_progress_bar=True)


def embed_consulta(q: str):
    pre = "query: " if config.PREFIXOS_E5 else ""
    return modelo_embedding().encode([pre + q], normalize_embeddings=True)[0]


def colecao(recriar: bool = False):
    import chromadb  # só a busca densa precisa; o modo bm25 roda sem chromadb/torch
    cliente = chromadb.PersistentClient(path=str(config.CHROMA))
    if recriar:
        try:
            cliente.delete_collection(config.COLECAO)
        except Exception:
            pass
    return cliente.get_or_create_collection(config.COLECAO, metadata={"hnsw:space": "cosine"})


def indexar(chunks: list[dict]) -> None:
    with open(config.CHUNKS, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    vetores = embed_passagens([c["texto_indexado"] for c in chunks])
    col = colecao(recriar=True)
    campos = ("doc_id", "titulo", "orgao", "eixo", "curso", "tipo", "url", "data", "pagina", "secao")
    for i in range(0, len(chunks), 500):
        lote = chunks[i:i + 500]
        col.add(ids=[c["chunk_id"] for c in lote],
                embeddings=[v.tolist() for v in vetores[i:i + 500]],
                documents=[c["texto"] for c in lote],
                metadatas=[{k: c[k] for k in campos} for c in lote])
    print(f"{col.count()} chunks indexados em {config.CHROMA}")


@lru_cache(maxsize=1)
def _bm25():
    chunks = [json.loads(l) for l in open(config.CHUNKS, encoding="utf-8")]
    return chunks, BM25Okapi([tokenizar(c["texto_indexado"]) for c in chunks])


def buscar(pergunta: str, k: int = config.TOP_K, modo: str = "hibrido", eixo: str | None = None,
           decompor_pergunta: bool = True) -> list[dict]:
    """modo: denso | bm25 | hibrido (RRF dos dois).
    Perguntas compostas são buscadas inteiras e também por subpergunta; tudo entra na fusão."""
    chunks, bm25 = _bm25()
    por_id = {c["chunk_id"]: c for c in chunks}
    rankings: list[list[str]] = []
    distancias: dict[str, float] = {}
    subperguntas = decompor(pergunta) if decompor_pergunta else []
    consultas = [pergunta] + subperguntas
    pesos: list[float] = []
    # cada subpergunta ganha uma vaga a mais no contexto (até MAX_TRECHOS)
    k = min(k + len(subperguntas), config.MAX_TRECHOS) if subperguntas else k

    for q in consultas:
        # datas e códigos são identificadores exatos: o embedding quase não os distingue
        # (todos os dias do cardápio ficam com a mesma similaridade), o BM25 sim.
        tem_identificador = bool(re.search(r"\d{1,2}/\d{1,2}|\b[a-z]{2,4}\d{3,4}\b", q.lower()))
        if modo in ("denso", "hibrido"):
            filtro = {"eixo": eixo} if eixo else None
            r = colecao().query(query_embeddings=[embed_consulta(q).tolist()],
                                n_results=config.CANDIDATOS, where=filtro)
            rankings.append(r["ids"][0]); pesos.append(1.0)
            for cid, dist in zip(r["ids"][0], r["distances"][0]):
                distancias[cid] = min(dist, distancias.get(cid, 2.0))

        if modo in ("bm25", "hibrido"):
            notas = bm25.get_scores(tokenizar(q))
            ordem = sorted(range(len(chunks)), key=lambda i: -notas[i])
            ids = [chunks[i]["chunk_id"] for i in ordem if not eixo or chunks[i]["eixo"] == eixo]
            rankings.append(ids[:config.CANDIDATOS])
            pesos.append(config.PESO_BM25_IDENTIFICADOR if tem_identificador else 1.0)

    fusao: dict[str, float] = {}
    for ranking, peso in zip(rankings, pesos):
        for pos, cid in enumerate(ranking):
            fusao[cid] = fusao.get(cid, 0.0) + peso / (config.RRF_K + pos + 1)

    resultado = []
    for cid, nota in sorted(fusao.items(), key=lambda x: -x[1])[:k]:
        c = dict(por_id[cid])
        c["nota_rrf"] = round(nota, 5)
        if cid in distancias:
            c["similaridade"] = round(1 - distancias[cid], 4)
        resultado.append(c)
    return resultado
