"""Gera as tabelas da página docs/entrega-3/llm-vs-rag.md a partir de
avaliacao/respostas_comparativas.json (saída de `python -m rumo_rag comparar`, issue #17).

    cd rag
    python -m rumo_rag comparar          # gera o JSON (precisa do LLM)
    python gerar_tabela_comparativa.py   # gera os includes (não precisa de GPU)

Saídas (incluídas na página via snippet, não editar à mão):
    includes/llm_vs_rag_tabela4.md     linhas da Tabela 4 (uma por pergunta)
    includes/llm_vs_rag_resumo.md      Tabela 3 (por eixo) e Tabela 5 (por categoria)

As colunas automáticas vêm do JSON. O julgamento humano (alucinou? resposta completa?)
fica em avaliacao/diagnosticos_comparativos.json, escrito pelas donas da issue:

    {"Q01": {"sem_rag": "alucinou", "com_rag": "fiel", "diagnostico": "inventou R$ 5,00"}}

    sem_rag: alucinou | correta | recusou | parcial
    com_rag: fiel | incompleta | recusou | alucinou
"""
import json
from collections import defaultdict
from pathlib import Path

raiz = Path(__file__).resolve().parent
caminho_json = raiz / "avaliacao" / "respostas_comparativas.json"
if caminho_json.exists():
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
else:
    # Ainda sem rodada: gera a tabela com "A medir" a partir das perguntas, para a página não quebrar
    vazio = {"resposta": "*A medir*", "recusou": False, "valores_sem_fonte": []}
    perguntas = []
    for arq in ("perguntas_ouro.jsonl", "perguntas_fora_da_base.jsonl"):
        perguntas += [json.loads(l) for l in open(raiz / "avaliacao" / arq, encoding="utf-8") if l.strip()]
    dados = {"meta": None, "respostas": [{**p, "sem_rag": vazio, "com_rag": vazio} for p in perguntas]}
caminho_diag = raiz / "avaliacao" / "diagnosticos_comparativos.json"
diag = json.loads(caminho_diag.read_text(encoding="utf-8")) if caminho_diag.exists() else {}
respostas = dados["respostas"]


def celula(texto: str) -> str:
    return (texto or "").replace("|", "\\|").replace("\n", "<br>").strip()


def sinal(lado: dict) -> str:
    """Sinal automático: recusa e valores que a base não sustenta."""
    if dados["meta"] is None:
        return "*A medir*"
    if lado["recusou"]:
        return "recusou"
    if lado["valores_sem_fonte"]:
        return "⚠ sem fonte: " + ", ".join(lado["valores_sem_fonte"])
    return "valores ok"


# ---------- Tabela 4: uma linha por pergunta ----------
linhas = []
for r in respostas:
    d = diag.get(r["id"], {})
    docs = ", ".join(f"`{x}`" for x in r["docs_esperados"]) or "—"
    julgamento = " · ".join(x for x in (
        f"sem RAG: {d['sem_rag']}" if d.get("sem_rag") else "",
        f"com RAG: {d['com_rag']}" if d.get("com_rag") else "") if x)
    fidelidade = "<br>".join(x for x in (
        f"Sem RAG: {sinal(r['sem_rag'])}", f"Com RAG: {sinal(r['com_rag'])}", julgamento) if x)
    linhas.append(
        f"| **{r['id']}** | `{r['eixo']}` | {r['categoria']} | {celula(r['pergunta'])} | {docs} "
        f"| {celula(r['sem_rag']['resposta'])} | {celula(r['com_rag']['resposta'])} "
        f"| {fidelidade} | {celula(d.get('diagnostico', '')) or '*A preencher*'} |")
cab = ("| ID | Eixo | Categoria | Pergunta | Docs esperados | Resposta Sem RAG (LLM puro) "
       "| Resposta Com RAG (RUmo) | Fidelidade / Alucinação | Diagnóstico |\n"
       "|:---:|:---:|:---:|---|---|---|---|---|---|")
