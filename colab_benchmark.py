#!/usr/bin/env python3
"""Script de execução autônoma do benchmark no Google Colab com GPU (A100 / L4 / H100 / T4).

Este script:
1. Detecta GPU disponível e memória VRAM total (torch.cuda).
2. Auto-sintoniza RUMO_HF_4BIT ('0' se VRAM >= 20GB [A100/L4], '1' se VRAM < 20GB [T4]).
3. Carrega opcionalmente HF_TOKEN de google.colab.userdata ou variável de ambiente.
4. Verifica e garante a indexação no ChromaDB a partir de rag/dados/chunks.jsonl.
5. Pré-aquece os modelos neurais na GPU (LiquidAI/d1-omni-600M e Qwen/Qwen2.5-7B-Instruct).
6. Executa o benchmark comparativo Sem RAG × Com RAG (rag.benchmark).
7. Audita rigorosamente a ausência de métricas de latência (Requisito R3).
8. Salva os resultados consolidados em JSON e Markdown.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao sys.path para importação de pacotes internos
RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def carregar_token_hf() -> str | None:
    """Tenta recuperar o token do Hugging Face de Secrets do Colab ou do ambiente."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        try:
            from google.colab import userdata
            token = userdata.get("HF_TOKEN") or userdata.get("HUGGING_FACE_HUB_TOKEN")
        except Exception:
            token = None
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token
        print("[Auth] Token do Hugging Face configurado via ambiente/Colab Secrets.")
    return token


def detectar_gpu_e_configurar_vram() -> dict:
    """Detecta GPU e auto-configura precisão / quantização conforme VRAM disponível."""
    info = {
        "cuda_disponivel": False,
        "dispositivo": "CPU",
        "vram_gb": 0.0,
        "bf16_suportado": False,
        "4bit": True,
    }

    try:
        import torch

        if torch.cuda.is_available():
            info["cuda_disponivel"] = True
            info["dispositivo"] = torch.cuda.get_device_name(0)
            propriedades = torch.cuda.get_device_properties(0)
            info["vram_gb"] = round(propriedades.total_memory / (1024 ** 3), 2)
            info["bf16_suportado"] = torch.cuda.is_bf16_supported()

            # Auto-tune RUMO_HF_4BIT se não especificado explicitamente
            if "RUMO_HF_4BIT" not in os.environ:
                # GPUs potentes (A100, L4, H100 com >= 20GB): modo full precision FP16/BF16
                if info["vram_gb"] >= 20.0:
                    os.environ["RUMO_HF_4BIT"] = "0"
                    info["4bit"] = False
                else:
                    os.environ["RUMO_HF_4BIT"] = "1"
                    info["4bit"] = True
            else:
                info["4bit"] = os.environ["RUMO_HF_4BIT"] == "1"

            modo_str = "4-bit (BitsAndBytes NF4)" if info["4bit"] else "FP16/BF16 (Precisão Total)"
            print(f"[Hardware] GPU Detectada: {info['dispositivo']} · VRAM: {info['vram_gb']} GB")
            print(f"[Hardware] Modo de Quantização Selecionado: {modo_str} (RUMO_HF_4BIT={os.environ['RUMO_HF_4BIT']})")
            return info
    except Exception:
        pass

    print("[Hardware] Nenhuma GPU CUDA ativa detectada. Execução configurada para CPU.")
    if "RUMO_HF_4BIT" not in os.environ:
        os.environ["RUMO_HF_4BIT"] = "0"

    return info


