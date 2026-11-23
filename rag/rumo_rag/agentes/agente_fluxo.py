"""Agente especializado em disciplinas e normas acadêmicas."""

from __future__ import annotations

import time

from .. import config, geracao, indice
from .agente_ru import _LOCK_INDICE, executar_agente_dominio, pergunta_fora_do_dominio
from .base import Agente
from ..grafo_curricular import carregar_grafo_f16
from .mensagem import Mensagem, Resposta

INSTRUCOES_FLUXO = f"""Você é o Agente Fluxo do sistema RUmo, especialista exclusivo nos fluxos de disciplinas, cursos de engenharia e normas acadêmicas da FCTE/UnB (campus Gama).
Seu domínio cobre APENAS fluxogramas curriculares, cadeias de pré-requisitos e correquisitos, códigos de disciplinas (como FGA0314), créditos, carga horária, projetos pedagógicos (PPCs), estágio, TCC, trancamento/matrícula e pós-graduação (PPGEB).
Regras:
1. Responda em português, de forma direta, usando SOMENTE as informações dos trechos numerados abaixo e APENAS sobre temas acadêmicos e fluxos de cursos. Ignore ou recuse qualquer tema sobre Restaurante Universitário (RU), cardápio, preços ou horários de refeição.
2. OBRIGATÓRIO: depois de cada afirmação ou item de lista, termine com a citação do trecho entre colchetes, por exemplo [1] ou [2][3]. Nunca omita [n] em listas.
3. Se os trechos não trazem a resposta acadêmica, diga exatamente: "{geracao.RECUSA}" e não sugira assuntos fora do seu domínio. Não invente códigos, créditos, pré-requisitos ou prazos.
4. Se a regra ou o fluxo depender do curso, currículo/ano de ingresso ou perfil (graduação, mestrado), especifique exatamente essa condição conforme os trechos.
5. Seja conciso: no máximo 120 palavras. Copie códigos de disciplinas, quantidades de créditos, cargas horárias e nomes exatamente como estão nos trechos."""


class AgenteFluxo(Agente):
    """Agente especialista em fluxo de disciplinas, pré-requisitos, PPCs e normas da FCTE/UnB."""

    nome = "Agente Fluxo"
    papel = (
        "Especialista em fluxo de disciplinas, pré-requisitos, PPCs e normas "
        "acadêmicas da FCTE/UnB"
    )
    eixo = "fluxo"
    instrucoes = INSTRUCOES_FLUXO
    ferramentas = ("grafo_fluxo", "minha_agenda")

    def __init__(self, k: int = config.TOP_K, modo: str = "hibrido"):
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("O parâmetro k deve ser um inteiro positivo.")
        if modo not in ("denso", "bm25", "hibrido"):
            raise ValueError("Modo de busca inválido.")

        self.k = k
        self.modo = modo

    def pesquisar(self, pergunta: str) -> dict:
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("A pergunta não pode estar vazia.")

        pergunta = pergunta.strip()
        with _LOCK_INDICE:
            trechos = indice.buscar(
                pergunta,
                k=self.k,
                modo=self.modo,
                eixo=self.eixo,
                decompor_pergunta=False,
            )

        fontes = []
        fontes_vistas = set()

        for trecho in trechos:
            chave = (
                trecho.get("doc_id"),
                trecho.get("pagina"),
                trecho.get("url"),
            )
            if chave not in fontes_vistas:
                fontes_vistas.add(chave)
                fontes.append({
                    campo: trecho.get(campo)
                    for campo in (
                        "doc_id", "titulo", "orgao", "pagina",
                        "secao", "url", "chunk_id",
                    )
                })

        return {
            "agente": self.nome,
            "eixo": self.eixo,
            "pergunta": pergunta,
            "encontrou": bool(trechos),
            "trechos": trechos,
            "fontes": fontes,
        }

    def montar_mensagens(self, pergunta: str, trechos: list[dict]) -> list[dict]:
        """Monta as mensagens para o LLM usando o prompt especializado do Agente Fluxo."""
        return geracao.montar_mensagens(pergunta, trechos, instrucoes=self.instrucoes)

    def responder_grafo(self, mensagem: Mensagem) -> Resposta | None:
        """Usa ferramentas locais (agenda ou grafo curricular) sem recorrer ao LLM."""
        if not pergunta_fora_do_dominio(mensagem.conteudo, self.eixo):
            from . import ferramentas

            contexto = mensagem.contexto if isinstance(mensagem.contexto, dict) else {}
            mensagem.contexto = contexto
            chamada = ferramentas.extrair_chamada_fluxo(mensagem.conteudo, contexto)
            if chamada is None:
                return None

            nome_ferr, args = chamada
            t0 = time.monotonic()
            res = getattr(ferramentas, nome_ferr)(**args)
            tempo_busca = round(time.monotonic() - t0, 3)
            if res.ferramenta == "grafo_fluxo" and res.recusado and res.dados.get("fallback_rag", True):
                return None

            backend = contexto.get("backend", config.BACKEND)
            texto_final, tempo_ger, alertas_final, redigido_llm = ferramentas.redigir_com_ferramenta(
                mensagem.conteudo,
                res,
                self.instrucoes,
                backend,
            )

            trace_ferr = res.para_trace()
            trace_ferr["redigido_por_llm"] = redigido_llm
            trace_ferr["llm_falhou"] = any("Redação via LLM falhou" in a for a in alertas_final)
            contexto["ferramenta_chamada"] = trace_ferr
            contexto["dado_estruturado"] = res.dados
            contexto["trechos_recuperados"] = list(res.trechos_evidencia)
            contexto["tempo_busca_s"] = tempo_busca
            contexto["tempo_geracao_s"] = tempo_ger
            return Resposta(
                conteudo=texto_final,
                fontes=list(res.fontes),
                confianca=0.0 if res.recusado else 1.0,
                alertas=alertas_final,
            )
        return None

    responder_ferramenta = responder_grafo

    def executar(self, mensagem: Mensagem) -> Resposta:
        """Executa consulta determinística ao grafo ou usa a busca RAG especializada."""
        resposta_grafo = self.responder_grafo(mensagem)
        if resposta_grafo is not None:
            return resposta_grafo
        return executar_agente_dominio(self, mensagem)
