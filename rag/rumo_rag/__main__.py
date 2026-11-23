"""Linha de comando do RUmo.

  python -m rumo_rag ingerir            # baixa, extrai, divide, gera embeddings e indexa
  python -m rumo_rag perguntar "..."    # consulta com resposta e fontes
  python -m rumo_rag "..." --agentes --trace  # orquestrador multiagentes em paralelo
  python -m rumo_rag avaliar            # métricas de recuperação no conjunto de teste
  python -m rumo_rag demo               # roda as perguntas da demonstração e salva as evidências
"""
import argparse
import json
import sys
import time

from . import agentes, chunking, config, extracao, geracao, indice


def ingerir(_args):
    t0 = time.time()
    docs = [d for d in extracao.carregar_catalogo() if d.get("tipo") != "cardapio"]
    extracao.baixar(docs)
    textos = extracao.extrair_todos(docs)
    chunks = []
    for d in docs:
        chunks.extend(chunking.dividir(d, textos[d["id"]]))
    tamanhos = sorted(len(c["texto"]) for c in chunks)
    print(f"{len(docs)} documentos → {len(chunks)} chunks · mediana {tamanhos[len(tamanhos)//2]} caracteres")
    indice.indexar(chunks)
    print(f"ingestão concluída em {time.time() - t0:.0f}s")


def responder(
    pergunta: str,
    backend: str,
    eixo: str | None = None,
    k: int = config.TOP_K,
    sem_rag: bool = False,
    usar_agentes: bool = False,
    falhar_agente: str | None = None,
    data: str | None = None,
    perfil: dict | None = None,
    curso: str | None = None,
    curriculo_id: str | None = None,
    vigencia: str | None = None,
) -> dict:
    if usar_agentes:
        return agentes.Orquestrador().executar(
            pergunta,
            backend=backend,
            k=k,
            falhar_agente=falhar_agente,
            data=data,
            perfil=perfil,
            curso=curso,
            curriculo_id=curriculo_id,
            vigencia=vigencia,
        )
    # Consultas curriculares suportadas pelo grafo são resolvidas pelo algoritmo
    # mesmo no modo CLI padrão (os comandos da task não exigem --agentes).
    ctx_grafo = {"backend": backend}
    if curso:
        ctx_grafo["curso"] = curso
    if curriculo_id:
        ctx_grafo["curriculo_id"] = curriculo_id
    if vigencia:
        ctx_grafo["vigencia"] = vigencia
    mensagem_grafo = agentes.Mensagem(
        remetente="CLI",
        destinatario="Agente Fluxo",
        conteudo=pergunta,
        contexto=ctx_grafo,
    )
    resposta_grafo = agentes.AgenteFluxo(k=k, modo=config.BUSCA).responder_grafo(mensagem_grafo)
    if resposta_grafo is not None:
        trechos = mensagem_grafo.contexto.get("trechos_recuperados", [])
        return {
            "pergunta": pergunta,
            "subperguntas": [],
            "resposta": resposta_grafo.conteudo,
            "fontes_citadas": [
                {"n": i, **fonte} for i, fonte in enumerate(resposta_grafo.fontes, start=1)
            ],
            "valores_sem_fonte": [],
            "sem_citacao": False,
            "trechos_recuperados": [
                {
                    chave: trecho.get(chave)
                    for chave in (
                        "chunk_id", "doc_id", "titulo", "pagina", "secao",
                        "similaridade", "url", "texto",
                    )
                }
                for trecho in trechos
            ],
            "tempo_decomposicao_s": 0.0,
            "tempo_busca_s": mensagem_grafo.contexto.get("tempo_busca_s", 0.0),
            "tempo_geracao_s": mensagem_grafo.contexto.get("tempo_geracao_s", 0.0),
            "backend": "grafo",
        }
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
    subperguntas = indice.decompor(
        pergunta,
        backend=backend if backend in ("ollama", "hf", "openai") else "auto",
    )
    t1 = time.time()
    trechos = indice.buscar_com_subperguntas(pergunta, subperguntas, k=k, modo=config.BUSCA, eixo=eixo)
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


