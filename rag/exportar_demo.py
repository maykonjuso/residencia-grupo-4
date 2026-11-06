"""Gera docs/javascripts/demo-dados.js a partir de avaliacao/demo_respostas.json (saídas reais)."""
import json
import re
from pathlib import Path

raiz = Path(__file__).resolve().parent
dados = json.loads((raiz / "avaliacao" / "demo_respostas.json").read_text(encoding="utf-8"))
rotulos = {json.loads(l)["id"]: json.loads(l).get("rotulo", "")
           for l in (raiz / "avaliacao" / "perguntas_demo.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
for d in dados:
    d["rotulo"] = d.get("rotulo") or rotulos.get(d["id"], "")
    d["backend_rotulo"] = "Qwen2.5-7B-Instruct · 4 bits · local" if d["backend"] == "hf" else d["backend"]
    for t in d["trechos_recuperados"]:
        t["texto"] = re.sub(r"^#+\s*", "", t["texto"], flags=re.M)[:600]
destino = raiz.parent / "docs" / "javascripts" / "demo-dados.js"
destino.write_text("/* Gerado por rag/exportar_demo.py. Não editar à mão. */\nwindow.RUMO_DEMO = "
                   + json.dumps(dados, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
print(f"{len(dados)} consultas exportadas para {destino}")

# ---- versão em Markdown para a página de demonstração (incluída via snippet) ----
linhas = []
for d in dados:
    linhas.append(f'\n### {d["id"]} · {d["rotulo"]}\n')
    linhas.append(f'```text\n$ python -m rumo_rag perguntar "{d["pergunta"]}"\n```\n')
    linhas.append('**Trechos recuperados (busca híbrida):**\n')
    linhas.append("| # | Chunk | Documento | Pág. | Seção | Similaridade |\n|---|---|---|---|---|---|")
    for i, t in enumerate(d["trechos_recuperados"], start=1):
        sim = "" if t.get("similaridade") is None else f'{t["similaridade"]:.3f}'
        secao = (t.get("secao") or "").replace("|", "/")[-60:]
        linhas.append(f'| {i} | `{t["chunk_id"]}` | {t["titulo"]} | {t["pagina"]} | {secao} | {sim} |')
    resp = d["resposta"].replace("\n", "\n    ")
    linhas.append(f'\n!!! quote "Resposta gerada ({d["backend_rotulo"]})"\n    {resp}\n')
    if d["fontes_citadas"]:
        linhas.append("**Fontes citadas na resposta:**\n")
        for f in d["fontes_citadas"]:
            linhas.append(f'- [{f["n"]}] **{f["doc_id"]}** · [{f["titulo"]}]({f["url"]}) · p. {f["pagina"]} · chunk `{f["chunk_id"]}`')
    else:
        linhas.append("**Fontes citadas na resposta:** nenhuma.")
    if d.get("valores_sem_fonte"):
        linhas.append(f'\n!!! danger "Verificador de fidelidade: valores sem fonte"\n    A resposta traz **{", ".join(d["valores_sem_fonte"])}**, que não aparece em nenhum trecho recuperado. O sistema mostra este alerta ao estudante.\n')
    elif d["fontes_citadas"]:
        linhas.append('\n<span class="selo selo--verde">verificador: todos os valores da resposta estão nas fontes</span>\n')
    linhas.append(f'\n<p class="legenda">Busca {d["tempo_busca_s"]} s · geração {d["tempo_geracao_s"]} s.</p>\n')
md = raiz.parent / "includes" / "demo_respostas.md"
md.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print(f"markdown da demonstração → {md}")