def garantir_indexacao_base(dry_run: bool = False) -> int:
    """Verifica se a coleção ChromaDB possui trechos e indexa a partir de chunks.jsonl se vazia."""
    if dry_run:
        print("[Base] Modo dry-run ativo: verificação de ChromaDB ignorada.")
        return 0

    from rag.rumo_rag import config, indice

    caminho_chunks = config.CHUNKS
    if not caminho_chunks.exists():
        caminho_alternativo = RAIZ / "rag" / "dados" / "chunks.jsonl"
        if caminho_alternativo.exists():
            caminho_chunks = caminho_alternativo

    try:
        col = indice.colecao()
        contagem = col.count()
    except Exception as e:
        print(f"[Base] Erro ao conectar ao ChromaDB: {e}. Tentando inicializar...")
        contagem = 0

    if contagem == 0:
        print("[Base] Coleção ChromaDB vazia. Iniciando indexação a partir de chunks.jsonl...")
        if not caminho_chunks.exists():
            raise FileNotFoundError(f"Arquivo de chunks não encontrado em: {caminho_chunks}")

        chunks = []
        with open(caminho_chunks, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    chunks.append(json.loads(linha))

        print(f"[Base] Carregando {len(chunks)} chunks de {caminho_chunks} para o ChromaDB...")
        indice.indexar(chunks)
        total_indexado = indice.colecao().count()
        print(f"[Base] Indexação concluída com sucesso! Total na coleção: {total_indexado} chunks.")
        return total_indexado

    print(f"[Base] Coleção ChromaDB pronta com {contagem} chunks já indexados.")
    return contagem


def pre_aquecer_modelos(backend: str = "hf", dry_run: bool = False) -> None:
    """Carrega os modelos neurais na memória da GPU para evitar overhead inicial na primeira query."""
    if dry_run or backend != "hf":
        return

    try:
        import torch
        if not torch.cuda.is_available():
            return
    except Exception:
        return

    print("\n[Pré-aquecimento] Carregando modelos neurais na VRAM da GPU...")
    from rag.rumo_rag import config, geracao, reescrita

    # 1. Classificador System-1 (LiquidAI/d1-omni-600M)
    try:
        print(f"  [1/2] Pré-aquecendo classificador System-1 ({config.MODELO_DECISAO})...")
        reescrita._carregar_decisor()
        # Modo estrito: se o Estágio 1 falhar, o erro aparece aqui em vez de virar "pergunta simples".
        os.environ["RUMO_STRICT_REWRITE"] = "1"
        pergunta_teste = "Qual o valor do almoço para estudante e quais os horários do jantar no Gama?"
        teste_cls, prob = reescrita.classificar_composta(pergunta_teste)
        print(f"        Classificador operacional na GPU (pergunta composta de teste: eh_composta={teste_cls}, p={prob:.4f}).")
        if not teste_cls:
            print("        [ALERTA] O classificador NÃO sinalizou a pergunta composta de teste; "
                  f"revise RUMO_DECISION_THRESHOLD (atual={config.LIMIAR_COMPOSTA}).")
    except Exception:
        import traceback
        print("        [ERRO] Falha no Estágio 1 (classificador d1-omni-600M):")
        traceback.print_exc()

    # 2. Gerador e Decompositor (Qwen2.5-7B)
    try:
        print(f"  [2/2] Pré-aquecendo modelo generativo ({config.MODELO_HF})...")
        tok, modelo = geracao._hf()
        dispositivo_modelo = getattr(modelo, "device", "gpu")
        print(f"        Modelo generativo carregado com sucesso no dispositivo: {dispositivo_modelo}.")
    except Exception as e:
        print(f"        [Aviso] Falha ao pré-aquecer modelo generativo: {e}")


def executar_colab_benchmark(
    backend: str = "hf",
    dry_run: bool = False,
    saida_formato: str = "md",
    arquivo_saida: str | Path | None = None,
    k: int = 5,
) -> dict:
    """Executa o pipeline completo de benchmark adaptado para Google Colab com GPU."""
    # 1. Configura autenticação opcional
    carregar_token_hf()

    # 2. Detecta GPU e configura VRAM
    detectar_gpu_e_configurar_vram()

    # 3. Garante que os dados estão indexados
    garantir_indexacao_base(dry_run=dry_run)

    # 4. Pré-aquece modelos na GPU
    pre_aquecer_modelos(backend=backend, dry_run=dry_run)

    # 5. Executa benchmark
    print(f"\n[Benchmark] Iniciando avaliação comparativa (backend={backend}, dry_run={dry_run})...")
    from rag.benchmark import (
        executar_benchmark,
        formatar_resultados_markdown,
        verificar_ausencia_latencia,
    )

    dados = executar_benchmark(backend=backend, dry_run=dry_run, k=k)

    # 6. Auditoria estrita de zero latência (Requisito R3)
    verificar_ausencia_latencia(dados)
    print("[Auditoria R3] Verificação estrita de Zero Latência aprovada com 100% de conformidade.")

    # 7. Persistência dos resultados
    caminho_json = Path(arquivo_saida or (RAIZ / "rag" / "avaliacao" / "resultado_benchmark_colab.json"))
    caminho_md = caminho_json.with_suffix(".md")

    caminho_json.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(dados, ensure_ascii=False, indent=2)
    caminho_json.write_text(json_str, encoding="utf-8")
    print(f"[Exportação] Resultados completos em JSON salvos em: {caminho_json}")

    md_str = formatar_resultados_markdown(dados)
    caminho_md.write_text(md_str, encoding="utf-8")
    print(f"[Exportação] Relatório executivo em Markdown salvo em: {caminho_md}")

    # Salva também os artefatos de granularidade para as issues #17, #28 e #29
    caminho_comparativas = RAIZ / "rag" / "avaliacao" / "respostas_comparativas.json"
    caminho_fidelidade = RAIZ / "rag" / "avaliacao" / "resultado_fidelidade.json"

    pareadas = {}
    for r in dados.get("resultados", []):
        qid = r.get("id")
        regime = r.get("regime")
        if qid not in pareadas:
            pareadas[qid] = {
                "id": qid,
                "pergunta": r.get("pergunta"),
                "tipo": r.get("tipo"),
                "eixo": r.get("eixo"),
                "tem_base": r.get("tem_base"),
            }
        pareadas[qid][regime] = {
            "resposta": r.get("resposta"),
            "subperguntas": r.get("subperguntas", []),
            "fontes_citadas": r.get("fontes_citadas", []),
            "valores_sem_fonte": r.get("valores_sem_fonte", []),
            "citacao_valida": r.get("citacao_valida"),
            "fidelidade_factual": r.get("fidelidade_factual"),
            "rouge_l": r.get("rouge_l"),
        }
    caminho_comparativas.write_text(json.dumps(list(pareadas.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Exportação] Respostas comparativas pareadas salvas em: {caminho_comparativas}")

    caminho_fidelidade.write_text(json.dumps(dados.get("metricas_consolidadas", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Exportação] Métricas consolidadas de fidelidade salvas em: {caminho_fidelidade}")

    # 8. Saída solicitada para stdout
    if saida_formato == "json":
        print(json_str)
    else:
        print("\n" + md_str)

    return dados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execução do Benchmark RUmo RAG no Google Colab com GPU (Zero Latência)"
    )
    parser.add_argument(
        "--backend",
        default="hf",
        choices=["hf", "ollama", "openai", "extrativo", "auto"],
        help="Backend de inferência do LLM (padrão: hf para HuggingFace em GPU)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execução simulada e determinística para validação imediata do fluxo sem GPU",
    )
    parser.add_argument(
        "--saida",
        choices=["md", "json"],
        default="md",
        help="Formato de exibição dos resultados no terminal (padrão: md)",
    )
    parser.add_argument(
        "--arquivo-saida",
        type=str,
        default=None,
        help="Caminho para o arquivo JSON de destino (padrão: rag/avaliacao/resultado_benchmark_colab.json)",
    )
    parser.add_argument(
        "-k",
        type=int,
        default=5,
        help="Quantidade de trechos recuperados por consulta (padrão: 5)",
    )

    args = parser.parse_args(argv)
    executar_colab_benchmark(
        backend=args.backend,
        dry_run=args.dry_run,
        saida_formato=args.saida,
        arquivo_saida=args.arquivo_saida,
        k=args.k,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
