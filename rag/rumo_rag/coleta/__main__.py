"""Linha de comando da coleta.

  python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09 --refeicao almoco
  python -m rumo_rag.coleta cardapio --estruturado --data 2026-11-09          # todas as refeições do dia
  python -m rumo_rag.coleta cardapio --data 2026-11-09 --refeicao almoco      # texto do chunk, para conferir
"""
import argparse
import json
import sys

from . import cardapio


def cmd_cardapio(args) -> int:
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
    c = sub.add_parser("cardapio", help="cardápio de uma data (texto ou JSON de montagem de prato)")
    c.add_argument("--data", required=True, help="AAAA-MM-DD")
    c.add_argument("--refeicao", choices=["cafe", "almoco", "jantar"])
    c.add_argument("--estruturado", action="store_true", help="devolve o JSON por compartimento (#54)")
    c.add_argument("--doc", help="restringe a um documento do catálogo, ex.: F09")
    c.add_argument("--saida", help="grava o JSON em arquivo em vez de imprimir")
    c.set_defaults(func=cmd_cardapio)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
