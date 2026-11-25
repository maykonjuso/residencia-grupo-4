"""Experimento comparativo de classificação e roteamento de perguntas múltiplas.

Compara três abordagens sobre `perguntas_roteamento_multiplas.jsonl`:
- Baseline: roteador léxico por regex (`agentes.rotear_subpergunta`).
- Teste 1: LLM decompõe e já classifica `eixo` no mesmo JSON (Estágio 2 estendido).
- Teste 2: `LiquidAI/d1-omni-600M` (System-1) classifica o domínio zero-shot.

Uso:
    python rag/avaliacao/scripts/avaliar_roteamento_agentes.py
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

_RAIZ_RAG = Path(__file__).resolve().parents[2]
if str(_RAIZ_RAG) not in sys.path:
    sys.path.insert(0, str(_RAIZ_RAG))

from rumo_rag import agentes, config, reescrita  # noqa: E402

_SYSTEM_DECOMPOR_E_ROTEAR = (
    "Você é o módulo de classificação e decomposição do sistema RUmo (UnB/FCTE - campus Gama).\n"
    "Domínios disponíveis:\n"
    '- "ru": Restaurante Universitário (cardápio, refeições, proteínas, alergênicos/leite/glúten, '
    "preços, grupos I-IV, isenção, bolsa/auxílio alimentação, horários, catraca/carteirinha).\n"
    '- "fluxo": fluxo de disciplinas, cursos de engenharia da FCTE, pré-requisitos, créditos, '
    "carga horária, estágio, trancamento/desistência de disciplina, ABI, pós-graduação/PPGEB.\n"
    '- "ambos": apenas quando uma subpergunta indivisível exige os dois domínios.\n\n'
    "Tarefa: quebre a pergunta composta em subperguntas independentes, diretas e autocontidas, "
    "classificando o eixo de cada uma.\n"
    'Retorne APENAS JSON: {"subperguntas": [{"pergunta": "...", "eixo": "ru"|"fluxo"|"ambos"}]}.'
)

_SYSTEM_CLASSIFICAR_SUB = (
    "Classifique a pergunta de estudante da UnB/FCTE em exatamente um domínio:\n"
    '- "ru": Restaurante Universitário (comida, cardápio, almoço, jantar, café/desjejum, '
    "alergênicos/derivados de leite/glúten, preço, auxílio alimentação, isenção, horários, catraca).\n"
    '- "fluxo": fluxo acadêmico e cursos da FCTE (disciplinas, pré-requisitos, créditos, carga horária, '
    "estágio, trancamento/desistência de turma, escolha de curso da ABI, mestrado/pós).\n"
    '- "ambos": somente se exigir simultaneamente os dois domínios.\n'
    'Retorne APENAS JSON: {"eixo": "ru"|"fluxo"|"ambos"}.'
)

_SCHEMA_DOMINIO = {
    "dominio": {
        "type": "choice",
        "instructions": "Which university domain does this student question belong to?",
        "criteria": {
            "ru": (
                "University dining hall / cafeteria (RU): meal prices, menu, lunch, dinner, breakfast, "
                "food allergies, milk/gluten, vegetarian, food assistance/scholarship, access turnstile."
            ),
            "fluxo": (
                "Academic courses and curriculum (FCTE/UnB): classes, prerequisites, credits, semesters, "
                "internship, dropping a class, major selection (ABI), graduate courses."
            ),
        },
    }
}

_LIMIAR_CONFIANCA_D1 = 0.60


def _normalizar_rotas(eixo: str) -> list[str]:
    v = (eixo or "").strip().lower()
    if v == "ru":
        return ["ru"]
    if v == "fluxo":
        return ["fluxo"]
    return ["ru", "fluxo"]


def _extrair_json(texto: str) -> dict[str, Any]:
    limpo = (texto or "").strip()
    m = re.search(r"\{.*\}", limpo, re.DOTALL)
    if m:
        limpo = m.group(0)
    try:
        obj = json.loads(limpo)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _descobrir_ollama() -> str | None:
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=3) as r:
            dados = json.loads(r.read().decode("utf-8"))
        modelos = [m.get("name", "") for m in dados.get("models", []) if m.get("name")]
        if not modelos:
            return None
        if config.MODELO_DECOMPOSITOR in modelos:
            return config.MODELO_DECOMPOSITOR
        for pref in ("qwen2.5:7b", "qwen2.5:3b", "qwen2.5", "qwen3"):
            for m in modelos:
                if pref in m:
                    return m
        return modelos[0]
    except Exception:
        return None


def _chamar_ollama_json(modelo: str, system: str, user: str) -> dict[str, Any]:
    corpo = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": "json",
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.0, "num_predict": 260},
    }
    req = urllib.request.Request(
        f"{config.OLLAMA_URL}/api/chat",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        conteudo = json.loads(r.read().decode("utf-8")).get("message", {}).get("content", "")
    return _extrair_json(conteudo)


def _carregar_hf_local():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    candidatos = [config.MODELO_HF]
    # Aproveita modelos locais menores já completos no cache caso Qwen2.5-7B esteja ausente
    for alt in ("Qwen/Qwen2.5-3B-Instruct", "crh225/plumb-4b"):
        if alt not in candidatos:
            candidatos.append(alt)

    ultimo_erro = None
    for nome in candidatos:
        try:
            tok = AutoTokenizer.from_pretrained(nome)
            dev, dtype = reescrita.dispositivo_gpu()
            mod = AutoModelForCausalLM.from_pretrained(
                nome,
                dtype=dtype if dev != "cpu" else torch.float32,
            ).to(dev).eval()
            return nome, tok, mod
        except Exception as exc:
            ultimo_erro = exc
    raise RuntimeError(f"Nenhum modelo HF generativo pôde ser carregado: {ultimo_erro}")


def _selecionar_backend_llm(preferencia: str = "auto") -> tuple[str, Any]:
    if preferencia in ("auto", "ollama"):
        mod_ollama = _descobrir_ollama()
        if mod_ollama:
            return "ollama", mod_ollama
        if preferencia == "ollama":
            raise RuntimeError(f"Ollama indisponível em {config.OLLAMA_URL} ou sem modelos.")

    nome, tok, mod = _carregar_hf_local()
    return "hf", (nome, tok, mod)


def _chamar_llm_json(backend_tipo: str, backend_ctx: Any, system: str, user: str) -> dict[str, Any]:
    if backend_tipo == "ollama":
        return _chamar_ollama_json(backend_ctx, system, user)

    _, tok, modelo = backend_ctx
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    entrada = tok.apply_chat_template(
        msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True
    ).to(modelo.device)
    saida = modelo.generate(
        **entrada,
        max_new_tokens=260,
        do_sample=False,
        repetition_penalty=1.05,
    )
    texto = tok.decode(saida[0][entrada["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return _extrair_json(texto)


def _classificar_dominio_d1(modelo_d1: Any, subpergunta: str) -> tuple[list[str], dict[str, float]]:
    res = modelo_d1.system_one(subpergunta.strip(), _SCHEMA_DOMINIO)
    probs = res["answers"]["dominio"]["probabilities"]
    p_ru = float(probs.get("ru", 0.0))
    p_fluxo = float(probs.get("fluxo", 0.0))
    if max(p_ru, p_fluxo) < _LIMIAR_CONFIANCA_D1:
        rotas = ["ru", "fluxo"]
    else:
        rotas = ["ru"] if p_ru >= p_fluxo else ["fluxo"]
    return rotas, {"ru": round(p_ru, 4), "fluxo": round(p_fluxo, 4)}


def _avaliar_subperguntas(registros: list[dict], chave_rotas: str, chave_tempo: str) -> dict:
    n = len(registros)
    exatas = sum(1 for r in registros if r[chave_rotas] == [r["eixo_esperado"]])
    cobertura = sum(1 for r in registros if r["eixo_esperado"] in r[chave_rotas])
    extras = sum(max(0, len(r[chave_rotas]) - 1) for r in registros)
    latencias = [r[chave_tempo] for r in registros]
    return {
        "n_subperguntas": n,
        "acertos_exatos": exatas,
        "acuracia_exata": round(exatas / n, 4),
        "recall_dominio": round(cobertura / n, 4),
        "chamadas_extras_desnecessarias": extras,
        "latencia_media_ms": round(statistics.mean(latencias), 2),
    }


def gerar_relatorio_md(resultado: dict) -> str:
    m_regex = resultado["metricas_subperguntas"]["regex"]
    m_t1 = resultado["metricas_subperguntas"]["teste1_llm"]
    m_t2 = resultado["metricas_subperguntas"]["teste2_d1_omni"]

    dec_t1 = resultado["metricas_decomposicao"]["teste1_llm"]
    dec_fb = resultado["metricas_decomposicao"]["fallback_sintatico"]
    st1_d1 = resultado["metricas_decomposicao"]["d1_omni_estagio1"]

    linhas = [
        "# Comparação de Classificação e Roteamento do Orquestrador (Teste 1 vs. Teste 2)",
        "",
        f"- **Dataset:** `rag/avaliacao/perguntas/perguntas_roteamento_multiplas.jsonl` "
        f"({resultado['total_perguntas_compostas']} perguntas múltiplas, {m_regex['n_subperguntas']} subperguntas esperadas)",
        f"- **Baseline:** Regex léxico (`agentes.rotear_subpergunta`)",
        f"- **Teste 1 (LLM Conjunto):** `{resultado['modelos']['teste1_llm']}` (decompõe e rotula `eixo` no mesmo JSON)",
        f"- **Teste 2 (System-1):** `{resultado['modelos']['teste2_d1_omni']}` (limiar compostas `{config.LIMIAR_COMPOSTA}`, confiança domínio `{_LIMIAR_CONFIANCA_D1}`)",
        "",
        "## 1. Roteamento por subpergunta (17 subperguntas canônicas)",
        "",
        "| Método | Acertos exatos | Acurácia exata | Recall do domínio | Chamadas extras (`ambos`) | Latência média |",
        "|---|---:|---:|---:|---:|---:|",
        f"| **Baseline · Regex** | {m_regex['acertos_exatos']}/{m_regex['n_subperguntas']} | {m_regex['acuracia_exata']:.1%} | {m_regex['recall_dominio']:.1%} | {m_regex['chamadas_extras_desnecessarias']} | {m_regex['latencia_media_ms']:.2f} ms |",
        f"| **Teste 1 · LLM Conjunto** | {m_t1['acertos_exatos']}/{m_t1['n_subperguntas']} | {m_t1['acuracia_exata']:.1%} | {m_t1['recall_dominio']:.1%} | {m_t1['chamadas_extras_desnecessarias']} | {m_t1['latencia_media_ms']:.1f} ms |",
        f"| **Teste 2 · d1-omni-600M** | {m_t2['acertos_exatos']}/{m_t2['n_subperguntas']} | {m_t2['acuracia_exata']:.1%} | {m_t2['recall_dominio']:.1%} | {m_t2['chamadas_extras_desnecessarias']} | {m_t2['latencia_media_ms']:.1f} ms |",
        "",
        "## 2. Decomposição e classificação nas 8 perguntas múltiplas",
        "",
        "| Etapa / Método | Resultado nas 8 compostas | Observação |",
        "|---|---|---|",
        f"| **Estágio 1 (`d1-omni-600M` >= {config.LIMIAR_COMPOSTA})** | {st1_d1['detectadas_compostas']}/{st1_d1['total']} detectadas ({st1_d1['taxa_deteccao']:.1%}) | Latência média {st1_d1['latencia_media_ms']:.1f} ms |",
        f"| **Teste 1 (LLM Decomposição + Eixo conjunto)** | {dec_t1['qtd_subperguntas_correta']}/{dec_t1['total']} com nº exato ({dec_t1['taxa_qtd_correta']:.1%}) · {dec_t1['sequencia_eixos_correta']}/{dec_t1['total']} com rota fim-a-fim exata | Latência média {dec_t1['latencia_media_ms']:.1f} ms |",
        f"| **Fallback sintático (`_decompor_fallback`)** | {dec_fb['qtd_subperguntas_correta']}/{dec_fb['total']} com nº exato ({dec_fb['taxa_qtd_correta']:.1%}) | Regra regex sem LLM |",
        "",
        "## 3. Onde os métodos divergiram nas subperguntas",
        "",
        "| ID | Subpergunta | Esperado | Regex | Teste 1 (LLM) | Teste 2 (`d1-omni`) |",
        "|---|---|---:|---|---|---|",
    ]

    for r in resultado["subperguntas"]:
        esp = r["eixo_esperado"]
        ok_rx = r["rotas_regex"] == [esp]
        ok_t1 = r["rotas_t1"] == [esp]
        ok_t2 = r["rotas_t2"] == [esp]
        if not (ok_rx and ok_t1 and ok_t2):
            p_info = f"`{r['rotas_t2']}` (RU={r['probs_t2']['ru']:.2f}, Fluxo={r['probs_t2']['fluxo']:.2f})"
            linhas.append(
                f"| {r['id_composta']} | {r['subpergunta']} | `{esp}` | `{r['rotas_regex']}` | `{r['rotas_t1']}` | {p_info} |"
            )

    if not any(
        not (r["rotas_regex"] == [r["eixo_esperado"]] == r["rotas_t1"] == r["rotas_t2"])
        for r in resultado["subperguntas"]
    ):
        linhas.append("| — | Todos os métodos concordaram em 100% das subperguntas | — | — | — | — |")

    linhas.extend(["", "## 4. Detalhe da decomposição conjunta (Teste 1)", ""])
    for item in resultado["compostas"]:
        subs_txt = "; ".join(f"`[{s['eixo']}]` {s['pergunta']}" for s in item["teste1_subperguntas"])
        linhas.append(
            f"- **{item['id']}** (d1-omni p={item['d1_prob_composta']:.3f}): {subs_txt or '(vazio)'}"
        )

    return "\n".join(linhas) + "\n"


def executar(backend_llm: str = "auto") -> dict[str, Any]:
    caminho_ds = config.PERGUNTAS_AVALIACAO / "perguntas_roteamento_multiplas.jsonl"
    with open(caminho_ds, encoding="utf-8") as f:
        casos = [json.loads(l) for l in f if l.strip()]

    print("1/2 Carregando modelo LLM para Teste 1...")
    tipo_llm, ctx_llm = _selecionar_backend_llm(preferencia=backend_llm)
    nome_llm = ctx_llm if tipo_llm == "ollama" else ctx_llm[0]
    print(f"    Teste 1 ativo via {tipo_llm}: {nome_llm}")

    print("2/2 Carregando LiquidAI/d1-omni-600M para Teste 2...")
    modelo_d1 = reescrita._carregar_decisor()
    # Warmup para não distorcer a latência do primeiro item
    _ = modelo_d1.system_one("Quanto custa o almoço?", _SCHEMA_DOMINIO)
    _ = _chamar_llm_json(tipo_llm, ctx_llm, _SYSTEM_CLASSIFICAR_SUB, "Quanto custa o almoço?")
    print("    Modelos aquecidos. Iniciando avaliação...\n")

    registros_compostas: list[dict[str, Any]] = []
    registros_subs: list[dict[str, Any]] = []

    for caso in casos:
        cid = caso["id"]
        q = caso["pergunta"]
        esp = caso["subperguntas_esperadas"]
        eixos_esp = [item["eixo"] for item in esp]

        # Estágio 1 d1-omni na pergunta composta
        t0 = time.perf_counter()
        eh_comp_d1, prob_d1 = reescrita.classificar_composta(q)
        lat_d1_comp = (time.perf_counter() - t0) * 1000.0

        # Fallback sintático
        subs_fb = reescrita._decompor_fallback(q)

        # Teste 1 fim-a-fim: decomposição + classificação de eixo conjunta no mesmo JSON
        t1 = time.perf_counter()
        resp_t1 = _chamar_llm_json(tipo_llm, ctx_llm, _SYSTEM_DECOMPOR_E_ROTEAR, q)
        lat_t1_comp = (time.perf_counter() - t1) * 1000.0
        brutas = resp_t1.get("subperguntas", [])
        subs_t1 = []
        for s in brutas:
            if isinstance(s, dict) and isinstance(s.get("pergunta"), str):
                subs_t1.append({
                    "pergunta": s["pergunta"].strip(),
                    "eixo": str(s.get("eixo", "ambos")).strip().lower(),
                })

        eixos_t1_pred = [s["eixo"] for s in subs_t1]
        registros_compostas.append({
            "id": cid,
            "pergunta": q,
            "esperado_n": len(esp),
            "esperado_eixos": eixos_esp,
            "d1_eh_composta": eh_comp_d1,
            "d1_prob_composta": prob_d1,
            "d1_latencia_ms": round(lat_d1_comp, 2),
            "fallback_n": len(subs_fb),
            "fallback_subperguntas": subs_fb,
            "teste1_subperguntas": subs_t1,
            "teste1_qtd_correta": len(subs_t1) == len(esp),
            "teste1_eixos_corretos": eixos_t1_pred == eixos_esp,
            "teste1_latencia_ms": round(lat_t1_comp, 2),
        })
        print(
            f"[{cid}] d1_comp={eh_comp_d1} (p={prob_d1:.3f}) | "
            f"T1 subs={len(subs_t1)}/{len(esp)} eixos={eixos_t1_pred} ({lat_t1_comp:.0f}ms)"
        )

        # Avaliação isolada das 17 subperguntas canônicas
        for idx_s, item_s in enumerate(esp, start=1):
            sub_txt = item_s["subpergunta"]
            eixo_esp = item_s["eixo"]

            t_r = time.perf_counter()
            rotas_rx = agentes.rotear_subpergunta(sub_txt)
            lat_rx = (time.perf_counter() - t_r) * 1000.0

            t_l = time.perf_counter()
            resp_sub_t1 = _chamar_llm_json(tipo_llm, ctx_llm, _SYSTEM_CLASSIFICAR_SUB, sub_txt)
            lat_l = (time.perf_counter() - t_l) * 1000.0
            rotas_t1 = _normalizar_rotas(str(resp_sub_t1.get("eixo", "ambos")))

            t_d = time.perf_counter()
            rotas_t2, probs_t2 = _classificar_dominio_d1(modelo_d1, sub_txt)
            lat_d = (time.perf_counter() - t_d) * 1000.0

            registros_subs.append({
                "id": f"{cid}.{idx_s}",
                "id_composta": cid,
                "subpergunta": sub_txt,
                "eixo_esperado": eixo_esp,
                "rotas_regex": rotas_rx,
                "latencia_regex_ms": round(lat_rx, 4),
                "rotas_t1": rotas_t1,
                "latencia_t1_ms": round(lat_l, 2),
                "rotas_t2": rotas_t2,
                "probs_t2": probs_t2,
                "latencia_t2_ms": round(lat_d, 2),
            })

    n_comp = len(registros_compostas)
    resultado = {
        "total_perguntas_compostas": n_comp,
        "modelos": {
            "teste1_llm": f"{tipo_llm}:{nome_llm}",
            "teste2_d1_omni": config.MODELO_DECISAO,
        },
        "metricas_subperguntas": {
            "regex": _avaliar_subperguntas(registros_subs, "rotas_regex", "latencia_regex_ms"),
            "teste1_llm": _avaliar_subperguntas(registros_subs, "rotas_t1", "latencia_t1_ms"),
            "teste2_d1_omni": _avaliar_subperguntas(registros_subs, "rotas_t2", "latencia_t2_ms"),
        },
        "metricas_decomposicao": {
            "d1_omni_estagio1": {
                "total": n_comp,
                "detectadas_compostas": sum(1 for c in registros_compostas if c["d1_eh_composta"]),
                "taxa_deteccao": round(sum(1 for c in registros_compostas if c["d1_eh_composta"]) / n_comp, 4),
                "latencia_media_ms": round(statistics.mean(c["d1_latencia_ms"] for c in registros_compostas), 2),
            },
            "teste1_llm": {
                "total": n_comp,
                "qtd_subperguntas_correta": sum(1 for c in registros_compostas if c["teste1_qtd_correta"]),
                "taxa_qtd_correta": round(sum(1 for c in registros_compostas if c["teste1_qtd_correta"]) / n_comp, 4),
                "sequencia_eixos_correta": sum(1 for c in registros_compostas if c["teste1_eixos_corretos"]),
                "latencia_media_ms": round(statistics.mean(c["teste1_latencia_ms"] for c in registros_compostas), 2),
            },
            "fallback_sintatico": {
                "total": n_comp,
                "qtd_subperguntas_correta": sum(1 for c in registros_compostas if c["fallback_n"] == c["esperado_n"]),
                "taxa_qtd_correta": round(
                    sum(1 for c in registros_compostas if c["fallback_n"] == c["esperado_n"]) / n_comp, 4
                ),
            },
        },
        "compostas": registros_compostas,
        "subperguntas": registros_subs,
    }

    config.RESULTADOS_AVALIACAO.mkdir(parents=True, exist_ok=True)
    arq_json = config.RESULTADOS_AVALIACAO / "resultado_roteamento_agentes.json"
    arq_md = config.RESULTADOS_AVALIACAO / "relatorio_roteamento_agentes.md"
    arq_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    arq_md.write_text(gerar_relatorio_md(resultado), encoding="utf-8")
    print(f"\nJSON salvo em: {arq_json}")
    print(f"Relatório MD salvo em: {arq_md}")
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara Teste 1 (LLM) vs Teste 2 (d1-omni) vs Regex")
    parser.add_argument("--backend-llm", default="auto", choices=["auto", "ollama", "hf"])
    args = parser.parse_args()
    executar(backend_llm=args.backend_llm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
