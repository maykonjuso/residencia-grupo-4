"""Orquestrador multiagentes, validador factual, sintetizador e roteamento híbrido.

Coordena agentes especializados pelo contrato comum (`Agente`, `Mensagem`,
`Resposta` e `Trace`):
- Classificação e decomposição via `reescrita.py`.
- Roteamento por domínio (eixo sugerido pelo LLM -> Regex -> `d1-omni-600M`).
- Execução paralela via `ThreadPoolExecutor` com troca explícita de `Mensagem` e `Resposta`.
- Validação factual (`AgenteValidador`) e devolução ao `Sintetizador` com limite de 1 retentativa.
- Composição final preservando os índices `[n]` isolados por parte e degradação elegante.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
import os
import time
from typing import Any

from .. import config, geracao, reescrita
from .agente_fluxo import AgenteFluxo
from .agente_ru import AgenteRU, _TERMOS_FLUXO, _TERMOS_RU
from .base import Agente
from .mensagem import Mensagem, Resposta
from .trace import Trace
from .validador import (
    AgenteValidador,
    ResultadoValidacao,
    normalizar_trecho_validacao as _normalizar_trecho_validacao,
)

_CAMPOS_TRECHO_RESUMO = (
    "chunk_id",
    "doc_id",
    "titulo",
    "orgao",
    "pagina",
    "secao",
    "similaridade",
    "nota_rrf",
    "url",
    "texto",
)


@dataclass
class RespostaAgente:
    """Visão estruturada da contribuição de um agente para composição e trace."""

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
    ferramenta_chamada: dict | None = None
    dado_estruturado: dict | None = None


def _resumir_trecho(t: dict) -> dict:
    """Padroniza os campos essenciais de um chunk recuperado."""
    resumo = {k: t.get(k) for k in _CAMPOS_TRECHO_RESUMO}
    if resumo["texto"] is None:
        resumo["texto"] = ""
    if resumo["secao"] is None:
        resumo["secao"] = ""
    return resumo


def _normalizar_fontes(fontes: list[dict] | None, texto: str, trechos: list[dict] | None) -> list[dict]:
    """Preserva as fontes retornadas pelo agente ou resolve `[n]` contra os trechos."""
    if fontes:
        saida: list[dict] = []
        for idx, f in enumerate(fontes, start=1):
            item = dict(f)
            item.setdefault("n", idx)
            saida.append(item)
        return saida
    if trechos:
        return geracao.citacoes_usadas(texto, [_normalizar_trecho_validacao(t) for t in trechos])
    return []


class Sintetizador(Agente):
    """Trata devoluções do AgenteValidador (máx. 1 retentativa) e compõe a saída isolando `[n]`."""

    nome = "Sintetizador"
    papel = "Composição de respostas parciais com isolamento de citações [n]"
    max_retentativas = 1

    def processar_devolucao(
        self,
        item: RespostaAgente,
        validacao: ResultadoValidacao,
        backend: str,
        tentativa: int = 1,
        instrucoes_base: str | None = None,
        agente_execucao: Agente | None = None,
    ) -> tuple[RespostaAgente, dict]:
        """Tenta corrigir a resposta com feedback do validador em até 1 retentativa."""
        resposta_anterior = item.resposta
        evento: dict[str, Any] = {
            "agente": item.agente,
            "nome_agente": item.nome_agente,
            "tentativa": tentativa,
            "motivos_reprovacao": list(validacao.motivos),
            "resposta_anterior": resposta_anterior,
            "segunda_tentativa": False,
            "acao": "recusa_apos_retentativa",
        }

        if item.erro:
            evento["acao"] = "erro_agente"
            return item, evento

        if tentativa > self.max_retentativas:
            item.resposta = geracao.RECUSA
            item.fontes_citadas = []
            evento["acao"] = "recusa_apos_retentativa"
            return item, evento

        if agente_execucao is not None:
            evento["segunda_tentativa"] = True
            msg_ret = Mensagem(
                remetente=self.nome,
                destinatario=getattr(agente_execucao, "nome", item.nome_agente),
                conteudo=item.subpergunta,
                contexto={
                    "eixo": item.agente,
                    "backend": backend,
                    "tentativa": tentativa + 1,
                    "segunda_tentativa": True,
                    "motivos_reprovacao": list(validacao.motivos),
                    "resposta_anterior": resposta_anterior,
                },
            )
            try:
                resp_ret = agente_execucao.executar(msg_ret)
                novos_trechos = msg_ret.contexto.get("trechos_recuperados") if isinstance(msg_ret.contexto, dict) else None
                if isinstance(novos_trechos, list):
                    item.trechos_recuperados = [_resumir_trecho(t) for t in novos_trechos]
                elif resp_ret.fontes:
                    fontes_texto = [
                        _resumir_trecho(f)
                        for f in resp_ret.fontes
                        if isinstance(f, dict) and (f.get("texto") or f.get("conteudo"))
                    ]
                    if fontes_texto:
                        item.trechos_recuperados = fontes_texto
                item.resposta = resp_ret.conteudo
                item.fontes_citadas = _normalizar_fontes(resp_ret.fontes, resp_ret.conteudo, item.trechos_recuperados)
                evento["resposta_segunda_tentativa"] = item.resposta
                evento["acao"] = "retentativa_agente"
                evento["_interacao_retentativa"] = (msg_ret, resp_ret)
            except Exception as exc:
                item.resposta = geracao.RECUSA
                item.fontes_citadas = []
                evento["erro_retentativa"] = f"{type(exc).__name__}: {exc}"
                evento["acao"] = "recusa_apos_retentativa"
            return item, evento

        trechos = [_normalizar_trecho_validacao(t) for t in (item.trechos_recuperados or [])]
        if not trechos:
            item.resposta = geracao.RECUSA
            item.fontes_citadas = []
            evento["acao"] = "recusa_sem_trechos"
            return item, evento

        motivos_txt = "; ".join(validacao.motivos) or "Resposta reprovada pelo Agente Validador"
        base_instr = instrucoes_base or geracao.INSTRUCOES
        instrucoes_reparo = (
            f"{base_instr}\n\n"
            f"CORREÇÃO OBRIGATÓRIA (motivos da reprovação anterior: {motivos_txt}):\n"
            "- Reescreva a resposta mantendo SOMENTE fatos presentes nos trechos recuperados.\n"
            "- Coloque obrigatoriamente a citação [1], [2], ... ao final de CADA afirmação e de CADA item de lista.\n"
            "- Remova ou recuse qualquer valor, preço, data, horário ou código que não conste literalmente nos trechos."
        )

        nova_resp = geracao.gerar_com_instrucoes(
            item.subpergunta,
            trechos,
            instrucoes=instrucoes_reparo,
            backend=backend,
        )
        if geracao.eh_recusa(nova_resp):
            item.resposta = geracao.RECUSA
            item.fontes_citadas = []
        else:
            item.resposta = nova_resp
            item.fontes_citadas = geracao.citacoes_usadas(nova_resp, trechos)
        evento["segunda_tentativa"] = True
        evento["resposta_segunda_tentativa"] = item.resposta
        evento["acao"] = "retentativa_com_feedback"
        return item, evento

    def compor(self, pergunta: str, partes: list[RespostaAgente]) -> dict:
        """Junta as respostas dos agentes mantendo os índices `[n]` e fontes isolados por parte."""
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
                aviso = (
                    f"⚠ Aviso ({parte.nome_agente}): não foi possível obter esta parte da resposta ({parte.erro})."
                )
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
            elif not val.get("aprovado", True) and not geracao.eh_recusa(parte.resposta):
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

    def executar(self, mensagem: Mensagem) -> Resposta:
        contexto = mensagem.contexto if isinstance(mensagem.contexto, dict) else {}
        acao = contexto.get("acao", "compor")

        if acao == "devolucao":
            parte_raw = contexto["parte"]
            parte = RespostaAgente(**parte_raw) if isinstance(parte_raw, dict) else parte_raw
            val_raw = contexto["validacao"]
            val = ResultadoValidacao(**val_raw) if isinstance(val_raw, dict) else val_raw
            backend = contexto.get("backend", config.BACKEND)
            tentativa = int(contexto.get("tentativa", 1))
            agente_execucao = contexto.pop("_agente_execucao", None)

            corrigida, evento = self.processar_devolucao(
                parte,
                val,
                backend=backend,
                tentativa=tentativa,
                instrucoes_base=contexto.get("instrucoes_base"),
                agente_execucao=agente_execucao,
            )
            interacao_ret = evento.pop("_interacao_retentativa", None)
            if interacao_ret is not None:
                contexto["_interacao_retentativa"] = interacao_ret
            contexto["parte_corrigida"] = asdict(corrigida)
            contexto["evento_devolucao"] = evento
            return Resposta(
                conteudo=corrigida.resposta,
                fontes=list(corrigida.fontes_citadas),
                confianca=None,
                alertas=list(evento.get("motivos_reprovacao", [])),
            )

        partes_raw = contexto.get("partes", [])
        partes = [
            RespostaAgente(**p) if isinstance(p, dict) else p
            for p in partes_raw
        ]
        composto = self.compor(mensagem.conteudo, partes)
        contexto["resultado_composicao"] = composto
        return Resposta(
            conteudo=composto["resposta"],
            fontes=list(composto["fontes_citadas"]),
            confianca=None,
            alertas=list(composto["avisos"]),
        )


def rotear_subpergunta(
    subpergunta: str,
    eixo_sugerido: str | None = None,
    usar_d1_fallback: bool = True,
) -> list[str]:
    """Roteamento híbrido: eixo do LLM (Teste 1) -> Regex rápido -> Teste 2 (d1-omni) quando ambíguo."""
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


class Orquestrador:
    """Coordena decomposição, roteamento, execução paralela via Mensagem/Resposta, validação e síntese."""

    def __init__(
        self,
        agente_ru: Agente | None = None,
        agente_fluxo: Agente | None = None,
        validador: AgenteValidador | None = None,
        sintetizador: Sintetizador | None = None,
    ):
        modo_padrao = config.BUSCA if config.BUSCA in ("denso", "bm25", "hibrido") else "hibrido"
        self.agentes: dict[str, Any] = {
            "ru": agente_ru if agente_ru is not None else AgenteRU(modo=modo_padrao),
            "fluxo": agente_fluxo if agente_fluxo is not None else AgenteFluxo(modo=modo_padrao),
        }
        self.validador = validador or AgenteValidador()
        self.sintetizador = sintetizador or Sintetizador()

    def _invocar_agente(
        self,
        idx: int,
        sub: str,
        ag_id: str,
        k: int,
        backend: str,
        falha_configurada: str | None,
        data: str | None = None,
        perfil: dict | None = None,
        curso: str | None = None,
        curriculo_id: str | None = None,
        vigencia: str | None = None,
    ) -> tuple[int, Mensagem, Resposta, RespostaAgente]:
        ag = self.agentes[ag_id]
        nome_ag = getattr(ag, "nome", ag_id)
        ctx_msg: dict[str, Any] = {"eixo": ag_id, "k": k, "backend": backend}
        if data is not None:
            ctx_msg["data"] = data
        if perfil is not None:
            ctx_msg["perfil"] = perfil
        if curso is not None:
            ctx_msg["curso"] = curso
        if curriculo_id is not None:
            ctx_msg["curriculo_id"] = curriculo_id
        if vigencia is not None:
            ctx_msg["vigencia"] = vigencia
        msg = Mensagem(
            remetente="Orquestrador",
            destinatario=nome_ag,
            conteudo=sub,
            contexto=ctx_msg,
        )
        t_inicio = time.monotonic()

        try:
            if falha_configurada == ag_id:
                raise RuntimeError(f"Falha simulada no agente '{ag_id}'")

            if hasattr(ag, "executar"):
                resp: Resposta = ag.executar(msg)
                duracao = round(time.monotonic() - t_inicio, 3)

                if "trechos_recuperados" in msg.contexto:
                    trechos_brutos = msg.contexto.get("trechos_recuperados") or []
                    trechos_resumo = [_resumir_trecho(t) for t in trechos_brutos]
                else:
                    # Agente fake que só preenche Resposta(conteudo, fontes) sem gravar trechos no contexto
                    fontes_com_texto = [
                        _resumir_trecho(f)
                        for f in (resp.fontes or [])
                        if isinstance(f, dict) and (f.get("texto") or f.get("conteudo"))
                    ]
                    trechos_brutos = None
                    trechos_resumo = fontes_com_texto

                fontes_citadas = _normalizar_fontes(resp.fontes, resp.conteudo, trechos_brutos)
                msg.contexto["trechos_recuperados"] = trechos_resumo
                if "tempo_busca_s" not in msg.contexto:
                    msg.contexto["tempo_busca_s"] = 0.0
                if "tempo_geracao_s" not in msg.contexto:
                    msg.contexto["tempo_geracao_s"] = duracao

                parte = RespostaAgente(
                    agente=ag_id,
                    nome_agente=nome_ag,
                    subpergunta=sub,
                    resposta=resp.conteudo,
                    trechos_recuperados=trechos_resumo,
                    fontes_citadas=fontes_citadas,
                    tempo_busca_s=float(msg.contexto.get("tempo_busca_s", 0.0)),
                    tempo_geracao_s=float(msg.contexto.get("tempo_geracao_s", duracao)),
                    tempo_total_s=duracao,
                    ferramenta_chamada=msg.contexto.get("ferramenta_chamada"),
                    dado_estruturado=msg.contexto.get("dado_estruturado"),
                )
                # Sinaliza ausência explícita de trechos para o validador quando vieram de agente fake
                if trechos_brutos is None:
                    msg.contexto["_sem_trechos_explicitos"] = True
                return idx, msg, resp, parte

            if hasattr(ag, "pesquisar"):
                pesq = ag.pesquisar(sub)
                trechos = pesq.get("trechos") or []
                texto = geracao.gerar(sub, trechos, backend=backend)
                duracao = round(time.monotonic() - t_inicio, 3)
                fontes = _normalizar_fontes(geracao.citacoes_usadas(texto, trechos), texto, trechos)
                resp = Resposta(conteudo=texto, fontes=fontes)
                trechos_resumo = [_resumir_trecho(t) for t in trechos]
                msg.contexto["trechos_recuperados"] = trechos_resumo
                parte = RespostaAgente(
                    agente=ag_id,
                    nome_agente=nome_ag,
                    subpergunta=sub,
                    resposta=texto,
                    trechos_recuperados=trechos_resumo,
                    fontes_citadas=fontes,
                    tempo_total_s=duracao,
                )
                return idx, msg, resp, parte

            # Compatibilidade residual caso receba agente legado com .responder()
            res_legado = ag.responder(sub, k=k, backend=backend)
            resp = Resposta(conteudo=res_legado.resposta, fontes=list(res_legado.fontes_citadas))
            return idx, msg, resp, res_legado
        except Exception as exc:
            duracao = round(time.monotonic() - t_inicio, 3)
            msg_erro = f"{type(exc).__name__}: {exc}"
            resp_erro = Resposta(conteudo="", fontes=[], confianca=0.0, alertas=[msg_erro])
            parte_erro = RespostaAgente(
                agente=ag_id,
                nome_agente=nome_ag,
                subpergunta=sub,
                resposta="",
                tempo_total_s=duracao,
                erro=msg_erro,
            )
            return idx, msg, resp_erro, parte_erro

    def _classificar_e_decompor(self, pergunta: str, backend: str) -> tuple[bool, float, list[dict[str, str]], float]:
        t0 = time.monotonic()
        eh_composta, prob_composta = reescrita.classificar_composta(pergunta)
        backend_decomp = (
            backend
            if backend in ("ollama", "hf", "openai")
            else ("fallback" if backend == "extrativo" else "auto")
        )
        cruzamento_dominios = bool(_TERMOS_RU.search(pergunta) and _TERMOS_FLUXO.search(pergunta))
        partes_fallback = reescrita._decompor_fallback(pergunta)

        if not eh_composta and (cruzamento_dominios or len(partes_fallback) >= 2):
            eh_composta = True

        itens_sub: list[dict[str, str]] = []
        if eh_composta:
            itens_sub = reescrita.decompor_com_roteamento(pergunta, backend=backend_decomp)
            if len(itens_sub) < 2 and len(partes_fallback) >= 2:
                itens_sub = [{"pergunta": s, "eixo": ""} for s in partes_fallback]
                eh_composta = True

        tempo_s = round(time.monotonic() - t0, 3)
        return eh_composta, prob_composta, itens_sub, tempo_s

    def _validar_parte(
        self,
        parte: RespostaAgente,
        sem_trechos_explicitos: bool,
        backend: str,
        falha_configurada: str | None,
        trace_oficial: Trace,
    ) -> tuple[RespostaAgente, dict, dict | None]:
        """Valida uma parte via `AgenteValidador.executar` e devolve no máximo 1 vez ao Sintetizador."""
        if parte.erro:
            evento = {
                "agente": parte.agente,
                "aprovado": False,
                "ignorado_por_erro": True,
                "motivos": [f"Agente indisponível: {parte.erro}"],
            }
            return parte, evento, None

        trechos_para_val = None if sem_trechos_explicitos else parte.trechos_recuperados
        msg_val = Mensagem(
            remetente="Orquestrador",
            destinatario=self.validador.nome,
            conteudo=parte.resposta,
            contexto={
                "agente": parte.agente,
                "subpergunta": parte.subpergunta,
                "trechos": trechos_para_val,
                "fontes": parte.fontes_citadas,
                "erro": parte.erro,
            },
        )

        try:
            if falha_configurada == "validador":
                raise RuntimeError("Falha simulada no agente 'validador'")
            resp_val = self.validador.executar(msg_val)
            trace_oficial.registrar(msg_val, resp_val)
            val = ResultadoValidacao(**msg_val.contexto["validacao"])
        except Exception as exc:
            aviso_val = (
                f"⚠ Aviso ({self.validador.nome}): validação factual indisponível "
                f"({type(exc).__name__}: {exc})."
            )
            parte.validacao = {
                "aprovado": True,
                "indisponivel": True,
                "valores_sem_fonte": [],
                "sem_citacao": False,
                "eh_recusa": False,
                "motivos": [aviso_val],
                "acao_recomendada": "aprovar_degradado",
            }
            resp_err = Resposta(conteudo="INDISPONIVEL", alertas=[aviso_val], confianca=0.0)
            trace_oficial.registrar(msg_val, resp_err)
            return (
                parte,
                {"agente": parte.agente, "aprovado": False, "indisponivel": True, "motivos": [aviso_val]},
                None,
            )

        aprovado_inicial = val.aprovado
        motivos_iniciais = list(val.motivos)
        ev_devolucao: dict[str, Any] | None = None
        if not val.aprovado:
            ag_dom = self.agentes.get(parte.agente)
            eh_agente_fake = (
                ag_dom is not None
                and not isinstance(ag_dom, (AgenteRU, AgenteFluxo))
                and not hasattr(ag_dom, "_resposta_fixa")
                and hasattr(ag_dom, "executar")
            )
            instrucoes_base = getattr(ag_dom, "instrucoes", None)
            msg_dev = Mensagem(
                remetente="Orquestrador",
                destinatario=self.sintetizador.nome,
                conteudo=parte.resposta,
                contexto={
                    "acao": "devolucao",
                    "parte": asdict(parte),
                    "validacao": asdict(val),
                    "backend": backend,
                    "tentativa": 1,
                    "instrucoes_base": instrucoes_base,
                    "_agente_execucao": ag_dom if eh_agente_fake else None,
                },
            )
            resp_dev = self.sintetizador.executar(msg_dev)
            interacao_ret = msg_dev.contexto.pop("_interacao_retentativa", None)
            trace_oficial.registrar(msg_dev, resp_dev)
            if interacao_ret is not None:
                trace_oficial.registrar(*interacao_ret)

            parte = RespostaAgente(**msg_dev.contexto["parte_corrigida"])
            ev_devolucao = msg_dev.contexto["evento_devolucao"]

            trechos_reval = (
                parte.trechos_recuperados
                if (not sem_trechos_explicitos or parte.trechos_recuperados)
                else None
            )
            msg_reval = Mensagem(
                remetente="Orquestrador",
                destinatario=self.validador.nome,
                conteudo=parte.resposta,
                contexto={
                    "agente": parte.agente,
                    "subpergunta": parte.subpergunta,
                    "trechos": trechos_reval,
                    "fontes": parte.fontes_citadas,
                    "erro": parte.erro,
                },
            )
            resp_reval = self.validador.executar(msg_reval)
            trace_oficial.registrar(msg_reval, resp_reval)
            val_apos = ResultadoValidacao(**msg_reval.contexto["validacao"])

            if not val_apos.aprovado and not geracao.eh_recusa(parte.resposta):
                # Limite de 1 retentativa atingido: aplica recusa final em vez de tentar novamente
                parte.resposta = geracao.RECUSA
                parte.fontes_citadas = []
                ev_devolucao["recusa_final"] = True
                msg_recusa = Mensagem(
                    remetente="Orquestrador",
                    destinatario=self.validador.nome,
                    conteudo=parte.resposta,
                    contexto={
                        "agente": parte.agente,
                        "subpergunta": parte.subpergunta,
                        "trechos": trechos_reval,
                        "fontes": [],
                        "erro": None,
                    },
                )
                resp_recusa = self.validador.executar(msg_recusa)
                trace_oficial.registrar(msg_recusa, resp_recusa)
                val_apos = ResultadoValidacao(**msg_recusa.contexto["validacao"])

            ev_devolucao["aprovado_apos_devolucao"] = val_apos.aprovado
            ev_devolucao["motivos_pos_devolucao"] = list(val_apos.motivos)
            val = val_apos

        parte.validacao = asdict(val)
        evento = {
            "agente": parte.agente,
            "aprovado_inicial": aprovado_inicial,
            "motivos_iniciais": motivos_iniciais,
            "aprovado": val.aprovado,
            "acao_recomendada": val.acao_recomendada,
            "motivos": list(val.motivos),
        }
        return parte, evento, ev_devolucao

    def executar(
        self,
        pergunta: str,
        backend: str = config.BACKEND,
        k: int = config.TOP_K,
        falhar_agente: str | None = None,
        data: str | None = None,
        perfil: dict | None = None,
        curso: str | None = None,
        curriculo_id: str | None = None,
        vigencia: str | None = None,
    ) -> dict:
        """Executa o fluxo multiagentes com contrato `Mensagem`/`Resposta` e registra o `Trace`."""
        trace_etapas: list[dict] = []
        trace_oficial = Trace()
        falha_configurada = falhar_agente or os.getenv("RUMO_FALHAR_AGENTE")

        # 1. Classificar e decompor via reescrita.py
        eh_composta, prob_composta, itens_sub, tempo_decomposicao_s = self._classificar_e_decompor(
            pergunta, backend
        )
        subperguntas = [i["pergunta"] for i in itens_sub]
        trace_etapas.append({
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

        # 2. Rotear cada subpergunta para os agentes de domínio
        tarefas: list[tuple[int, str, str]] = []
        roteamento_detalhes: list[dict] = []
        ordem = 0
        for item in consultas_rotear:
            sub = item["pergunta"]
            eixo_sug = item.get("eixo") or None
            destinos = rotear_subpergunta(sub, eixo_sugerido=eixo_sug)
            roteamento_detalhes.append({
                "subpergunta": sub,
                "eixo_sugerido": eixo_sug or "",
                "agentes": destinos,
            })
            for ag_id in destinos:
                tarefas.append((ordem, sub, ag_id))
                ordem += 1

        trace_etapas.append({
            "etapa": "roteamento",
            "rotas": roteamento_detalhes,
            "total_chamadas": len(tarefas),
        })

        # 3. Executar agentes em paralelo usando o contrato Mensagem -> Resposta
        t0_par = time.monotonic()
        brutos: dict[int, tuple[Mensagem, Resposta, RespostaAgente]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(tarefas))) as pool:
            futuros = [
                pool.submit(
                    self._invocar_agente,
                    idx,
                    sub,
                    ag_id,
                    k,
                    backend,
                    falha_configurada,
                    data,
                    perfil,
                    curso,
                    curriculo_id,
                    vigencia,
                )
                for idx, sub, ag_id in tarefas
            ]
            for fut in as_completed(futuros):
                idx, msg, resp, parte = fut.result()
                brutos[idx] = (msg, resp, parte)
        tempo_paralelo_s = round(time.monotonic() - t0_par, 3)

        partes_ordenadas: list[RespostaAgente] = []
        flags_sem_trechos: list[bool] = []
        for idx in range(len(tarefas)):
            msg, resp, parte = brutos[idx]
            sem_trechos_explicitos = bool(msg.contexto.pop("_sem_trechos_explicitos", False))
            trace_oficial.registrar(msg, resp)
            partes_ordenadas.append(parte)
            flags_sem_trechos.append(sem_trechos_explicitos)

        soma_tempos_individuais_s = round(sum(p.tempo_total_s for p in partes_ordenadas), 3)
        ganho_paralelismo_s = round(max(0.0, soma_tempos_individuais_s - tempo_paralelo_s), 3)

        trace_etapas.append({
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
                    "ferramenta": p.ferramenta_chamada,
                }
                for p in partes_ordenadas
            ],
        })

        # 4. Validador factual + devolução ao Sintetizador (máx. 1 retentativa)
        eventos_validacao: list[dict] = []
        devolucoes: list[dict] = []
        for idx, parte in enumerate(partes_ordenadas):
            parte_atualizada, ev_val, ev_dev = self._validar_parte(
                parte=parte,
                sem_trechos_explicitos=flags_sem_trechos[idx],
                backend=backend,
                falha_configurada=falha_configurada,
                trace_oficial=trace_oficial,
            )
            partes_ordenadas[idx] = parte_atualizada
            eventos_validacao.append(ev_val)
            if ev_dev is not None:
                devolucoes.append(ev_dev)

        trace_etapas.append({
            "etapa": "validacao_factual",
            "resultados": eventos_validacao,
            "devolucoes_ao_sintetizador": devolucoes,
        })

        # 5. Síntese / Composição via contrato Mensagem -> Resposta
        msg_sint = Mensagem(
            remetente="Orquestrador",
            destinatario=self.sintetizador.nome,
            conteudo=pergunta,
            contexto={"acao": "compor", "partes": [asdict(p) for p in partes_ordenadas]},
        )
        resp_sint = self.sintetizador.executar(msg_sint)
        composto = msg_sint.contexto.pop("resultado_composicao")
        trace_oficial.registrar(msg_sint, resp_sint)

        trace_etapas.append({
            "etapa": "composicao_sintetizador",
            "n_partes": len(partes_ordenadas),
            "indices_isolados_por_parte": True,
            "degradado": composto["degradado"],
            "avisos": composto["avisos"],
        })

        trace_dict = trace_oficial.para_dict()
        ferramentas_usadas = [
            {"agente": p.agente, **p.ferramenta_chamada}
            for p in partes_ordenadas
            if p.ferramenta_chamada
        ]
        dados_estruturados = [
            {
                "agente": p.agente,
                "ferramenta": p.ferramenta_chamada["nome"],
                "dados": p.dado_estruturado,
            }
            for p in partes_ordenadas
            if p.ferramenta_chamada and p.dado_estruturado is not None
        ]
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
            "ferramentas_usadas": ferramentas_usadas,
            "dados_estruturados": dados_estruturados,
            "degradado": composto["degradado"],
            "avisos": composto["avisos"],
            "tempo_paralelo_s": tempo_paralelo_s,
            "soma_tempos_individuais_s": soma_tempos_individuais_s,
            "ganho_paralelismo_s": ganho_paralelismo_s,
            "trace": trace_etapas,
            "trace_agentes": trace_dict,
            "interacoes": trace_dict["interacoes"],
        }
