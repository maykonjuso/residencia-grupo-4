"""Linha de comando da coleta.

  python -m rumo_rag.coleta cardapio --dry-run          # baixa a semana atual do site do RU e imprime, sem gravar (#50)
  python -m rumo_rag.coleta cardapio                    # idem, e grava: HTML bruto, PDF e entrada no catalogo.yaml
  python -m rumo_rag.coleta cardapio --dry-run --semana 2026-11-16
  python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09 --refeicao almoco
  python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09          # todas as refeições do dia
  python -m rumo_rag.coleta cardapio --data 2026-11-09 --refeicao almoco      # texto do chunk, para conferir
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import cardapio, scraper


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
    g = scraper.gravar(r["pagina"], r["pdf"], r["semana"], date.today())
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
        ids = {r["fonte"]["chunk_id"] for r in resultados}
        for c in cardapio.carregar_chunks_cardapio():
            if c["chunk_id"] in ids:
                print(f"[{c['chunk_id']} · p. {c['pagina']}]\n{c['texto']}\n")
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
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
