"""Linha de comando do RUmo.

  python -m rumo_rag ingerir            # baixa, extrai, divide, gera embeddings e indexa
  python -m rumo_rag perguntar "..."    # consulta com resposta e fontes
  python -m rumo_rag avaliar            # métricas de recuperação no conjunto de teste
  python -m rumo_rag demo               # roda as perguntas da demonstração e salva as evidências
"""
import argparse
import json
import sys
import time

from . import chunking, config, extracao, geracao, indice


def ingerir(_args):
    t0 = time.time()
    docs = extracao.carregar_catalogo()
    extracao.baixar(docs)
    textos = extracao.extrair_todos(docs)
    chunks = []
    for d in docs:
        chunks.extend(chunking.dividir(d, textos[d["id"]]))
    tamanhos = sorted(len(c["texto"]) for c in chunks)
    print(f"{len(docs)} documentos → {len(chunks)} chunks · mediana {tamanhos[len(tamanhos)//2]} caracteres")
    indice.indexar(chunks)
    print(f"ingestão concluída em {time.time() - t0:.0f}s")


def responder(pergunta: str, backend: str, eixo: str | None = None, k: int = config.TOP_K, sem_rag: bool = False) -> dict:
    if sem_rag:
        t0 = time.time()
        resposta = geracao.gerar_sem_rag(pergunta, backend=backend)
        t1 = time.time()
        return {
            "pergunta": pergunta,
            "subperguntas": [],
            "resposta": resposta,
            "fontes_citadas": [],
            "valores_sem_fonte": [],
            "sem_citacao": False,
            "trechos_recuperados": [],
            "tempo_decomposicao_s": 0.0,
            "tempo_busca_s": 0.0,
            "tempo_geracao_s": round(t1 - t0, 2),
            "backend": backend,
        }
    t0 = time.time()
    subperguntas = indice.decompor(pergunta, backend=backend if backend in ("ollama", "hf") else "auto")
    t1 = time.time()
    trechos = indice.buscar_com_subperguntas(pergunta, subperguntas, k=k, eixo=eixo)
    t2 = time.time()
    resposta = geracao.gerar(pergunta, trechos, backend)
    t3 = time.time()
    return {
        "pergunta": pergunta,
        "subperguntas": subperguntas,
        "resposta": resposta,
        "fontes_citadas": geracao.citacoes_usadas(resposta, trechos),
        "valores_sem_fonte": geracao.valores_sem_fonte(resposta, trechos),
        "sem_citacao": geracao.resposta_sem_citacao(resposta, trechos),   # RN-02
        "trechos_recuperados": [
            {k2: t.get(k2) for k2 in ("chunk_id", "doc_id", "titulo", "pagina", "secao", "similaridade", "nota_rrf", "url", "texto")}
            for t in trechos],
        "tempo_decomposicao_s": round(t1 - t0, 3),
        "tempo_busca_s": round(t2 - t1, 2),
        "tempo_geracao_s": round(t3 - t2, 2),
        "backend": backend,
    }


def imprimir(r: dict, sem_rag: bool = False):
    print(f"\nPergunta: {r['pergunta']}\n")
    if sem_rag or r.get("sem_rag"):
        print("Modo: Sem RAG (LLM puro)")
        print(f"\nResposta ({r['backend']}):\n{r['resposta']}\n")
        print(f"(geração {r['tempo_geracao_s']}s)")
        return
    if r.get("subperguntas"):
        print("Subperguntas (decomposição):")
        for s in r["subperguntas"]:
            print(f"  - {s}")
        print()
    print("Trechos recuperados:")
    for i, t in enumerate(r["trechos_recuperados"], start=1):
        sim = f" · sim {t['similaridade']}" if t.get("similaridade") is not None else ""
        print(f"  [{i}] {t['chunk_id']} · {t['titulo'][:60]} · p.{t['pagina']}{sim}")
    print(f"\nResposta ({r['backend']}):\n{r['resposta']}\n")
    print("Fontes citadas:")
    for f in r["fontes_citadas"]:
        print(f"  [{f['n']}] {f['doc_id']} · {f['titulo']} · p.{f['pagina']} · {f['url']}")
    if r.get("sem_citacao"):
        print("\n⚠ ALERTA (RN-02): a resposta não cita nenhum trecho; trate como não verificada")
    if r.get("valores_sem_fonte"):
        print(f"\n⚠ ALERTA: valores na resposta que não aparecem nas fontes: {', '.join(r['valores_sem_fonte'])}")
    print(f"\n(busca {r['tempo_busca_s']}s · geração {r['tempo_geracao_s']}s)")


