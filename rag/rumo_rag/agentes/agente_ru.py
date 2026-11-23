"""Agente especializado em informações do Restaurante Universitário (RU)."""

from __future__ import annotations

import re
import threading
import time
from typing import Any

from .. import config, geracao, indice
from .base import Agente
from .mensagem import Mensagem, Resposta

# Protege chamadas simultâneas ao índice vetorial/BM25 em execução paralela (ChromaDB RustBindingsAPI).
_LOCK_INDICE = threading.Lock()

_TERMOS_RU = re.compile(
    r"\b(?:"
    r"ru|restaurante(?:\s+universit[aá]rio)?|almo[cç]o|jantar|caf[eé](?:\s+da\s+manh[aã])?|"
    r"desjejum|refei[cç][aã]o|refei[cç][oõ]es|card[aá]pio|prato|monta(?:r|gem)?\s+(?:um\s+)?prato|"
    r"vegetariano|vegetariana|vegano|vegana|alerg[eê]nicos?|gl[uú]ten|lactose|calorias?|cal[oó]ric[ao]|kcal|"
    r"sem\s+(?:leite|gl[uú]ten|lactose)|aux[ií]lio\s+alimenta[cç][aã]o|pnaes|"
    r"grupo\s+(?:i{1,3}|iv)|isento|isen[cç][aã]o|bandej[aã]o|catraca"
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
    r"minha\s+agenda|minhas?\s+aulas?|agenda\s+de\s+aulas?|sala\s+d[ae]\s+aula|"
    r"[a-z]{2,4}\d{3,4}"
    r")\b",
    re.IGNORECASE,
)


def pergunta_fora_do_dominio(pergunta: str, eixo: str) -> bool:
    """Retorna True quando a pergunta pertence claramente ao outro domínio especializado."""
    if not isinstance(pergunta, str) or not pergunta.strip():
        return False
    casa_ru = bool(_TERMOS_RU.search(pergunta))
    casa_fluxo = bool(_TERMOS_FLUXO.search(pergunta))
    if eixo == "ru":
        return casa_fluxo and not casa_ru
    if eixo == "fluxo":
        return casa_ru and not casa_fluxo
    return False


def executar_agente_dominio(agente: Any, mensagem: Mensagem) -> Resposta:
    """Fluxo compartilhado (Opção A): guarda de domínio, busca via pesquisar(), geração e higienização."""
    contexto = mensagem.contexto if isinstance(mensagem.contexto, dict) else {}
    backend = contexto.get("backend", config.BACKEND)

    if pergunta_fora_do_dominio(mensagem.conteudo, agente.eixo):
        contexto["trechos_recuperados"] = []
        contexto["tempo_busca_s"] = 0.0
        contexto["tempo_geracao_s"] = 0.0
        return Resposta(
            conteudo=geracao.RECUSA,
            fontes=[],
            confianca=0.0,
            alertas=[f"Pergunta fora do domínio do {agente.nome}."],
        )

    t0 = time.monotonic()
    resultado = agente.pesquisar(mensagem.conteudo)
    t1 = time.monotonic()

    trechos = resultado["trechos"]
    contexto["trechos_recuperados"] = trechos

    trechos_norm = [
        {
            "chunk_id": t.get("chunk_id") or "",
            "doc_id": t.get("doc_id") or "",
            "titulo": t.get("titulo") or "",
            "orgao": t.get("orgao") or "",
            "pagina": t.get("pagina") if t.get("pagina") is not None else "",
            "secao": t.get("secao") or "",
            "url": t.get("url") or "",
            "texto": t.get("texto") or "",
        }
        for t in trechos
    ]

    texto = geracao.gerar_com_instrucoes(
        resultado["pergunta"],
        trechos_norm,
        instrucoes=agente.instrucoes,
        backend=backend,
    )
    t2 = time.monotonic()

    contexto["tempo_busca_s"] = round(t1 - t0, 3)
    contexto["tempo_geracao_s"] = round(t2 - t1, 3)

    alertas: list[str] = []
    if not trechos:
        alertas.append(f"Nenhum trecho encontrado no eixo {agente.eixo.upper()}.")

    if geracao.eh_recusa(texto):
        return Resposta(
            conteudo=geracao.RECUSA,
            fontes=[],
            confianca=0.0,
            alertas=alertas,
        )

    fontes_citadas = geracao.citacoes_usadas(texto, trechos_norm)
    for fonte in fontes_citadas:
        idx = fonte.get("n", 0) - 1
        if 0 <= idx < len(trechos) and not fonte.get("secao"):
            fonte["secao"] = trechos[idx].get("secao")

    if trechos:
        sims = [
            float(t["similaridade"])
            for t in trechos
            if t.get("similaridade") is not None
        ]
        confianca: float | None = round(sum(sims) / len(sims), 4) if sims else 1.0
    else:
        confianca = 0.0

    if geracao.resposta_sem_citacao(texto, trechos_norm):
        alertas.append("Resposta afirmativa sem citação [n] (RN-02)")
    if valores := geracao.valores_sem_fonte(texto, trechos_norm):
        alertas.append(f"Valores sem respaldo nos trechos: {', '.join(valores)}")

    return Resposta(
        conteudo=texto,
        fontes=fontes_citadas,
        confianca=confianca,
        alertas=alertas,
    )