(raiz.parent / "includes" / "llm_vs_rag_tabela4.md").write_text(
    cab + "\n" + "\n".join(linhas) + "\n", encoding="utf-8")


# ---------- Tabelas 3 e 5: agregados ----------
def agregar(chave: str) -> dict:
    g = defaultdict(lambda: defaultdict(int))
    for r in respostas:
        a = g[r[chave]]
        d = diag.get(r["id"], {})
        a["n"] += 1
        a["sem_valor_sem_fonte"] += bool(r["sem_rag"]["valores_sem_fonte"])
        a["sem_recusou"] += r["sem_rag"]["recusou"]
        a["com_valor_sem_fonte"] += bool(r["com_rag"]["valores_sem_fonte"])
        a["com_recusou"] += r["com_rag"]["recusou"]
        a["sem_alucinou"] += d.get("sem_rag") == "alucinou"
        a["com_fiel"] += d.get("com_rag") == "fiel"
        a["com_incompleta"] += d.get("com_rag") == "incompleta"
    return g


def tabela(g: dict, titulo: str, ordem: list[str]) -> str:
    julgado = bool(diag)
    out = [f"| {titulo} | n | Sem RAG: valores sem fonte | Sem RAG: recusas | Com RAG: valores sem fonte "
           f"| Com RAG: recusas | Sem RAG: alucinações | Com RAG: fidelidade total | Com RAG: incompletude |",
           "|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"]
    total = defaultdict(int)
    for k in ordem + sorted(set(g) - set(ordem)):
        if k not in g:
            continue
        a = g[k]
        for c, v in a.items():
            total[c] += v
        out.append(_linha(f"`{k}`", a, julgado))
    out.append(_linha("**Total**", total, julgado))
    return "\n".join(out)


def _linha(rotulo: str, a: dict, julgado: bool) -> str:
    h = (lambda c: str(a[c])) if julgado else (lambda c: "*A julgar*")
    return (f"| {rotulo} | {a['n']} | {a['sem_valor_sem_fonte']} | {a['sem_recusou']} | {a['com_valor_sem_fonte']} "
            f"| {a['com_recusou']} | {h('sem_alucinou')} | {h('com_fiel')} | {h('com_incompleta')} |")


m = dados["meta"]
if m is None:
    (raiz.parent / "includes" / "llm_vs_rag_resumo.md").write_text(
        "!!! warning \"Rodada ainda não executada\"\n    Rode `python -m rumo_rag comparar` e depois "
        "`python gerar_tabela_comparativa.py` para preencher as tabelas.\n", encoding="utf-8")
    print(f"sem respostas_comparativas.json: {len(respostas)} linhas com 'A medir'")
    raise SystemExit
resumo = [
    f'<p class="legenda">Rodada de {m["gerado_em"][:10]} · {m["modelo"]} · backend {m["backend"]} · '
    f'{m["decodificacao"]} · top-{m["top_k"]} · embedding {m["embedding"]} · {m["n"]} perguntas.</p>\n',
    "#### Por eixo\n",
    tabela(agregar("eixo"), "Eixo", ["ru", "apoio", "fluxo", "fora"]),
    '\n<p class="legenda">Tabela 3. Comparação agregada por eixo temático.</p>\n',
    "#### Por categoria\n",
    tabela(agregar("categoria"), "Categoria",
           ["preço", "cardápio", "horário", "calendário", "pré-requisito", "currículo",
            "regra", "procedimento", "conceito", "fora da base"]),
    '\n<p class="legenda">Tabela 5. Comparação agregada por categoria de pergunta.</p>\n',
]
(raiz.parent / "includes" / "llm_vs_rag_resumo.md").write_text("\n".join(resumo), encoding="utf-8")
print(f"{len(respostas)} perguntas · {len(diag)} diagnósticos → includes/llm_vs_rag_tabela4.md e llm_vs_rag_resumo.md")
