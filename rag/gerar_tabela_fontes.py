"""Gera a tabela de fontes da GitPage a partir do catálogo (evita divergência entre os dois)."""
import json
from collections import Counter
from pathlib import Path
import yaml

raiz = Path(__file__).resolve().parent
docs = yaml.safe_load((raiz / "catalogo.yaml").read_text(encoding="utf-8"))["documentos"]
n = Counter(json.loads(l)["doc_id"] for l in (raiz / "dados" / "chunks.jsonl").open(encoding="utf-8"))
nomes = {"ru": "Eixo RU", "fluxo": "Eixo fluxo de disciplinas", "apoio": "Apoio"}
saida = []
for eixo in ("ru", "fluxo", "apoio"):
    saida.append(f"\n### {nomes[eixo]} {{#eixo-{eixo}}}\n\n| ID | Documento | Órgão | Tipo | Data | Chunks |\n|---|---|---|---|---|---|")
    for d in docs:
        if d["eixo"] == eixo:
            saida.append(f"| {d['id']} | [{d['titulo']}]({d['url']}) | {d['orgao']} | {d['tipo']} | {d['data']} | {n[d['id']]} |")
destino = raiz.parent / "includes" / "tabela_fontes.md"   # incluída via snippet
destino.write_text("\n".join(saida) + "\n", encoding="utf-8")
print(f"{len(docs)} documentos · {sum(n.values())} chunks → {destino}")
