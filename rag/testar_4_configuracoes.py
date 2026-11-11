"""Suíte de Testes: 4 Configurações para o RUmo (Critério de Pronto).

Configurações avaliadas:
  1. Configuração 1: LLM Pura (Zero-shot, sem RAG)
  2. Configuração 2: RAG Extrativo (Sem LLM)
  3. Configuração 3: RAG Generativo Simples (k=3, contexto reduzido)
  4. Configuração 4: RAG Generativo Híbrido Completo (k=5, metadados completos + verificador)
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

RAIZ_RAG = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ_RAG))

from rumo_rag import config, geracao, indice

PERGUNTAS = [
    {
        "id": "P1",
        "tipo": "Fato Numérico / Preço (Eixo RU)",
        "pergunta": "Quanto um estudante de graduação paga no almoço do RU?",
        "gabarito": "R$ 6,10 (Grupo II - regular) ou R$ 0,00 (Grupo I - isentos/baixa renda)",
        "doc_esperado": "F01 / F04",
    },
    {
        "id": "P2",
        "tipo": "Regra Acadêmica Local (Eixo Fluxo)",
        "pergunta": "Quais são os pré-requisitos de Testes de Software na FCTE?",
        "gabarito": "Requisitos de Software (FGA0313), com relação indireta com MDS",
        "doc_esperado": "F16",
    },
    {
        "id": "P3",
        "tipo": "Pergunta Fora da Base (Regra RF04)",
        "pergunta": "Qual é a senha do Wi-Fi da biblioteca da FCTE?",
        "gabarito": "Não encontrei essa informação nas fontes da base.",
        "doc_esperado": "NENHUM (Recusa obrigatória)",
    },
]


def checar_ollama() -> bool:
    try:
        req = urllib.request.Request(f"{config.OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def rodar_llm_pura(pergunta: str, modelo: str) -> dict:
    """Configuração 1: LLM Pura (Zero-shot)"""
    t0 = time.time()
    prompt = [
        {"role": "system", "content": "Você é um assistente acadêmico da UnB. Responda em até 80 palavras de forma direta."},
        {"role": "user", "content": pergunta}
    ]
    corpo = {"model": modelo, "messages": prompt, "stream": False, "options": {"temperature": 0}}
    req = urllib.request.Request(f"{config.OLLAMA_URL}/api/chat", data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())["message"]["content"].strip()
    dt = time.time() - t0

    citacoes = re.findall(r"\[\d+\]", resp)
    valores = geracao.PADRAO_VALOR.findall(resp)
    recusou = "não encontrei" in resp.lower() or "não possuo" in resp.lower()

    return {
        "nome": "1. LLM Pura",
        "resposta": resp,
        "tempo_s": round(dt, 2),
        "citacoes": len(citacoes),
        "valores_inventados": valores,
        "recusa_adequada": recusou,
    }


def rodar_rag_extrativo(pergunta: str, k: int = 5) -> dict:
    """Configuração 2: RAG Extrativo (Sem LLM)"""
    t0 = time.time()
    trechos = indice.buscar(pergunta, k=k)
    t_busca = time.time() - t0

    t1 = time.time()
    resp = geracao._gerar_extrativo(pergunta, trechos)
    t_ger = time.time() - t1

    fontes = geracao.citacoes_usadas(resp, trechos)
    sem_fonte = geracao.valores_sem_fonte(resp, trechos)
    recusou = "não encontrei essa informação" in resp.lower()

    return {
        "nome": "2. RAG Extrativo (Sem LLM)",
        "resposta": resp,
        "tempo_s": round(t_busca + t_ger, 2),
        "citacoes": len(fontes),
        "valores_inventados": sem_fonte,
        "recusa_adequada": recusou,
    }


def rodar_rag_generativo(pergunta: str, modelo: str, k: int, nome: str) -> dict:
    """Configurações 3 e 4: RAG Generativo com variação de contexto k"""
    t0 = time.time()
    trechos = indice.buscar(pergunta, k=k)
    t_busca = time.time() - t0

    t1 = time.time()
    msgs = geracao.montar_mensagens(pergunta, trechos)
    resp = geracao._gerar_ollama(msgs)
    t_ger = time.time() - t1

    fontes = geracao.citacoes_usadas(resp, trechos)
    sem_fonte = geracao.valores_sem_fonte(resp, trechos)
    recusou = "não encontrei essa informação" in resp.lower()

    return {
        "nome": nome,
        "resposta": resp,
        "tempo_s": round(t_busca + t_ger, 2),
        "citacoes": len(fontes),
        "valores_inventados": sem_fonte,
        "recusa_adequada": recusou,
    }


def main():
    modelo = os.getenv("RUMO_OLLAMA_MODEL", "qwen2.5:7b")
    ollama_ativo = checar_ollama()

    print("=" * 80)
    print("BATERIA DE TESTES: 4 CONFIGURAÇÕES PARA O PRODUTO RUMO")
    print(f"Modelo Ollama: {modelo} | Ollama Online: {'SIM' if ollama_ativo else 'NÃO (verifique ollama serve)'}")
    print("=" * 80)

    if not ollama_ativo:
        print("\n[ERRO CRÍTICO] O Ollama não está respondendo em http://localhost:11434.")
        print("Para rodar o teste completo das 4 configurações, abra o Ollama no terminal.")
        return

    resultados_tabela = []

    for caso in PERGUNTAS:
        p = caso["pergunta"]
        print(f"\n" + "#" * 80)
        print(f"CASO [{caso['id']}]: {caso['tipo']}")
        print(f"Pergunta: \"{p}\"")
        print(f"Gabarito Oficial: {caso['gabarito']}")
        print("#" * 80)

        # Configuração 1: LLM Pura
        print("\n[Rodando 1. LLM Pura (Zero-shot)]...")
        c1 = rodar_llm_pura(p, modelo)
        print(f"-> Resposta:\n{c1['resposta']}")
        print(f"-> Tempo: {c1['tempo_s']}s | Citações: {c1['citacoes']} | Valores alucinados/sem base: {c1['valores_inventados']}")

        # Configuração 2: RAG Extrativo
        print("\n[Rodando 2. RAG Extrativo (Sem LLM)]...")
        c2 = rodar_rag_extrativo(p, k=5)
        print(f"-> Resposta:\n{c2['resposta']}")
        print(f"-> Tempo: {c2['tempo_s']}s | Citações: {c2['citacoes']} | Valores sem base: {c2['valores_inventados']}")

        # Configuração 3: RAG Generativo Simples (k=3)
        print("\n[Rodando 3. RAG Generativo Simples (k=3)]...")
        c3 = rodar_rag_generativo(p, modelo, k=3, nome="3. RAG Generativo (k=3)")
        print(f"-> Resposta:\n{c3['resposta']}")
        print(f"-> Tempo: {c3['tempo_s']}s | Citações: {c3['citacoes']} | Valores sem base: {c3['valores_inventados']}")

        # Configuração 4: RAG Generativo Completo (k=5)
        print("\n[Rodando 4. RAG Generativo Completo (k=5)]...")
        c4 = rodar_rag_generativo(p, modelo, k=5, nome="4. RAG Generativo Completo (k=5)")
        print(f"-> Resposta:\n{c4['resposta']}")
        print(f"-> Tempo: {c4['tempo_s']}s | Citações: {c4['citacoes']} | Valores sem base: {c4['valores_inventados']}")

        for conf in [c1, c2, c3, c4]:
            recusa_valida = conf["recusa_adequada"] if caso["id"] == "P3" else "N/A"
            resultados_tabela.append({
                "caso": caso["id"],
                "tipo": caso["tipo"],
                "config": conf["nome"],
                "tempo": f"{conf['tempo_s']}s",
                "citacoes": conf["citacoes"],
                "alucinacoes": len(conf["valores_inventados"]),
                "recusa": recusa_valida
            })

    # Imprime tabela comparativa consolidada
    print("\n" + "=" * 80)
    print("TABELA COMPARATIVA CONSOLIDADA (CRITÉRIO DE PRONTO)")
    print("=" * 80)
    print(f"{'Caso':<5} | {'Configuração':<32} | {'Tempo':<8} | {'Citações':<9} | {'Alucinações':<12} | {'Recusa RF04'}")
    print("-" * 80)
    for r in resultados_tabela:
        print(f"{r['caso']:<5} | {r['config']:<32} | {r['tempo']:<8} | {r['citacoes']:<9} | {r['alucinacoes']:<12} | {str(r['recusa']):<10}")
        if "Completo" in r['config']:
            print("-" * 80)


if __name__ == "__main__":
    main()
