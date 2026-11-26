"""Linha de comando da coleta.

  python -m rumo_rag.coleta cardapio --dry-run          # baixa a semana atual do site do RU e imprime, sem gravar (#50)
  python -m rumo_rag.coleta cardapio                    # idem, e grava: HTML bruto, PDF e entrada no catalogo.yaml
  python -m rumo_rag.coleta cardapio --dry-run --semana 2026-11-16
  python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09 --refeicao almoco
  python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09          # todas as refeições do dia
  python -m rumo_rag.coleta cardapio --data 2026-11-09 --refeicao almoco      # texto do chunk, para conferir
  python -m rumo_rag.coleta turmas --ano 2026 --periodo 2 --dry-run           # oferta da FCTE no SIGAA público (#56)
  python -m rumo_rag.coleta turmas --ano 2026 --periodo 2                     # idem, e grava JSON, texto curado e catálogo
  python -m rumo_rag.coleta prerequisitos --curriculo software-2024-2          # fichas do SIGAA × grafo (#52)
  python -m rumo_rag.coleta prerequisitos --local dados/sigaa/prerequisitos_software-2024-2.json  # recompara sem rede
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import cardapio, scraper, sigaa


def cmd_turmas(args) -> int:
    """Oferta de turmas de graduação da FCTE na consulta pública do SIGAA (#56)."""
    try:
        if args.pagina_local:
            bruto = Path(args.pagina_local).read_text(encoding="utf-8", errors="replace")
            turmas = sigaa.ler_turmas(bruto)
            if not turmas:
                raise sigaa.ErroSigaa(f"Nenhuma turma em {args.pagina_local}.")
        else:
            turmas, bruto = sigaa.coletar_turmas(args.ano, args.periodo)
    except sigaa.ErroSigaa as e:
        print(f"erro: {e}\nNada foi gravado.", file=sys.stderr)
        return 3
    oferta = sigaa.montar_oferta(turmas, args.ano, args.periodo, date.today().isoformat())
    sigaa.validar_oferta(oferta)
    disciplinas = len({t["codigo"] for t in turmas})
    sem_local = sum(1 for t in turmas if not t["salas"])
    sem_horario = sum(1 for t in turmas if not t["aulas"])
    print(f"{len(turmas)} turmas de {disciplinas} disciplinas em {args.ano}.{args.periodo} "
          f"({sem_local} sem local, {sem_horario} sem horário por extenso)")
    if args.dry_run:
        print(sigaa.gerar_markdown(oferta)[:3000])
        print("(dry-run: nada foi gravado)", file=sys.stderr)
        return 0
    g = sigaa.gravar_oferta(oferta, None if args.pagina_local else bruto)
    for arq in g["arquivos"]:
        print(f"gravado: {arq}", file=sys.stderr)
    for aviso in g["avisos"]:
        print(f"aviso: {aviso}", file=sys.stderr)
    estado = "registrada no catálogo" if g["novo"] else "já estava no catálogo"
    print(f"{g['doc_id']} {estado}. Para indexar: python -m rumo_rag ingerir", file=sys.stderr)
    return 0


def cmd_prerequisitos(args) -> int:
    """Pré-requisitos das fichas públicas do SIGAA comparados com o grafo curricular (#52)."""
    grafo = json.loads((sigaa.config.DADOS / "grafo_curricular.json").read_text(encoding="utf-8"))
    curriculos = {c["curriculo_id"]: c for c in grafo["curriculos"]}
    if args.local:
        anterior = json.loads(Path(args.local).read_text(encoding="utf-8"))
        curriculo = curriculos[anterior["curriculo_id"]]
        relatorio = sigaa.montar_relatorio_componentes(curriculo, anterior["componentes"],
                                                       anterior["fonte"]["coletado_em"],
                                                       anterior.get("falhas_de_coleta", []))
    else:
        if args.curriculo not in curriculos:
            print(f"erro: currículo {args.curriculo!r} não está no grafo ({', '.join(curriculos)})", file=sys.stderr)
            return 2
        curriculo = curriculos[args.curriculo]
        sessao = sigaa.Sessao()
        componentes, faltando = [], []
        for no in curriculo["nos"]:
            try:
                ficha, _ = sigaa.coletar_componente(no["codigo"], sessao)
                componentes.append(ficha)
                print(f"ok {no['codigo']}: {ficha['pre_requisitos']['expressao'] or '-'}", file=sys.stderr)
            except (sigaa.ErroSigaa, ValueError) as e:
                faltando.append({"codigo": no["codigo"], "erro": str(e)})
                print(f"falhou {no['codigo']}: {e}", file=sys.stderr)
        relatorio = sigaa.montar_relatorio_componentes(curriculo, componentes, date.today().isoformat(), faltando)
    r = relatorio["resumo"]
    print(f"{relatorio['curriculo_id']}: {r['fichas']} fichas de {r['disciplinas']} disciplinas · "
          f"{r['iguais']} relações iguais, {r['divergentes']} divergentes, {r['sem_ficha']} sem ficha")
    for linha in relatorio["comparacao"]:
        if linha["situacao"] == "diverge":
            print(f"  {linha['codigo']} ({linha['relacao']}): SIGAA {linha['sigaa']} "
                  f"[{linha['expressao_sigaa']}] × grafo {linha['grafo']}")
    if args.saida and not args.local:
        destino = Path(args.saida)
        scraper.gravar_atomico(destino, json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n")
        print(f"gravado: {destino}", file=sys.stderr)
    return 1 if (args.falhar_se_divergir and r["divergentes"]) else 0


def cmd_coleta(args) -> int:
    """Scraper do cardápio semanal do RU Gama (#50)."""
    try:
        referencia = date.fromisoformat(args.semana) if args.semana else date.today()
    except ValueError:
        print(f"erro: --semana deve ser AAAA-MM-DD, recebi {args.semana!r}", file=sys.stderr)
        return 2
    try:
        r = scraper.coletar(referencia,
                            pagina_local=Path(args.pagina_local) if args.pagina_local else None,
                            pdf_local=Path(args.pdf_local) if args.pdf_local else None,
                            url_pdf=args.url_pdf)
    except scraper.ErroColeta as e:
        print(f"erro: {e}\nNada foi gravado.", file=sys.stderr)
        return 3
    for aviso in r["avisos"]:
        print(f"aviso: {aviso}", file=sys.stderr)
    print(scraper.imprimir(r))
    if args.dry_run:
        print("(dry-run: nada foi gravado)", file=sys.stderr)
        return 0
    g = scraper.gravar(r["pagina"], r["pdf"], r["semana"], date.today(), resultado=r)
    for arq in g["arquivos"]:
        print(f"gravado: {arq}", file=sys.stderr)
    if g["novo"]:
        print(f"{g['doc_id']} registrado no catálogo. Para indexar: python -m rumo_rag ingerir", file=sys.stderr)
    else:
        print(f"semana já estava no catálogo como {g['doc_id']}; PDF atualizado.", file=sys.stderr)
    return 0


def cmd_cardapio(args) -> int:
    if not args.data:
        return cmd_coleta(args)
    try:
        resultados = cardapio.buscar(args.data, args.refeicao, doc_id=args.doc)
    except ValueError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    if not resultados:
        print(f"Não encontrei cardápio para {args.data}"
              + (f" ({args.refeicao})" if args.refeicao else "") + " nas fontes da base.", file=sys.stderr)
        return 1

    if not args.estruturado:
        ids = {r["fonte"].get("chunk_id") for r in resultados if r["fonte"].get("chunk_id")}
        impressos = 0
        if cardapio.config.CHUNKS.exists():
            for c in cardapio.carregar_chunks_cardapio():
                if c["chunk_id"] in ids:
                    print(f"[{c['chunk_id']} · p. {c['pagina']}]\n{c['texto']}\n")
                    impressos += 1
        if not impressos:
            for r in resultados:
                cid = r["fonte"].get("chunk_id") or r["fonte"]["doc_id"]
                pag = r["fonte"].get("pagina") or 1
                print(f"[{cid} · p. {pag}]\n{cardapio._formatar_refeicao_texto(r)}\n")
        return 0

    for r in resultados:
        cardapio.validar(r)
        for aviso in r["avisos"]:
            print(f"aviso: {aviso}", file=sys.stderr)
    saida = resultados[0] if args.refeicao else resultados
    texto = json.dumps(saida, ensure_ascii=False, indent=2)
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        print(f"salvo em {args.saida}", file=sys.stderr)
    else:
        print(texto)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m rumo_rag.coleta")
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("cardapio", help="sem --data: coleta a semana no site do RU (#50); "
                                        "com --data: consulta a base (texto ou JSON, #54)")
    c.add_argument("--data", help="AAAA-MM-DD: consulta o cardápio já indexado desse dia")
    coleta = c.add_argument_group("coleta no site do RU (sem --data)")
    coleta.add_argument("--dry-run", action="store_true", help="baixa e imprime os dias, sem gravar nada")
    coleta.add_argument("--semana", help="AAAA-MM-DD de um dia da semana desejada (padrão: hoje)")
    coleta.add_argument("--pagina-local", help="lê um HTML bruto salvo em vez de baixar a página")
    coleta.add_argument("--pdf-local", help="lê um PDF do disco em vez de baixar")
    coleta.add_argument("--url-pdf", help="baixa este PDF direto, sem passar pela página")
    c.add_argument("--refeicao", choices=["cafe", "almoco", "jantar"])
    c.add_argument("--estruturado", action="store_true", help="devolve o JSON por compartimento (#54)")
    c.add_argument("--doc", help="restringe a um documento do catálogo, ex.: F09")
    c.add_argument("--saida", help="grava o JSON em arquivo em vez de imprimir")
    c.set_defaults(func=cmd_cardapio)

    t = sub.add_parser("turmas", help="oferta de turmas da FCTE na consulta pública do SIGAA (#56)")
    t.add_argument("--ano", type=int, required=True)
    t.add_argument("--periodo", type=int, choices=[1, 2, 3, 4], required=True)
    t.add_argument("--dry-run", action="store_true", help="baixa e imprime, sem gravar nada")
    t.add_argument("--pagina-local", help="lê um HTML salvo da consulta em vez de baixar")
    t.set_defaults(func=cmd_turmas)

    pr = sub.add_parser("prerequisitos", help="fichas públicas do SIGAA comparadas com o grafo curricular (#52)")
    pr.add_argument("--curriculo", default="software-2024-2", help="curriculo_id do grafo_curricular.json")
    pr.add_argument("--saida", help="grava o relatório JSON (fichas + comparação)")
    pr.add_argument("--local", help="recompara um relatório já gravado, sem acessar o SIGAA")
    pr.add_argument("--falhar-se-divergir", action="store_true", help="sai com código 1 se houver divergência")
    pr.set_defaults(func=cmd_prerequisitos)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
