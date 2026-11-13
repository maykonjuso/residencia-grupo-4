"""Linha de comando do RUmo.

  python -m rumo_rag ingerir            # baixa, extrai, divide, gera embeddings e indexa
  python -m rumo_rag perguntar "..."    # consulta com resposta e fontes
  python -m rumo_rag perguntar --sem-rag "..."   # mesmo LLM e mesma persona, sem trechos (#17)
  python -m rumo_rag avaliar            # métricas de recuperação no conjunto de teste
  python -m rumo_rag demo               # roda as perguntas da demonstração e salva as evidências
  python -m rumo_rag comparar           # perguntas-ouro com e sem RAG, respostas pareadas (#17, #28)
"""
import argparse
import json
import sys
import time
from datetime import datetime

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


def responder(pergunta: str, backend: str, eixo: str | None = None, k: int = config.TOP_K,
              com_rag: bool = True) -> dict:
    t0 = time.time()
    # sem RAG (#17): nem consulta o índice; o LLM recebe só a pergunta
    trechos = indice.buscar(pergunta, k=k, eixo=eixo) if com_rag else []
    t1 = time.time()
    resposta = geracao.gerar(pergunta, trechos, backend, com_rag=com_rag)
    t2 = time.time()
    return {
        "pergunta": pergunta,
        "modo": "com_rag" if com_rag else "sem_rag",
        "resposta": resposta,
        "recusou": geracao.eh_recusa(resposta),                           # RN-03
        "fontes_citadas": geracao.citacoes_usadas(resposta, trechos),
        "valores_sem_fonte": geracao.valores_sem_fonte(resposta, trechos),
        "sem_citacao": geracao.resposta_sem_citacao(resposta, trechos) if com_rag else None,   # RN-02
        "trechos_recuperados": [
            {k2: t.get(k2) for k2 in ("chunk_id", "doc_id", "titulo", "pagina", "secao", "similaridade", "nota_rrf", "url", "texto")}
            for t in trechos],
        "tempo_busca_s": round(t1 - t0, 2),
        "tempo_geracao_s": round(t2 - t1, 2),
        "backend": backend,
    }


def imprimir(r: dict):
    print(f"\nPergunta: {r['pergunta']}\n")
    if r.get("modo") == "sem_rag":
        print(f"Resposta SEM RAG ({r['backend']}, sem trechos recuperados):\n{r['resposta']}\n")
        print(f"(geração {r['tempo_geracao_s']}s)")
        return
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
    imprimir(responder(" ".join(args.pergunta), args.backend, args.eixo, args.k, com_rag=not args.sem_rag))


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


def _ler_jsonl(caminho):
    return [json.loads(l) for l in open(caminho, encoding="utf-8") if l.strip()]


