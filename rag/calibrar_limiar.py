"""Calibração do limiar do Estágio 1 (LiquidAI/d1-omni-600M) em um conjunto SEPARADO do benchmark.

O limiar padrão (0,50) foi herdado de outro classificador. Para o d1-omni-600M, uma pergunta composta
óbvia obteve p = 0,39 e nunca foi sinalizada. Em vez de ajustar o limiar nas perguntas do benchmark
(o que contaminaria a avaliação), calibra-se aqui em `perguntas_calibracao.jsonl`, que não compartilha
nenhuma pergunta com `perguntas_benchmark.jsonl`. Todas as perguntas passam pelo pré-filtro de
conectivos, ou seja, representam o regime em que o modelo realmente é acionado.

Uso (GPU):  python -m rag.calibrar_limiar
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .rumo_rag import config, reescrita
except ImportError:  # execução direta
    from rag.rumo_rag import config, reescrita


def escolher_limiar(probs_compostas: list[float], probs_simples: list[float]) -> dict:
    """Escolhe o limiar que maximiza a acurácia balanceada (predito composta se p >= limiar).

    Empates são resolvidos pela mediana dos limiares empatados. Função pura (testável sem modelo).
    """
    if not probs_compostas or not probs_simples:
        raise ValueError("São necessárias perguntas compostas e simples para calibrar.")

    valores = sorted(set(probs_compostas) | set(probs_simples))
    candidatos = [valores[0] - 1e-6]
    candidatos += [(a + b) / 2 for a, b in zip(valores, valores[1:])]
    candidatos.append(valores[-1] + 1e-6)

    def avaliar(limiar: float) -> tuple[float, float, float]:
        tpr = sum(p >= limiar for p in probs_compostas) / len(probs_compostas)
        tnr = sum(p < limiar for p in probs_simples) / len(probs_simples)
        return (tpr + tnr) / 2, tpr, tnr

    pontuados = [(avaliar(c), c) for c in candidatos]
    melhor = max(p[0][0] for p in pontuados)
    empatados = sorted(c for (acc, _, _), c in pontuados if acc == melhor)
    limiar = empatados[len(empatados) // 2]
    acc, tpr, tnr = avaliar(limiar)
    return {
        "limiar": round(limiar, 4),
        "acuracia_balanceada": round(acc, 4),
        "recall_compostas": round(tpr, 4),
        "especificidade_simples": round(tnr, 4),
        "separavel": tpr == 1.0 and tnr == 1.0,
    }


def carregar_calibracao(caminho: Path | str | None = None) -> list[dict]:
    caminho = Path(caminho or config.AVALIACAO / "perguntas_calibracao.jsonl")
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def calibrar(caminho: Path | str | None = None, salvar: bool = True) -> dict:
    """Calcula p(múltiplas) bruto para cada pergunta de calibração e escolhe o limiar."""
    itens = carregar_calibracao(caminho)
    for item in itens:
        item["prob_multipla"] = round(reescrita.probabilidade_multipla(item["pergunta"]), 4)

    compostas = [i["prob_multipla"] for i in itens if i["composta"]]
    simples = [i["prob_multipla"] for i in itens if not i["composta"]]
    resultado = escolher_limiar(compostas, simples)
    resultado.update(
        {
            "limiar_padrao": config.LIMIAR_COMPOSTA,
            "modelo": config.MODELO_DECISAO,
            "n_compostas": len(compostas),
            "n_simples": len(simples),
            "itens": itens,
        }
    )
    if salvar:
        destino = config.AVALIACAO / "calibracao_limiar.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def imprimir(resultado: dict) -> None:
    print(f"[Calibração] {resultado['modelo']} · {resultado['n_compostas']} compostas / {resultado['n_simples']} simples")
    for item in sorted(resultado["itens"], key=lambda i: i["prob_multipla"]):
        rotulo = "COMPOSTA" if item["composta"] else "simples "
        print(f"  p={item['prob_multipla']:.4f}  {rotulo}  {item['id']}  {item['pergunta']}")
    print(
        f"[Calibração] limiar escolhido = {resultado['limiar']} (padrão {resultado['limiar_padrao']}) · "
        f"recall compostas = {resultado['recall_compostas']:.2f} · "
        f"especificidade simples = {resultado['especificidade_simples']:.2f} · "
        f"separável = {resultado['separavel']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibra o limiar do Estágio 1 (d1-omni-600M)")
    parser.add_argument("--arquivo", default=None, help="JSONL de calibração (padrão: perguntas_calibracao.jsonl)")
    args = parser.parse_args(argv)
    imprimir(calibrar(args.arquivo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