def imprimir_agentes(r: dict, mostrar_trace: bool = False):
    print(f"\nPergunta: {r['pergunta']}\n")
    if mostrar_trace:
        print("=== [TRACE · Orquestrador Multiagentes] ===")
        for passo in r.get("trace", []):
            etapa = passo.get("etapa")
            if etapa == "classificacao_decomposicao":
                print(
                    f"1. Classificação/Decomposição: composta={passo['eh_composta']} "
                    f"(p={passo['prob_composta']}, limiar={passo['limiar']}, {passo['tempo_s']}s)"
                )
                for i, sub in enumerate(passo.get("subperguntas", []), start=1):
                    print(f"   - Subpergunta {i}: {sub}")
            elif etapa == "roteamento":
                print(f"2. Roteamento ({passo['total_chamadas']} execução(ões)):")
                for rota in passo.get("rotas", []):
                    print(f"   - \"{rota['subpergunta']}\" -> {', '.join(rota['agentes'])}")
            elif etapa == "execucao_paralela":
                print(
                    f"3. Execução em paralelo: tempo_total={passo['tempo_paralelo_s']}s "
                    f"| soma_individual={passo['soma_tempos_individuais_s']}s "
                    f"| ganho={passo['ganho_paralelismo_s']}s"
                )
                for ex in passo.get("execucoes", []):
                    status = f"ERRO ({ex['erro']})" if ex.get("erro") else f"OK ({ex['n_trechos']} trechos)"
                    ferr = ex.get("ferramenta")
                    ferr_txt = ""
                    if ferr:
                        args_txt = json.dumps(ferr.get("argumentos", {}), ensure_ascii=False)
                        estado_f = " · RECUSADO" if ferr.get("recusado") else ""
                        modo_red = ""
                        if not ferr.get("recusado") and "redigido_por_llm" in ferr:
                            modo_red = " · redação=LLM" if ferr["redigido_por_llm"] else " · redação=determinística"
                        ferr_txt = f" · ferramenta={ferr['nome']}({args_txt}){estado_f}{modo_red}"
                    print(f"   - [{ex['nome_agente']}] {ex['tempo_total_s']}s · {status}{ferr_txt}")
            elif etapa == "validacao_factual":
                print("4. Validador factual:")
                for res in passo.get("resultados", []):
                    if res.get("ignorado_por_erro"):
                        estado = "ignorado (agente falhou)"
                    elif res.get("indisponivel"):
                        estado = "indisponível (degradado)"
                    else:
                        estado = "APROVADO" if res.get("aprovado") else "REPROVADO"
                    det = f" ({'; '.join(res['motivos'])})" if res.get("motivos") else ""
                    if res.get("aprovado_inicial") is False and not res.get("ignorado_por_erro") and not res.get("indisponivel"):
                        motivos_ini = "; ".join(res.get("motivos_iniciais", []))
                        print(
                            f"   - {res['agente']}: 1ª avaliação=REPROVADO ({motivos_ini}) "
                            f"-> pós-reparo={estado}{det}"
                        )
                    else:
                        print(f"   - {res['agente']}: {estado}{det}")
                for dev in passo.get("devolucoes_ao_sintetizador", []):
                    status_pos = (
                        "RECUSA FINAL"
                        if dev.get("recusa_final")
                        else ("APROVADO" if dev.get("aprovado_apos_devolucao") else "SINALIZADO")
                    )
                    motivos_dev = "; ".join(dev.get("motivos_reprovacao", []))
                    resp_ant = (dev.get("resposta_anterior") or "").replace("\n", " ").strip()
                    if len(resp_ant) > 120:
                        resp_ant = resp_ant[:117] + "..."
                    print(
                        f"   -> Devolvido ao Sintetizador ({dev['nome_agente']}, "
                        f"tentativa {dev.get('tentativa', 1)}/1): "
                        f"ação={dev['acao']} · pós-reparo={status_pos}"
                    )
                    if motivos_dev:
                        print(f"      motivos: {motivos_dev}")
                    if resp_ant:
                        print(f"      resposta reprovada: \"{resp_ant}\"")
            elif etapa == "composicao_sintetizador":
                print(
                    f"5. Composição (Sintetizador): {passo['n_partes']} parte(s) · "
                    f"índices [n] isolados={passo['indices_isolados_por_parte']} · "
                    f"degradado={passo['degradado']}"
                )
        interacoes = r.get("interacoes") or []
        if interacoes:
            print(f"6. Interações registradas no Trace ({len(interacoes)} Mensagem -> Resposta):")
            for idx_i, it in enumerate(interacoes, start=1):
                msg_i = it.get("mensagem", {})
                resp_i = it.get("resposta", {})
                conteudo_r = (resp_i.get("conteudo") or "").replace("\n", " ").strip()
                if len(conteudo_r) > 80:
                    conteudo_r = conteudo_r[:77] + "..."
                alertas_i = resp_i.get("alertas") or []
                alerta_txt = f" · alertas={len(alertas_i)}" if alertas_i else ""
                print(
                    f"   [{idx_i}] {msg_i.get('remetente')} -> {msg_i.get('destinatario')}: "
                    f"\"{conteudo_r}\"{alerta_txt}"
                )
        print("===========================================\n")

    for i, parte in enumerate(r.get("partes", []), start=1):
        print(f"--- Parte {i} · {parte['nome_agente']} ---")
        print(f"Subpergunta: {parte['subpergunta']}")
        if parte.get("erro"):
            print(f"⚠ Falha no agente: {parte['erro']}")
            print()
            continue
        print("Trechos recuperados (índices locais):")
        for idx_t, t in enumerate(parte.get("trechos_recuperados", []), start=1):
            sim = f" · sim {t['similaridade']}" if t.get("similaridade") is not None else ""
            print(f"  [{idx_t}] {t['chunk_id']} · {t['titulo'][:60]} · p.{t['pagina']}{sim}")
        print(f"\nResposta ({r['backend']}):\n{parte['resposta']}\n")
        print("Fontes citadas:")
        for f in parte.get("fontes_citadas", []):
            print(f"  [{f['n']}] {f['doc_id']} · {f['titulo']} · p.{f['pagina']} · {f['url']}")
        if parte.get("dado_estruturado") is not None and parte.get("ferramenta_chamada"):
            nome_f = parte["ferramenta_chamada"]["nome"]
            print(f"\nDado estruturado ({nome_f}):")
            print(json.dumps(parte["dado_estruturado"], ensure_ascii=False, indent=2))
        val = parte.get("validacao") or {}
        if val.get("motivos"):
            print(f"⚠ Validador: {'; '.join(val['motivos'])}")
        print()

    for aviso in r.get("avisos", []):
        print(aviso)

    print(
        f"(paralelo {r['tempo_paralelo_s']}s vs soma individual {r['soma_tempos_individuais_s']}s "
        f"· decomposição {r['tempo_decomposicao_s']}s)"
    )