def comparar(args):
    """#17/#28: mesmas perguntas, mesmo LLM, mesmo backend; muda só a presença dos trechos.
    Grava rag/avaliacao/respostas_comparativas.json com as respostas pareadas."""
    if args.backend == "extrativo":
        sys.exit("comparar precisa de um LLM: use --backend hf (padrão), ollama ou openai")
    casos = _ler_jsonl(config.AVALIACAO / "perguntas_ouro.jsonl")
    if not args.sem_fora_da_base:
        casos += _ler_jsonl(config.AVALIACAO / "perguntas_fora_da_base.jsonl")
    if args.ids:
        filtro = set(args.ids.split(","))
        casos = [c for c in casos if c["id"] in filtro]

    pares = []
    for i, c in enumerate(casos, start=1):
        print(f"[{i}/{len(casos)}] {c['id']} · {c['pergunta']}")
        com = responder(c["pergunta"], args.backend, k=args.k, com_rag=True)
        sem = responder(c["pergunta"], args.backend, k=args.k, com_rag=False)
        # Sem RAG não há fonte nenhuma, então "valor sem fonte" seria todo valor da resposta.
        # Para ficar comparável, auditamos os valores contra os trechos que a base devolve para
        # a mesma pergunta: valor que não aparece ali é valor que a base oficial não sustenta.
        sem["valores_sem_fonte"] = geracao.valores_sem_fonte(sem["resposta"], com["trechos_recuperados"])
        docs_recuperados = [t["doc_id"] for t in com["trechos_recuperados"]]
        pares.append({
            "id": c["id"], "eixo": c["eixo"], "categoria": c.get("categoria", ""),
            "pergunta": c["pergunta"], "docs_esperados": c["docs_esperados"],
            "sem_rag": {k2: sem[k2] for k2 in ("resposta", "recusou", "valores_sem_fonte",
                                               "tempo_busca_s", "tempo_geracao_s")},
            "com_rag": {
                **{k2: com[k2] for k2 in ("resposta", "recusou", "valores_sem_fonte", "sem_citacao",
                                          "fontes_citadas", "tempo_busca_s", "tempo_geracao_s")},
                "docs_recuperados": docs_recuperados,
                "doc_esperado_recuperado": any(d in c["docs_esperados"] for d in docs_recuperados),
            },
        })

    modelo = {"hf": config.MODELO_HF + (" · 4 bits" if config.HF_4BIT else ""),
              "ollama": config.MODELO_OLLAMA, "openai": config.OPENAI_MODEL}[args.backend]
    saida = {
        "meta": {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "backend": args.backend, "modelo": modelo,
            "embedding": config.MODELO_EMBEDDING, "top_k": args.k,
            "decodificacao": "greedy (do_sample=False)" if args.backend == "hf" else "temperature=0",
            "prompt_com_rag": geracao.INSTRUCOES, "prompt_sem_rag": geracao.INSTRUCOES_SEM_RAG,
            "n": len(pares),
        },
        "respostas": pares,
    }
    destino = config.AVALIACAO / args.saida
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(pares) or 1
    print(f"\n{len(pares)} perguntas · recusas sem RAG {sum(p['sem_rag']['recusou'] for p in pares)}"
          f" · com RAG {sum(p['com_rag']['recusou'] for p in pares)}")
    print(f"respostas com valor sem fonte: sem RAG {sum(bool(p['sem_rag']['valores_sem_fonte']) for p in pares)}"
          f" · com RAG {sum(bool(p['com_rag']['valores_sem_fonte']) for p in pares)}")
    print(f"tempo médio de geração: sem RAG {sum(p['sem_rag']['tempo_geracao_s'] for p in pares)/n:.1f}s"
          f" · com RAG {sum(p['com_rag']['tempo_geracao_s'] for p in pares)/n:.1f}s")
    print(f"respostas pareadas salvas em {destino}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rumo_rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingerir").set_defaults(f=ingerir)
    p = sub.add_parser("perguntar")
    p.add_argument("pergunta", nargs="+")
    p.add_argument("--backend", default=config.BACKEND, choices=["hf", "ollama", "openai", "extrativo"])
    p.add_argument("--eixo", choices=["ru", "fluxo", "apoio"])
    p.add_argument("-k", type=int, default=config.TOP_K)
    p.add_argument("--sem-rag", action="store_true",
                   help="mesmo LLM e mesma persona, sem trechos recuperados (linha de base da Entrega 3)")
    p.set_defaults(f=perguntar)
    a = sub.add_parser("avaliar")
    a.add_argument("-k", type=int, default=config.TOP_K)
    a.set_defaults(f=avaliar)
    d = sub.add_parser("demo")
    d.add_argument("--backend", default=config.BACKEND, choices=["hf", "ollama", "openai", "extrativo"])
    d.set_defaults(f=demo)
    c = sub.add_parser("comparar")
    c.add_argument("--backend", default=config.BACKEND, choices=["hf", "ollama", "openai", "extrativo"])
    c.add_argument("-k", type=int, default=config.TOP_K)
    c.add_argument("--ids", help="roda só estas perguntas, ex.: Q01,Q14,X01 (teste rápido)")
    c.add_argument("--sem-fora-da-base", action="store_true", help="não inclui perguntas_fora_da_base.jsonl")
    c.add_argument("--saida", default="respostas_comparativas.json")
    c.set_defaults(f=comparar)
    args = ap.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    sys.exit(main())
