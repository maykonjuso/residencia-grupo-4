"""Avaliação completa do pipeline de reescrita (JevK5-Lite + LLM Decomposer) sobre C01–C05."""
from __future__ import annotations

import json
import statistics
import time

from rumo_rag import config, geracao, indice, reescrita

CASOS_COMPOSTOS = [
    {
        "id": "C01",
        "pergunta": "Qual o valor do almoço para estudante e quais os horários de funcionamento do jantar no Gama?",
        "eixo_a": ("RU (Tarifas)", ["F01", "F04"]),
        "eixo_b": ("RU (Horários)", ["F02", "F03"]),
    },
    {
        "id": "C02",
        "pergunta": "Qual o pré-requisito de Engenharia de Software e como funciona o trancamento geral de matrícula?",
        "eixo_a": ("Fluxo (ESW)", ["F15", "F16"]),
        "eixo_b": ("Legislação (CEPE 93/2018)", ["F31"]),
    },
    {
        "id": "C03",
        "pergunta": "Estudante com gratuidade tem direito ao café da manhã e qual o horário do almoço no sábado?",
        "eixo_a": ("RU (Assistência)", ["F01", "F04", "F06", "F07"]),
        "eixo_b": ("RU (Horários FDS)", ["F02", "F03"]),
    },
    {
        "id": "C04",
        "pergunta": "Quais matérias da Engenharia Aeroespacial exigem Cálculo 2 e onde consulto o calendário acadêmico?",
        "eixo_a": ("Fluxo (Aeroespacial)", ["F17", "F18"]),
        "eixo_b": ("Calendário UnB", ["F29", "F30"]),
    },
    {
        "id": "C05",
        "pergunta": "O RU abre aos domingos e quais os documentos necessários para fazer a carteirinha?",
        "eixo_a": ("RU (Operação)", ["F02", "F03"]),
        "eixo_b": ("Acesso / Carteirinha", ["F05"]),
    },
]


def _avaliar_cobertura(docs_recuperados: list[str], esperado_a: list[str], esperado_b: list[str]) -> dict:
    ok_a = any(d in esperado_a for d in docs_recuperados)
    ok_b = any(d in esperado_b for d in docs_recuperados)
    eixos = int(ok_a) + int(ok_b)
    return {
        "eixo_a_coberto": ok_a,
        "eixo_b_coberto": ok_b,
        "eixos_cobertos": eixos,
        "cobertura_pct": round(eixos * 50.0, 1),
    }