def perguntar(args):
    sem_rag = getattr(args, "sem_rag", False)
    usar_agentes = getattr(args, "agentes", False)
    falhar_agente = getattr(args, "falhar_agente", None)
    data = getattr(args, "data", None)
    curso = getattr(args, "curso", None)
    curriculo_id = getattr(args, "curriculo", None)
    vigencia = getattr(args, "vigencia", None)
    r = responder(
        " ".join(args.pergunta),
        args.backend,
        args.eixo,
        args.k,
        sem_rag=sem_rag,
        usar_agentes=usar_agentes,
        falhar_agente=falhar_agente,
        data=data,
        curso=curso,
        curriculo_id=curriculo_id,
        vigencia=vigencia,
    )
    if getattr(args, "saida", "texto") == "json":
        saida_dict = dict(r)
        if not usar_agentes:
            saida_dict["sem_rag"] = sem_rag
        print(json.dumps(saida_dict, ensure_ascii=False, indent=2))
    elif usar_agentes:
        imprimir_agentes(r, mostrar_trace=getattr(args, "trace", False))
    else:
        imprimir(r, sem_rag=sem_rag)


def avaliar(args):
    with open(config.PERGUNTAS_AVALIACAO / "perguntas_ouro.jsonl", encoding="utf-8") as f:
        casos = [json.loads(l) for l in f]
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
    config.RESULTADOS_AVALIACAO.mkdir(parents=True, exist_ok=True)
    (config.RESULTADOS_AVALIACAO / "resultado_recuperacao.json").write_text(
        json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")


def demo(args):
    with open(config.PERGUNTAS_AVALIACAO / "perguntas_demo.jsonl", encoding="utf-8") as f:
        perguntas = [json.loads(l) for l in f]
    saidas = []
    for p in perguntas:
        r = responder(p["pergunta"], args.backend)
        r["id"] = p["id"]
        r["rotulo"] = p.get("rotulo", "")
        imprimir(r)
        saidas.append(r)
    config.RESULTADOS_AVALIACAO.mkdir(parents=True, exist_ok=True)
    destino = config.RESULTADOS_AVALIACAO / "demo_respostas.json"
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
    p.add_argument("--agentes", action="store_true", help="Usa o orquestrador multiagentes (RU, Fluxo e Validador)")
    p.add_argument("--trace", action="store_true", help="Exibe o rastreamento completo da orquestração multiagentes")
    p.add_argument("--data", default=None, help="Data de referência AAAA-MM-DD para ferramentas de cardápio")
    p.add_argument("--curso", default=None, help="Curso da FCTE para consulta curricular (ex.: software, aeroespacial, eletronica, automotiva, energia)")
    p.add_argument("--curriculo", default=None, help="ID exato do currículo/vigência (ex.: automotiva-2018-2026, automotiva-2027)")
    p.add_argument("--vigencia", default=None, help="Ano/período de vigência do currículo (ex.: 2027, 2018)")
    p.add_argument("--falhar-agente", choices=["ru", "fluxo", "validador"], default=None,
                   help="Simula queda de um agente para testar degradação elegante")
    p.add_argument("--saida", choices=["texto", "json"], default="texto", help="Formato de saída (texto ou json)")
    p.set_defaults(f=perguntar)
    a = sub.add_parser("avaliar")
    a.add_argument("-k", type=int, default=config.TOP_K)
    a.set_defaults(f=avaliar)
    d = sub.add_parser("demo")
    d.add_argument("--backend", default=config.BACKEND, choices=["hf", "ollama", "openai", "extrativo"])
    d.set_defaults(f=demo)

    lista_args = list(sys.argv[1:] if argv is None else argv)
    subcomandos = {"ingerir", "perguntar", "avaliar", "demo", "-h", "--help"}
    if lista_args and lista_args[0] not in subcomandos:
        lista_args = ["perguntar", *lista_args]

    args = ap.parse_args(lista_args)
    args.f(args)


if __name__ == "__main__":
    sys.exit(main())
