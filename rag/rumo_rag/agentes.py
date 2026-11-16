"""Camada de agentes especializados, validador factual, sintetizador e orquestrador.

Arquitetura multiagentes do RUmo (Épico #37, preparada para evolução em #40 e #41):
- AgenteRU: especialista no eixo Restaurante Universitário (eixo="ru").
- AgenteFluxo: especialista no eixo Fluxo de disciplinas da FCTE/UnB (eixo="fluxo").
- AgenteValidador: confere aderência factual (valores_sem_fonte e citações RN-02) e
  devolve ao Sintetizador respostas reprovadas para reparo ou sinalização.
- Sintetizador: trata devoluções do validador e compõe a resposta final mantendo os
  índices [n] isolados por parte (regra contratual de rastreabilidade).
- Orquestrador: classifica/decompõe via `reescrita.py`, roteia por domínio, executa em
  paralelo via ThreadPoolExecutor e garante degradação elegante em falhas.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
import os
import re
import threading
import time

from . import config, geracao, indice, reescrita

# Protege inicialização e consultas no ChromaDB/BM25 (RustBindingsAPI não é thread-safe)
_LOCK_BUSCA = threading.Lock()

_TERMOS_RU = re.compile(
    r"\b(?:"
    r"ru|restaurante(?:\s+universit[aá]rio)?|almo[cç]o|jantar|caf[eé](?:\s+da\s+manh[aã])?|"
    r"refei[cç][aã]o|refei[cç][oõ]es|card[aá]pio|prato|vegetariano|vegetariana|vegano|vegana|"
    r"alerg[eê]nicos?|gl[uú]ten|lactose|aux[ií]lio\s+alimenta[cç][aã]o|pnaes|"
    r"grupo\s+(?:i{1,3}|iv)|isento|isen[cç][aã]o|bandej[aã]o"
    r")\b",
    re.IGNORECASE,
)

_TERMOS_FLUXO = re.compile(
    r"\b(?:"
    r"fluxo|fluxograma|disciplina|disciplinas|mat[eé]ria|mat[eé]rias|"
    r"pr[eé]-?requisitos?|requisito|cr[eé]ditos?|semestre|semestres|grade|matriz|curricular|"
    r"ppc|curso|cursos|engenharia|software|aeroespacial|automotiva|eletr[oô]nica|energia|"
    r"biom[eé]dica|ppgeb|mestrado|matr[ií]cula|trancamento|sigaa|ira|est[aá]gio|tcc|"
    r"optativa|obrigat[oó]ria|abi|c[aá]lculo|f[ií]sica|testes\s+de\s+software|termodin[aâ]mica|"
    r"[a-z]{2,4}\d{3,4}"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class RespostaAgente:
    """Resultado produzido por um agente especialista para uma subpergunta."""

    agente: str
    nome_agente: str
    subpergunta: str
    resposta: str
    trechos_recuperados: list[dict] = field(default_factory=list)
    fontes_citadas: list[dict] = field(default_factory=list)
    tempo_busca_s: float = 0.0
    tempo_geracao_s: float = 0.0
    tempo_total_s: float = 0.0
    erro: str | None = None
    validacao: dict | None = None


@dataclass
class ResultadoValidacao:
    """Parecer factual emitido pelo AgenteValidador sobre a saída de um agente."""

    aprovado: bool
    valores_sem_fonte: list[str]
    sem_citacao: bool
    eh_recusa: bool
    motivos: list[str]
    acao_recomendada: str


class AgenteBase:
    """Estrutura base para agentes de domínio conectados ao índice e à geração."""

    id_agente: str = "base"
    nome: str = "Agente Base"
    eixo: str | None = None
    eixo_apoio: str | None = "apoio"

    def buscar_contexto(self, subpergunta: str, k: int = config.TOP_K) -> list[dict]:
        """Recupera os chunks mais relevantes no eixo do agente (com fallback em apoio se vazio)."""
        with _LOCK_BUSCA:
            trechos = indice._buscar_simples(subpergunta, k=k, modo=config.BUSCA, eixo=self.eixo)
            if not trechos and self.eixo_apoio and self.eixo != self.eixo_apoio:
                trechos = indice._buscar_simples(subpergunta, k=k, modo=config.BUSCA, eixo=self.eixo_apoio)
        return trechos

    def gerar_resposta(
        self, subpergunta: str, trechos: list[dict], backend: str = config.BACKEND
    ) -> str:
        """Gera a resposta fundamentada apenas nos trechos recuperados pelo agente."""
        return geracao.gerar(subpergunta, trechos, backend=backend)

    def responder(
        self, subpergunta: str, k: int = config.TOP_K, backend: str = config.BACKEND
    ) -> RespostaAgente:
        """Executa busca + geração e devolve RespostaAgente com citações [n] locais."""
        t0 = time.monotonic()
        trechos = self.buscar_contexto(subpergunta, k=k)
        t1 = time.monotonic()
        resposta = self.gerar_resposta(subpergunta, trechos, backend=backend)
        t2 = time.monotonic()
        fontes = geracao.citacoes_usadas(resposta, trechos)
        return RespostaAgente(
            agente=self.id_agente,
            nome_agente=self.nome,
            subpergunta=subpergunta,
            resposta=resposta,
            trechos_recuperados=[_resumir_trecho(t) for t in trechos],
            fontes_citadas=fontes,
            tempo_busca_s=round(t1 - t0, 3),
            tempo_geracao_s=round(t2 - t1, 3),
            tempo_total_s=round(t2 - t0, 3),
        )


class AgenteRU(AgenteBase):
    """Agente especialista em Restaurante Universitário (preços, cardápio, acesso, auxílio)."""

    id_agente = "ru"
    nome = "Agente RU"
    eixo = "ru"


class AgenteFluxo(AgenteBase):
    """Agente especialista em fluxo de disciplinas, pré-requisitos, PPCs e normas da FCTE."""

    id_agente = "fluxo"
    nome = "Agente Fluxo"
    eixo = "fluxo"


class AgenteValidador:
    """Terceiro agente: verifica fidelidade factual e citações e devolve ao Sintetizador se reprovar."""

    id_agente = "validador"
    nome = "Agente Validador"

    def validar(self, item: RespostaAgente) -> ResultadoValidacao:
        """Confere aderência da resposta aos trechos locais do agente."""
        if item.erro:
            return ResultadoValidacao(
                aprovado=False,
                valores_sem_fonte=[],
                sem_citacao=False,
                eh_recusa=False,
                motivos=[f"Falha na execução do agente: {item.erro}"],
                acao_recomendada="devolver_ao_sintetizador",
            )

        trechos = item.trechos_recuperados or []
        valores = geracao.valores_sem_fonte(item.resposta, trechos)
        sem_cit = geracao.resposta_sem_citacao(item.resposta, trechos)
        recusa = geracao.eh_recusa(item.resposta)

        motivos: list[str] = []
        if valores:
            motivos.append(f"Valores sem respaldo nos trechos: {', '.join(valores)}")
        if sem_cit:
            motivos.append("Resposta afirmativa sem citação [n] (RN-02)")

        aprovado = not motivos
        return ResultadoValidacao(
            aprovado=aprovado,
            valores_sem_fonte=valores,
            sem_citacao=sem_cit,
            eh_recusa=recusa,
            motivos=motivos,
            acao_recomendada="aprovar" if aprovado else "devolver_ao_sintetizador",
        )


class Sintetizador:
    """Trata devoluções do AgenteValidador e compõe a saída sem misturar índices [n]."""

    def processar_devolucao(
        self,
        item: RespostaAgente,
        validacao: ResultadoValidacao,
        backend: str,
    ) -> tuple[RespostaAgente, dict]:
        """Executa ação corretiva quando o AgenteValidador reprova uma resposta parcial."""
        evento: dict = {
            "agente": item.agente,
            "nome_agente": item.nome_agente,
            "motivos_reprovacao": list(validacao.motivos),
            "acao": "sinalizacao_factual",
        }

        if item.erro:
            return item, evento

        trechos = item.trechos_recuperados or []
        if backend != "extrativo" and trechos:
            nova_resp = geracao.gerar(item.subpergunta, trechos, backend="extrativo")
            item.resposta = nova_resp
            item.fontes_citadas = geracao.citacoes_usadas(nova_resp, trechos)
            evento["acao"] = "fallback_extrativo"
            return item, evento

        if not trechos:
            item.resposta = geracao.RECUSA
            item.fontes_citadas = []
            evento["acao"] = "recusa_sem_trechos"
            return item, evento

        aviso = "; ".join(validacao.motivos)
        item.resposta = f"{item.resposta}\n[Aviso do {AgenteValidador.nome}: {aviso}]"
        evento["acao"] = "sinalizacao_factual"
        return item, evento

    def compor(self, pergunta: str, partes: list[RespostaAgente]) -> dict:
        """Junta as respostas dos agentes mantendo os índices [n] e fontes isolados por parte."""
        blocos_texto: list[str] = []
        avisos: list[str] = []
        trechos_agregados: list[dict] = []
        fontes_agregadas: list[dict] = []
        valores_sem_fonte_geral: list[str] = []
        sem_citacao_geral = False
        degradado = False

        mult = len(partes) > 1 or any(p.erro for p in partes)
        for parte in partes:
            if parte.erro:
                degradado = True
                aviso = f"⚠ Aviso ({parte.nome_agente}): não foi possível obter esta parte da resposta ({parte.erro})."
                avisos.append(aviso)
                blocos_texto.append(f"[{parte.nome_agente}] {parte.subpergunta}\n{aviso}")
                continue

            if mult:
                blocos_texto.append(f"[{parte.nome_agente}] {parte.subpergunta}\n{parte.resposta}")
            else:
                blocos_texto.append(parte.resposta)

            val = parte.validacao or {}
            if val.get("indisponivel"):
                degradado = True
                avisos.extend(val.get("motivos", []))
            for v in val.get("valores_sem_fonte", []):
                if v not in valores_sem_fonte_geral:
                    valores_sem_fonte_geral.append(v)
            if val.get("sem_citacao"):
                sem_citacao_geral = True

            for t in parte.trechos_recuperados:
                trecho_com_agente = dict(t)
                trecho_com_agente["agente"] = parte.agente
                trechos_agregados.append(trecho_com_agente)

            for f in parte.fontes_citadas:
                fonte_com_agente = dict(f)
                fonte_com_agente["agente"] = parte.agente
                fonte_com_agente["subpergunta"] = parte.subpergunta
                fontes_agregadas.append(fonte_com_agente)

        resposta_final = "\n\n".join(blocos_texto) if blocos_texto else geracao.RECUSA
        return {
            "resposta": resposta_final,
            "partes": [asdict(p) for p in partes],
            "fontes_citadas": fontes_agregadas,
            "trechos_recuperados": trechos_agregados,
            "valores_sem_fonte": valores_sem_fonte_geral,
            "sem_citacao": sem_citacao_geral,
            "degradado": degradado,
            "avisos": avisos,
            "tempo_busca_s": round(sum(p.tempo_busca_s for p in partes), 2),
            "tempo_geracao_s": round(sum(p.tempo_geracao_s for p in partes), 2),
        }


def rotear_subpergunta(
    subpergunta: str,
    eixo_sugerido: str | None = None,
    usar_d1_fallback: bool = True,
) -> list[str]:
    """Roteamento híbrido: Teste 1 (eixo do LLM) -> Regex rápido -> Teste 2 (d1-omni quando ambíguo)."""
    eixo_norm = (eixo_sugerido or "").strip().lower()
    if eixo_norm in ("ru", "fluxo"):
        return [eixo_norm]
    if eixo_norm == "ambos":
        return ["ru", "fluxo"]

    casa_ru = bool(_TERMOS_RU.search(subpergunta))
    casa_fluxo = bool(_TERMOS_FLUXO.search(subpergunta))
    if casa_ru and not casa_fluxo:
        return ["ru"]
    if casa_fluxo and not casa_ru:
        return ["fluxo"]
    if casa_ru and casa_fluxo:
        return ["ru", "fluxo"]
    if usar_d1_fallback:
        return reescrita.classificar_dominio_d1(subpergunta)
    return ["ru", "fluxo"]


def _resumir_trecho(t: dict) -> dict:
    campos = ("chunk_id", "doc_id", "titulo", "orgao", "pagina", "secao", "similaridade", "nota_rrf", "url", "texto")
    return {k: t.get(k) for k in campos}


class Orquestrador:
    """Coordena decomposição, roteamento, execução paralela, validação factual e síntese."""

    def __init__(
        self,
        agente_ru: AgenteBase | None = None,
        agente_fluxo: AgenteBase | None = None,
        validador: AgenteValidador | None = None,
        sintetizador: Sintetizador | None = None,
    ):
        self.agentes: dict[str, AgenteBase] = {
            "ru": agente_ru or AgenteRU(),
            "fluxo": agente_fluxo or AgenteFluxo(),
        }
        self.validador = validador or AgenteValidador()
        self.sintetizador = sintetizador or Sintetizador()

    def executar(
        self,
        pergunta: str,
        backend: str = config.BACKEND,
        k: int = config.TOP_K,
        falhar_agente: str | None = None,
    ) -> dict:
        """Executa o fluxo completo multiagentes e devolve resposta estruturada + trace."""
        trace: list[dict] = []
        falha_configurada = falhar_agente or os.getenv("RUMO_FALHAR_AGENTE")

        # 1. Classificar e decompor via reescrita.py (limiar calibrado em config.LIMIAR_COMPOSTA)
        t0_dec = time.monotonic()
        eh_composta, prob_composta = reescrita.classificar_composta(pergunta)
        backend_decomp = (
            backend if backend in ("ollama", "hf") else ("fallback" if backend == "extrativo" else "auto")
        )
        itens_sub: list[dict[str, str]] = []
        if eh_composta:
            itens_sub = reescrita.decompor_com_roteamento(pergunta, backend=backend_decomp)
        elif prob_composta == 0.0 and _TERMOS_RU.search(pergunta) and _TERMOS_FLUXO.search(pergunta):
            # Fallback quando Estágio 1 falhou offline (prob=0.0) mas há cruzamento explícito RU + Fluxo
            itens_sub = [{"pergunta": s, "eixo": ""} for s in reescrita._decompor_fallback(pergunta)]
            eh_composta = len(itens_sub) >= 2
        subperguntas = [i["pergunta"] for i in itens_sub]
        tempo_decomposicao_s = round(time.monotonic() - t0_dec, 3)

        trace.append({
            "etapa": "classificacao_decomposicao",
            "eh_composta": eh_composta,
            "prob_composta": prob_composta,
            "limiar": config.LIMIAR_COMPOSTA,
            "subperguntas": list(subperguntas),
            "tempo_s": tempo_decomposicao_s,
        })

        consultas_rotear = (
            itens_sub if len(itens_sub) >= 2 else [{"pergunta": pergunta, "eixo": ""}]
        )

        # 2. Rotear cada subpergunta para os agentes de domínio (Teste 1 -> Regex -> Teste 2 d1-omni)
        tarefas: list[tuple[int, str, str]] = []
        roteamento_detalhes: list[dict] = []
        ordem = 0
        for item in consultas_rotear:
            sub = item["pergunta"]
            eixo_sug = item.get("eixo") or None
            destinos = rotear_subpergunta(sub, eixo_sugerido=eixo_sug)
            roteamento_detalhes.append({"subpergunta": sub, "eixo_sugerido": eixo_sug or "", "agentes": destinos})
            for ag_id in destinos:
                tarefas.append((ordem, sub, ag_id))
                ordem += 1

        trace.append({
            "etapa": "roteamento",
            "rotas": roteamento_detalhes,
            "total_chamadas": len(tarefas),
        })

        # 3. Executar agentes em paralelo com degradação elegante
        def _rodar_tarefa(idx: int, sub: str, ag_id: str) -> tuple[int, RespostaAgente]:
            ag = self.agentes[ag_id]
            t_inicio = time.monotonic()
            try:
                if falha_configurada == ag_id:
                    raise RuntimeError(f"Falha simulada no agente '{ag_id}'")
                res = ag.responder(sub, k=k, backend=backend)
                if not res.tempo_total_s:
                    res.tempo_total_s = round(time.monotonic() - t_inicio, 3)
                return idx, res
            except Exception as exc:
                duracao = round(time.monotonic() - t_inicio, 3)
                return idx, RespostaAgente(
                    agente=ag_id,
                    nome_agente=getattr(ag, "nome", ag_id),
                    subpergunta=sub,
                    resposta="",
                    tempo_total_s=duracao,
                    erro=f"{type(exc).__name__}: {exc}",
                )

        t0_par = time.monotonic()
        resultados_brutos: dict[int, RespostaAgente] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(tarefas))) as pool:
            futuros = [pool.submit(_rodar_tarefa, idx, sub, ag_id) for idx, sub, ag_id in tarefas]
            for fut in as_completed(futuros):
                idx, res_agente = fut.result()
                resultados_brutos[idx] = res_agente
        tempo_paralelo_s = round(time.monotonic() - t0_par, 3)

        partes_ordenadas = [resultados_brutos[i] for i in range(len(tarefas))]
        soma_tempos_individuais_s = round(sum(p.tempo_total_s for p in partes_ordenadas), 3)
        ganho_paralelismo_s = round(max(0.0, soma_tempos_individuais_s - tempo_paralelo_s), 3)

        trace.append({
            "etapa": "execucao_paralela",
            "tempo_paralelo_s": tempo_paralelo_s,
            "soma_tempos_individuais_s": soma_tempos_individuais_s,
            "ganho_paralelismo_s": ganho_paralelismo_s,
            "execucoes": [
                {
                    "agente": p.agente,
                    "nome_agente": p.nome_agente,
                    "subpergunta": p.subpergunta,
                    "tempo_total_s": p.tempo_total_s,
                    "n_trechos": len(p.trechos_recuperados),
                    "erro": p.erro,
                }
                for p in partes_ordenadas
            ],
        })

        # 4. Validador factual + devolução ao Sintetizador se reprovada
        eventos_validacao: list[dict] = []
        devolucoes: list[dict] = []
        for idx, parte in enumerate(partes_ordenadas):
            if parte.erro:
                eventos_validacao.append({
                    "agente": parte.agente,
                    "aprovado": False,
                    "ignorado_por_erro": True,
                    "motivos": [f"Agente indisponível: {parte.erro}"],
                })
                continue

            try:
                if falha_configurada == "validador":
                    raise RuntimeError("Falha simulada no agente 'validador'")
                val = self.validador.validar(parte)
            except Exception as exc:
                parte.validacao = {
                    "aprovado": True,
                    "indisponivel": True,
                    "valores_sem_fonte": [],
                    "sem_citacao": False,
                    "eh_recusa": False,
                    "motivos": [f"⚠ Aviso ({AgenteValidador.nome}): validação factual indisponível ({type(exc).__name__}: {exc})."],
                    "acao_recomendada": "aprovar_degradado",
                }
                eventos_validacao.append({
                    "agente": parte.agente,
                    "aprovado": False,
                    "indisponivel": True,
                    "motivos": list(parte.validacao["motivos"]),
                })
                continue

            if not val.aprovado:
                parte_corrigida, ev_devolucao = self.sintetizador.processar_devolucao(parte, val, backend=backend)
                val_apos = self.validador.validar(parte_corrigida)
                ev_devolucao["aprovado_apos_devolucao"] = val_apos.aprovado
                ev_devolucao["motivos_pos_devolucao"] = list(val_apos.motivos)
                devolucoes.append(ev_devolucao)
                partes_ordenadas[idx] = parte_corrigida
                val = val_apos

            partes_ordenadas[idx].validacao = asdict(val)
            eventos_validacao.append({
                "agente": partes_ordenadas[idx].agente,
                "aprovado": val.aprovado,
                "acao_recomendada": val.acao_recomendada,
                "motivos": list(val.motivos),
            })

        trace.append({
            "etapa": "validacao_factual",
            "resultados": eventos_validacao,
            "devolucoes_ao_sintetizador": devolucoes,
        })

        # 5. Síntese / Composição sem misturar índices [n]
        composto = self.sintetizador.compor(pergunta, partes_ordenadas)
        trace.append({
            "etapa": "composicao_sintetizador",
            "n_partes": len(partes_ordenadas),
            "indices_isolados_por_parte": True,
            "degradado": composto["degradado"],
            "avisos": composto["avisos"],
        })

        return {
            "pergunta": pergunta,
            "subperguntas": subperguntas,
            "resposta": composto["resposta"],
            "fontes_citadas": composto["fontes_citadas"],
            "valores_sem_fonte": composto["valores_sem_fonte"],
            "sem_citacao": composto["sem_citacao"],
            "trechos_recuperados": composto["trechos_recuperados"],
            "tempo_decomposicao_s": tempo_decomposicao_s,
            "tempo_busca_s": composto["tempo_busca_s"],
            "tempo_geracao_s": composto["tempo_geracao_s"],
            "backend": backend,
            "modo_agentes": True,
            "partes": composto["partes"],
            "degradado": composto["degradado"],
            "avisos": composto["avisos"],
            "tempo_paralelo_s": tempo_paralelo_s,
            "soma_tempos_individuais_s": soma_tempos_individuais_s,
            "ganho_paralelismo_s": ganho_paralelismo_s,
            "trace": trace,
        }