INSTRUCOES_RU = f"""Você é o Agente RU do sistema RUmo, especialista exclusivo no Restaurante Universitário da UnB (campus Gama/FCTE).
Seu domínio cobre APENAS cardápios semanais (café da manhã, almoço e jantar), opções vegetarianas/veganas, alergênicos (leite, glúten e derivados), valores das refeições, grupos de pagamento I a IV, isenção, auxílio alimentação (PNAES) e horários do RU.
Regras:
1. Responda em português, de forma direta, usando SOMENTE as informações dos trechos numerados abaixo e APENAS sobre o Restaurante Universitário. Ignore ou recuse qualquer tema sobre disciplinas, pré-requisitos, fluxogramas ou cursos.
2. OBRIGATÓRIO: depois de cada afirmação ou item de lista, termine com a citação do trecho entre colchetes, por exemplo [1] ou [2][3]. Nunca omita [n] em listas.
3. Se os trechos não trazem a resposta sobre o RU, diga exatamente: "{geracao.RECUSA}" e não sugira assuntos fora do RU. Não invente pratos, ingredientes, valores ou datas.
4. Quando o valor ou o acesso depender do grupo de pagamento (I, II, III ou IV) ou do vínculo do estudante, informe exatamente essa condição segundo os trechos.
5. Seja conciso: no máximo 120 palavras. Copie datas, horários, preparações e valores exatamente como estão nos trechos."""


class AgenteRU(Agente):
    """Agente especialista em Restaurante Universitário (preços, cardápio, horários, auxílio)."""

    nome = "Agente RU"
    papel = (
        "Especialista em informações do Restaurante Universitário "
        "(cardápio, preços, horários, isenção e auxílio)"
    )
    eixo = "ru"
    instrucoes = INSTRUCOES_RU
    ferramentas = ("cardapio_do_dia", "montar_prato")

    def __init__(
        self,
        k: int = config.TOP_K,
        modo: str = "hibrido",
    ):
        # Valida a quantidade de trechos que serão recuperados.
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("O parâmetro k deve ser um inteiro positivo.")

        # Valida o método de recuperação.
        if modo not in ("denso", "bm25", "hibrido"):
            raise ValueError("Modo de busca inválido.")

        self.k = k
        self.modo = modo

    def pesquisar(self, pergunta: str) -> dict:
        """
        Pesquisa informações do Restaurante Universitário.

        Recebe uma pergunta do Orquestrador e retorna os
        trechos recuperados e suas respectivas fontes.
        """

        # Valida a pergunta recebida.
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("A pergunta não pode estar vazia.")

        pergunta = pergunta.strip()

        # Busca restrita aos documentos do eixo RU.
        # A decomposição fica sob responsabilidade do Orquestrador.
        with _LOCK_INDICE:
            trechos = indice.buscar(
                pergunta,
                k=self.k,
                modo=self.modo,
                eixo=self.eixo,
                decompor_pergunta=False,
            )

        # Organiza as fontes sem duplicar a mesma página.
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
                        "doc_id",
                        "titulo",
                        "orgao",
                        "pagina",
                        "secao",
                        "url",
                        "chunk_id",
                    )
                })

        # Retorna os resultados para o Orquestrador.
        return {
            "agente": self.nome,
            "eixo": self.eixo,
            "pergunta": pergunta,
            "encontrou": bool(trechos),
            "trechos": trechos,
            "fontes": fontes,
        }

    def montar_mensagens(self, pergunta: str, trechos: list[dict]) -> list[dict]:
        """Monta as mensagens para o LLM usando o prompt especializado do Agente RU."""
        return geracao.montar_mensagens(pergunta, trechos, instrucoes=self.instrucoes)

    def responder_ferramenta(self, mensagem: Mensagem) -> Resposta | None:
        """Executa ferramenta estruturada do Agente RU quando a consulta pede cardápio/montagem."""
        if pergunta_fora_do_dominio(mensagem.conteudo, self.eixo):
            return None
        from . import ferramentas

        contexto = mensagem.contexto if isinstance(mensagem.contexto, dict) else {}
        mensagem.contexto = contexto
        chamada = ferramentas.extrair_chamada_ru(mensagem.conteudo, contexto)
        if chamada is None:
            return None

        nome_ferr, args = chamada
        t0 = time.monotonic()
        fn = getattr(ferramentas, nome_ferr)
        res = fn(**args)
        duracao = round(time.monotonic() - t0, 3)

        contexto["ferramenta_chamada"] = res.para_trace()
        contexto["dado_estruturado"] = res.dados
        contexto["trechos_recuperados"] = list(res.trechos_evidencia)
        contexto["tempo_busca_s"] = duracao
        contexto["tempo_geracao_s"] = 0.0
        return Resposta(
            conteudo=res.texto_base,
            fontes=list(res.fontes),
            confianca=0.0 if res.recusado else 1.0,
            alertas=list(res.alertas),
        )

    def executar(self, mensagem: Mensagem) -> Resposta:
        """Executa ferramenta estruturada quando aplicável ou segue busca RAG + geração."""
        resposta_ferr = self.responder_ferramenta(mensagem)
        if resposta_ferr is not None:
            return resposta_ferr
        return executar_agente_dominio(self, mensagem)
