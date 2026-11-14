"""Script de comparação: LLM Pura vs RAG Extrativo (sem LLM) vs RAG Generativo (com LLM).

Uso:
    cd rag
    python comparativo_rag.py
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

# Evita tentativas de rede desnecessárias ao carregar o modelo de embedding local
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Adiciona diretório rag ao sys.path
RAIZ_RAG = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ_RAG))

from rumo_rag import config, geracao, indice

PERGUNTAS_TESTE = [
    {
        "id": "T1",
        "tipo": "Preço / Valor específico (Eixo RU)",
        "pergunta": "Quanto um estudante de graduação paga no almoço do RU?",
        "esperado_doc": ["F01", "F04"],
        "fato_esperado": "R$ 4,50 (Grupo III - graduação sem auxílio) ou R$ 0,00 (Grupo I - isentos)",
        "fora_da_base": False,
    },
    {
        "id": "T2",
        "tipo": "Fluxo acadêmico local (Eixo FCTE)",
        "pergunta": "Quais são os pré-requisitos de Testes de Software na FCTE?",
        "esperado_doc": ["F16"],
        "fato_esperado": "Requisitos de Software (FGA0313), com ligação indireta com MDS (FGA0312)",
        "fora_da_base": False,
    },
    {
        "id": "T3",
        "tipo": "Fora da base / Teste de Recusa (RF04)",
        "pergunta": "Qual é a senha do Wi-Fi da biblioteca da FCTE?",
        "esperado_doc": [],
        "fato_esperado": "Não encontrei essa informação nas fontes da base.",
        "fora_da_base": True,
    },
]


def testar_llm_pura(pergunta: str, modelo: str) -> dict:
    """1. LLM Pura (Zero-Shot): sem qualquer contexto ou RAG."""
    t0 = time.time()
    prompt = [
        {"role": "system", "content": "Você é um assistente acadêmico. Responda de forma concisa em até 100 palavras."},
        {"role": "user", "content": pergunta}
    ]
    corpo = {
        "model": modelo,
        "messages": prompt,
        "stream": False,
        "options": {"temperature": 0}
    }
    req = urllib.request.Request(
        f"{config.OLLAMA_URL}/api/chat",
        data=json.dumps(corpo).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resposta = json.loads(r.read())["message"]["content"].strip()
    dt = time.time() - t0

    # Extrai valores para checar alucinação
    valores = geracao.PADRAO_VALOR.findall(resposta)
    citacoes = re.findall(r"\[\d+\]", resposta)

    # Recusa semântica ampla para LLM pura (não amarrada à frase do prompt de RAG)
    padrao_recusa_pura = re.compile(
        r"(?:não (?:encontrei|possuo|tenho|disponho|sei)|não há informação|"
        r"contat(?:e|ar)|procure a|secretaria|departamento de ti)",
        re.I,
    )
    recusou = bool(padrao_recusa_pura.search(resposta)) if "senha" in pergunta.lower() else "N/A"

    return {
        "abordagem": "1. LLM Pura (Zero-Shot)",
        "tempo_s": round(dt, 2),
        "resposta": resposta,
        "qtd_citacoes": len(citacoes),
        "valores_mencionados": valores,
        "recusa_correta": recusou,
    }


def testar_rag_extrativo(pergunta: str, k: int = config.TOP_K) -> dict:
    """2. RAG sem LLM (Extrativo puro): apenas busca e seleção de trechos léxicos."""
    t0 = time.time()
    trechos = indice.buscar(pergunta, k=k)
    t_busca = time.time() - t0

    t1 = time.time()
    resposta = geracao._gerar_extrativo(pergunta, trechos)
    t_ger = time.time() - t1

    fontes = geracao.citacoes_usadas(resposta, trechos)
    # Deduplica fontes preservando a ordem
    fontes_unicas = list(dict.fromkeys(f["doc_id"] for f in fontes))
    valores_sem = geracao.valores_sem_fonte(resposta, trechos)

    recusa_aplicavel = "senha" in pergunta.lower()
    recusa_ok = ("não encontrei" in resposta.lower()) if recusa_aplicavel else "N/A"

    return {
        "abordagem": "2. RAG sem LLM (Extrativo)",
        "tempo_busca_s": round(t_busca, 2),
        "tempo_geracao_s": round(t_ger, 4),
        "tempo_total_s": round(t_busca + t_ger, 2),
        "resposta": resposta,
        "qtd_citacoes": len(fontes_unicas),
        "fontes": fontes_unicas,
        "valores_sem_fonte": valores_sem,
        "recusa_correta": recusa_ok,
    }


def testar_rag_ollama(pergunta: str, modelo: str, k: int = config.TOP_K) -> dict:
    """3. RAG com LLM (Generativo): busca no índice + síntese instruída no Ollama."""
    t0 = time.time()
    trechos = indice.buscar(pergunta, k=k)
    t_busca = time.time() - t0

    t1 = time.time()
    msgs = geracao.montar_mensagens(pergunta, trechos)
    resposta = geracao._gerar_ollama(msgs)
    t_ger = time.time() - t1

    fontes = geracao.citacoes_usadas(resposta, trechos)
    # Deduplica fontes preservando a ordem
    fontes_unicas = list(dict.fromkeys(f["doc_id"] for f in fontes))
    valores_sem = geracao.valores_sem_fonte(resposta, trechos)

    recusa_aplicavel = "senha" in pergunta.lower()
    recusa_ok = ("não encontrei" in resposta.lower()) if recusa_aplicavel else "N/A"

    return {
        "abordagem": "3. RAG com LLM (Generativo)",
        "tempo_busca_s": round(t_busca, 2),
        "tempo_geracao_s": round(t_ger, 2),
        "tempo_total_s": round(t_busca + t_ger, 2),
        "resposta": resposta,
        "qtd_citacoes": len(fontes_unicas),
        "fontes": fontes_unicas,
        "valores_sem_fonte": valores_sem,
        "recusa_correta": recusa_ok,
    }


def main():
    modelo_ollama = os.getenv("RUMO_OLLAMA_MODEL", "qwen2.5:7b")
    print("=" * 80)
    print("BENCHMARK COMPARATIVO: LLM PURA vs RAG EXTRATIVO vs RAG GENERATIVO")
    print(f"Modelo Ollama configurado: {modelo_ollama}")
    print(f"URL Ollama: {config.OLLAMA_URL}")
    print("=" * 80)

    # Checa se o Ollama está acessível
    ollama_ok = False
    try:
        req = urllib.request.Request(f"{config.OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            ollama_ok = r.status == 200
    except Exception:
        ollama_ok = False

    if not ollama_ok:
        print("\n[AVISO] Não foi possível conectar ao Ollama em http://localhost:11434.")
        print("Certifique-se de que o Ollama está aberto ('ollama serve') para rodar os testes generativos.\n")

    # Warmup do modelo de embeddings para que a latência de inicialização (~5s)
    # não seja cobrada indevidamente na primeira pergunta (T1) do extrativo
    try:
        indice.embed_consulta("warmup")
    except Exception:
        pass

    relatorio = []

    for caso in PERGUNTAS_TESTE:
        print(f"\n>>> TESTANDO CASO [{caso['id']}]: {caso['tipo']}")
        print(f"Pergunta: \"{caso['pergunta']}\"")
        print(f"Fato Esperado: {caso['fato_esperado']}\n")

        # 1. RAG Extrativo (Sempre funciona, independente do Ollama)
        print("... Executando 2. RAG Extrativo (sem LLM)")
        res_extrativo = testar_rag_extrativo(caso["pergunta"])

        res_pura = None
        res_rag = None

        if ollama_ok:
            print("... Executando 1. LLM Pura (Zero-Shot)")
            try:
                res_pura = testar_llm_pura(caso["pergunta"], modelo_ollama)
            except Exception as e:
                print(f"    Erro no teste LLM Pura: {e}")

            print("... Executando 3. RAG com LLM (Generativo)")
            try:
                res_rag = testar_rag_ollama(caso["pergunta"], modelo_ollama)
            except Exception as e:
                print(f"    Erro no teste RAG LLM: {e}")

        # Exibe respostas comparadas
        print("\n--- RESPOSTAS OBTIDAS ---")
        if res_pura:
            print(f"[LLM PURA ({res_pura['tempo_s']}s)]:\n{res_pura['resposta']}")
            print(f"  Valores citados de cabeça: {res_pura['valores_mencionados']}")
            print(f"  Citações formais: {res_pura['qtd_citacoes']}")
        else:
            print("[LLM PURA]: Não executado (Ollama offline)")

        print(f"\n[RAG EXTRATIVO ({res_extrativo['tempo_total_s']}s)]:\n{res_extrativo['resposta']}")
        print(f"  Fontes usadas: {res_extrativo['fontes']}")
        print(f"  Valores sem fonte (alucinações): {res_extrativo['valores_sem_fonte']}")

        if res_rag:
            print(f"\n[RAG GENERATIVO ({res_rag['tempo_total_s']}s)]:\n{res_rag['resposta']}")
            print(f"  Fontes citadas: {res_rag['fontes']}")
            print(f"  Valores sem fonte (alucinações): {res_rag['valores_sem_fonte']}")
        else:
            print("[RAG GENERATIVO]: Não executado (Ollama offline)")

        print("-" * 80)
        relatorio.append({
            "caso": caso,
            "pura": res_pura,
            "extrativo": res_extrativo,
            "rag": res_rag
        })

    # Resumo final em tabela
    print("\n" + "=" * 80)
    print("RESUMO COMPARATIVO DE MÉTRICAS")
    print("=" * 80)
    print(f"{'Caso':<6} | {'Abordagem':<22} | {'Tempo':<8} | {'Fontes':<8} | {'Alucinações':<12} | {'Recusa'}")
    print("-" * 75)
    for r in relatorio:
        cid = r["caso"]["id"]
        recusa_pura = str(r["pura"]["recusa_correta"]) if r["pura"] else "N/A"
        recusa_ext = str(r["extrativo"]["recusa_correta"])
        recusa_rag = str(r["rag"]["recusa_correta"]) if r["rag"] else "N/A"
        if r["pura"]:
            print(f"{cid:<6} | {'1. LLM Pura':<22} | {str(r['pura']['tempo_s'])+'s':<8} | {r['pura']['qtd_citacoes']:<8} | {len(r['pura']['valores_mencionados']):<12} | {recusa_pura}")
        print(f"{cid:<6} | {'2. RAG Extrativo':<22} | {str(r['extrativo']['tempo_total_s'])+'s':<8} | {r['extrativo']['qtd_citacoes']:<8} | {len(r['extrativo']['valores_sem_fonte']):<12} | {recusa_ext}")
        if r["rag"]:
            print(f"{cid:<6} | {'3. RAG Generativo':<22} | {str(r['rag']['tempo_total_s'])+'s':<8} | {r['rag']['qtd_citacoes']:<8} | {len(r['rag']['valores_sem_fonte']):<12} | {recusa_rag}")
        print("-" * 75)


if __name__ == "__main__":
    main()