def main() -> None:
    # Aquecimento de modelos (BGE-M3, BM25, JevK5-Lite e Qwen2.5-7B no Ollama)
    print("Aquecendo índices e modelos locais...")
    indice.buscar("Qual o preço do almoço no RU?", k=1, decompor_pergunta=False)
    reescrita.classificar_composta("Quanto custa o almoço e qual o horário do jantar?")
    geracao._gerar_ollama([{"role": "user", "content": "Responda apenas OK."}])
    reescrita._decompor_llm.cache_clear()

    resultados = []
    for caso in CASOS_COMPOSTOS:
        cid = caso["id"]
        q = caso["pergunta"]
        _, docs_a = caso["eixo_a"]
        _, docs_b = caso["eixo_b"]

        # 1. Sem reescrita
        t0 = time.perf_counter()
        trechos_sem = indice.buscar(q, k=config.TOP_K, decompor_pergunta=False)
        t_busca_sem = time.perf_counter() - t0

        t1 = time.perf_counter()
        resp_sem = geracao.gerar(q, trechos_sem, backend="ollama")
        t_ger_sem = time.perf_counter() - t1

        docs_sem = [t["doc_id"] for t in trechos_sem]
        cov_sem = _avaliar_cobertura(docs_sem, docs_a, docs_b)

        # 2. Com reescrita (Estágio 1 JevK5-Lite + Estágio 2 LLM + Estágio 3 Busca intercalada)
        t_jev0 = time.perf_counter()
        eh_comp, prob_jev = reescrita.classificar_composta(q)
        t_jev_ms = (time.perf_counter() - t_jev0) * 1000.0

        t_dec0 = time.perf_counter()
        subs = reescrita.decompor(q) if eh_comp else []
        t_decomp = (t_jev_ms / 1000.0) + (time.perf_counter() - t_dec0)

        t_b0 = time.perf_counter()
        trechos_com = indice.buscar_com_subperguntas(q, subs, k=config.TOP_K)
        t_busca_com = time.perf_counter() - t_b0

        t_g0 = time.perf_counter()
        resp_com = geracao.gerar(q, trechos_com, backend="ollama")
        t_ger_com = time.perf_counter() - t_g0

        docs_com = [t["doc_id"] for t in trechos_com]
        cov_com = _avaliar_cobertura(docs_com, docs_a, docs_b)

        item = {
            "id": cid,
            "pergunta": q,
            "jev_eh_composta": eh_comp,
            "prob_jev": prob_jev,
            "latencia_jev_ms": round(t_jev_ms, 1),
            "subperguntas": subs,
            "sem_reescrita": {
                "docs": docs_sem,
                **cov_sem,
                "tempo_busca_s": round(t_busca_sem, 3),
                "tempo_geracao_s": round(t_ger_sem, 3),
                "tempo_total_s": round(t_busca_sem + t_ger_sem, 3),
                "citacoes": len(geracao.citacoes_usadas(resp_sem, trechos_sem)),
                "valores_sem_fonte": geracao.valores_sem_fonte(resp_sem, trechos_sem),
            },
            "com_reescrita": {
                "docs": docs_com,
                **cov_com,
                "tempo_decomposicao_s": round(t_decomp, 3),
                "tempo_busca_s": round(t_busca_com, 3),
                "tempo_geracao_s": round(t_ger_com, 3),
                "tempo_total_s": round(t_decomp + t_busca_com + t_ger_com, 3),
                "citacoes": len(geracao.citacoes_usadas(resp_com, trechos_com)),
                "valores_sem_fonte": geracao.valores_sem_fonte(resp_com, trechos_com),
            },
        }
        resultados.append(item)
        print(
            f"{cid} | Jev={prob_jev:.3f} ({t_jev_ms:.0f}ms) | "
            f"Sem: {cov_sem['eixos_cobertos']}/2 ({t_busca_sem:.2f}s+{t_ger_sem:.2f}s) | "
            f"Com: {cov_com['eixos_cobertos']}/2 ({t_decomp:.2f}s+{t_busca_com:.2f}s+{t_ger_com:.2f}s)"
        )

    resumo = {
        "hardware": "MacBook Air M4 24 GB (CPU para JevK5-Lite/BGE-M3 + Ollama local qwen2.5:7b)",
        "sem_reescrita": {
            "cobertura_media_pct": round(statistics.mean(r["sem_reescrita"]["cobertura_pct"] for r in resultados), 1),
            "tempo_busca_medio_s": round(statistics.mean(r["sem_reescrita"]["tempo_busca_s"] for r in resultados), 3),
            "tempo_geracao_medio_s": round(statistics.mean(r["sem_reescrita"]["tempo_geracao_s"] for r in resultados), 2),
            "tempo_total_medio_s": round(statistics.mean(r["sem_reescrita"]["tempo_total_s"] for r in resultados), 2),
        },
        "com_reescrita": {
            "cobertura_media_pct": round(statistics.mean(r["com_reescrita"]["cobertura_pct"] for r in resultados), 1),
            "latencia_jev_media_ms": round(statistics.mean(r["latencia_jev_ms"] for r in resultados), 1),
            "tempo_decomposicao_medio_s": round(statistics.mean(r["com_reescrita"]["tempo_decomposicao_s"] for r in resultados), 2),
            "tempo_busca_medio_s": round(statistics.mean(r["com_reescrita"]["tempo_busca_s"] for r in resultados), 3),
            "tempo_geracao_medio_s": round(statistics.mean(r["com_reescrita"]["tempo_geracao_s"] for r in resultados), 2),
            "tempo_total_medio_s": round(statistics.mean(r["com_reescrita"]["tempo_total_s"] for r in resultados), 2),
        },
        "casos": resultados,
    }

    destino = config.AVALIACAO / "resultado_reescrita.json"
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nResumo salvo em", destino)
    print(json.dumps(resumo["sem_reescrita"], ensure_ascii=False))
    print(json.dumps(resumo["com_reescrita"], ensure_ascii=False))


if __name__ == "__main__":
    main()