def perguntar(args):
    sem_rag = getattr(args, "sem_rag", False)
    r = responder(" ".join(args.pergunta), args.backend, args.eixo, args.k, sem_rag=sem_rag)
    if getattr(args, "saida", "texto") == "json":
        saida_dict = dict(r)
        saida_dict["sem_rag"] = sem_rag
        print(json.dumps(saida_dict, ensure_ascii=False, indent=2))
    else:
        imprimir(r, sem_rag=sem_rag)


def avaliar(args):
    casos = [json.loads(l) for l in open(config.AVALIACAO / "perguntas_ouro.jsonl", encoding="utf-8")]
    linhas = []
    for modo in ("bm25", "denso", "hibrido"):
        hit1 = hitk = rr = 0.0
        detalhes = []
        for c in casos:
            res = indice.buscar(c["pergunta"], k=args.k, modo=modo)
            docs = [r["doc_id"] for r in res]
            pos = next((i for i, d in enumerate(docs) if d in c["docs_esperados"]), None)
            hit1 += pos == 0
            hitk += pos is not None
            rr += 1 / (pos + 1) if pos is not None else 0
            detalhes.append({"id": c["id"], "pos": pos, "top": docs})
        n = len(casos)
        linhas.append({"modo": modo, "n": n, "hit@1": round(hit1 / n, 3), f"hit@{args.k}": round(hitk / n, 3),
                       "mrr": round(rr / n, 3), "detalhes": detalhes})
        print(f"{modo:8s} hit@1={hit1/n:.3f} hit@{args.k}={hitk/n:.3f} MRR={rr/n:.3f} (n={n})")
    (config.AVALIACAO / "resultado_recuperacao.json").write_text(
        json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")


def demo(args):
    perguntas = [json.loads(l) for l in open(config.AVALIACAO / "perguntas_demo.jsonl", encoding="utf-8")]
    saidas = []
    for p in perguntas:
        r = responder(p["pergunta"], args.backend)
        r["id"] = p["id"]
        r["rotulo"] = p.get("rotulo", "")
        imprimir(r)
        saidas.append(r)
    destino = config.AVALIACAO / "demo_respostas.json"
    destino.write_text(json.dumps(saidas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nevidências salvas em {destino}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rumo_rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingerir").set_defaults(f=ingerir)
    p = sub.add_parser("perguntar")
    p.add_argument("pergunta", nargs="+")
    p.add_argument("--backend", default=config.BACKEND, choices=["hf", "ollama", "openai", "extrativo"])
    p.add_argument("--eixo", choices=["ru", "fluxo", "apoio"])
    p.add_argument("-k", type=int, default=config.TOP_K)
    p.add_argument("--sem-rag", action="store_true", help="Executa apenas com LLM puro, sem busca ou recuperação na base")
    p.add_argument("--saida", choices=["texto", "json"], default="texto", help="Formato de saída (texto ou json)")
    p.set_defaults(f=perguntar)
    a = sub.add_parser("avaliar")
    a.add_argument("-k", type=int, default=config.TOP_K)
    a.set_defaults(f=avaliar)
    d = sub.add_parser("demo")
    d.add_argument("--backend", default=config.BACKEND, choices=["hf", "ollama", "openai", "extrativo"])
    d.set_defaults(f=demo)
    args = ap.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    sys.exit(main())
