"""Agente especializado em disciplinas e normas acadêmicas."""

from __future__ import annotations

import time

from .. import calendario, config, geracao, indice
from .agente_ru import (
    _LOCK_INDICE,
    deduplicar_fontes,
    executar_agente_dominio,
    executar_ferramenta_estruturada,
)
from .base import Agente
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

        return {
            "agente": self.nome,
            "eixo": self.eixo,
            "pergunta": pergunta,
            "encontrou": bool(trechos),
            "trechos": trechos,
            "fontes": deduplicar_fontes(trechos),
        }

    def montar_mensagens(self, pergunta: str, trechos: list[dict]) -> list[dict]:
        """Monta as mensagens para o LLM usando o prompt especializado do Agente Fluxo."""
        return geracao.montar_mensagens(pergunta, trechos, instrucoes=self.instrucoes)

    def responder_grafo(self, mensagem: Mensagem) -> Resposta | None:
        """Executa ferramenta local (agenda ou grafo curricular) e delega a redação (com guardião) ao backend ativo."""
        from . import ferramentas

        return executar_ferramenta_estruturada(
            self,
            mensagem,
            ferramentas.extrair_chamada_fluxo,
            permitir_fallback_rag=True,
        )

    responder_ferramenta = responder_grafo

    def executar(self, mensagem: Mensagem) -> Resposta:
        """Usa calendário estruturado, grafo curricular ou busca RAG especializada no eixo Fluxo."""
        contexto = mensagem.contexto if isinstance(mensagem.contexto, dict) else {}
        data_ref_raw = contexto.get("data")
        data_ref = None
        if data_ref_raw is not None:
            try:
                data_ref = calendario._parse_data_flexivel(data_ref_raw)
            except ValueError:
                data_ref = None

        t0 = time.monotonic()
        resp_cal = calendario.carregar_calendario().consultar_pergunta(
            mensagem.conteudo,
            data_referencia=data_ref,
        )
        if resp_cal is not None:
            contexto["trechos_recuperados"] = resp_cal["trechos"]
            contexto["tempo_busca_s"] = round(time.monotonic() - t0, 3)
            contexto["tempo_geracao_s"] = 0.0
            if resp_cal.get("consulta_data") is not None:
                contexto["calendario"] = resp_cal["consulta_data"]
            return Resposta(
                conteudo=resp_cal["resposta"],
                fontes=resp_cal["fontes_citadas"],
                confianca=1.0,
                alertas=[],
            )

        resposta_grafo = self.responder_grafo(mensagem)
        if resposta_grafo is not None:
            return resposta_grafo
        return executar_agente_dominio(self, mensagem)
