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

# Calibrado em BM25 com as perguntas-ouro: D7 fora da base max=9,036;
# menor positivo sem termos de domínio (Q12) max=9,551 no eixo Fluxo.
LIMIAR_BM25_SEM_DOMINIO = 9.3

_TERMOS_RU = re.compile(
    r"\b(?:"
    r"ru|restaurante(?:\s+universit[aá]rio)?|almo[cç]o|jantar|caf[eé](?:\s+da\s+manh[aã])?|"
    r"desjejum|refei[cç][aã]o|refei[cç][oõ]es|card[aá]pio|prato|monta(?:r|gem)?\s+(?:um\s+)?prato|"
    r"vegetariano|vegetariana|vegano|vegana|alerg[eê]nicos?|alergia|intoler[aâ]ncia|cel[ií]ac[oa]s?|"
    r"gl[uú]ten|trigo|lactose|leite|soja|amendoim|oleaginosas?|cogumelos?|su[ií]n[oa]|ovos?|pimenta|mel|"
    r"calorias?|cal[oó]ric[ao]|kcal|nutricional|dietas?|sem\s+(?:leite|gl[uú]ten|lactose)|"
    r"aux[ií]lio\s+alimenta[cç][aã]o|pnaes|"
    r"grupo\s+(?:i{1,3}|iv)|isento|isen[cç][aã]o|bandej[aã]o|catraca"
    r")\b",
    re.IGNORECASE,
)

_TERMOS_FLUXO = re.compile(
    r"\b(?:"
    r"fluxo|fluxograma|disciplina|disciplinas|mat[eé]ria|mat[eé]rias|"
    r"pr[eé]-?requisitos?|co-?requisitos?|requisito|cr[eé]ditos?|semestre|semestres|grade|matriz|curricular|"
    r"ppc|curso|cursos|engenharia|software|aeroespacial|automotiva|eletr[oô]nica|energia|"
    r"biom[eé]dica|ppgeb|mestrado|matr[ií]cula|trancamento|sigaa|ira|est[aá]gio|tcc|"
    r"optativa|obrigat[oó]ria|abi|c[aá]lculo|f[ií]sica|testes\s+de\s+software|termodin[aâ]mica|"
    r"reprov\w*|trava\w*|destrava\w*|gargalo|caminho\s+cr[ií]tico|"
    r"minha\s+agenda|minhas?\s+aulas?|agenda\s+de\s+aulas?|sala\s+d[ae]\s+aula|"
    r"calend[aá]rio(?:\s+acad[eê]mico)?|feriados?|pontos?\s+facultativos?|recesso|"
    r"semana\s+universit[aá]ria|semana\s+de\s+provas|per[ií]odo\s+letivo|"
    r"tem\s+aula|h[aá]\s+aula|vai\s+ter\s+aula|in[ií]cio\s+das\s+aulas|t[eé]rmino\s+das\s+aulas|"
    r"[a-z]{2,4}\d{3,4}"
    r")\b",
    re.IGNORECASE,
)

_ANOTACAO_DATA_API = re.compile(
    r"\s*\((?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)[^)]*\d{2}/\d{2}/\d{4}[^)]*\)\s*$",
    re.IGNORECASE,
)


def _sem_anotacao_data(texto: str) -> str:
    """Remove o sufixo parentético de `api.com_data()` para evitar falsos cruzamentos de domínio."""
    return _ANOTACAO_DATA_API.sub("", texto).strip()


def pergunta_fora_do_dominio(pergunta: str, eixo: str) -> bool:
    """Retorna True quando a pergunta pertence claramente ao outro domínio especializado."""
    if not isinstance(pergunta, str) or not pergunta.strip():
        return False
    base = _sem_anotacao_data(pergunta)
    casa_ru = bool(_TERMOS_RU.search(base))
    casa_fluxo = bool(_TERMOS_FLUXO.search(base))
    if eixo == "ru":
        return casa_fluxo and not casa_ru
    if eixo == "fluxo":
        return casa_ru and not casa_fluxo
    return False


def pergunta_sem_dominio(pergunta: str) -> bool:
    """Retorna True quando a pergunta não contém sinais dos domínios RU nem Fluxo."""
    if not isinstance(pergunta, str) or not pergunta.strip():
        return True
    base = _sem_anotacao_data(pergunta)
    return not _TERMOS_RU.search(base) and not _TERMOS_FLUXO.search(base)


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

    if backend == "extrativo" and pergunta_sem_dominio(mensagem.conteudo):
        scores = [float(t["score_bm25"]) for t in trechos if t.get("score_bm25") is not None]
        if scores and max(scores) < LIMIAR_BM25_SEM_DOMINIO:
            contexto["trechos_recuperados"] = []
            contexto["tempo_busca_s"] = round(t1 - t0, 3)
            contexto["tempo_geracao_s"] = 0.0
            return Resposta(
                conteudo=geracao.RECUSA,
                fontes=[],
                confianca=0.0,
                alertas=["Pergunta sem termos de domínio e com relevância BM25 abaixo do limiar."],
            )

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
    if resultado.get("aviso_cardapio"):
        alertas.append(resultado["aviso_cardapio"])
    elif not trechos:
        alertas.append(f"Nenhum trecho encontrado no eixo {agente.eixo.upper()}.")

    if not trechos and resultado.get("aviso_cardapio"):
        return Resposta(
            conteudo=geracao.RECUSA,
            fontes=[],
            confianca=0.0,
            alertas=alertas,
        )

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
Seu domínio cobre APENAS cardápios semanais (café da manhã, almoço e jantar), opções vegetarianas/veganas, os 10 alergênicos oficiais (cogumelo, leite e derivados, mel, pimenta, soja, trigo/glúten, amendoim, oleaginosa, ovo e suíno), valores das refeições, grupos de pagamento I a IV, isenção, auxílio alimentação (PNAES) e horários do RU.
Regras:
1. Responda em português, de forma direta, usando SOMENTE as informações dos trechos numerados abaixo e APENAS sobre o Restaurante Universitário. Ignore ou recuse qualquer tema sobre disciplinas, pré-requisitos, fluxogramas ou cursos.
2. OBRIGATÓRIO: depois de cada afirmação ou item de lista, termine com a citação do trecho entre colchetes, por exemplo [1] ou [2][3]. Nunca omita [n] em listas.
3. Se os trechos não trazem a resposta sobre o RU, diga exatamente: "{geracao.RECUSA}" e não sugira assuntos fora do RU. Não invente pratos, ingredientes, calorias, valores nutricionais ou datas; nunca estime informações não publicadas. Caso algum item tenha aviso "a conferir na distribuição", oriente a confirmar na linha de distribuição.
4. Quando o valor ou o acesso depender do grupo de pagamento (I, II, III ou IV) ou do vínculo do estudante, informe exatamente essa condição segundo os trechos. Se a pergunta mencionar auxílio alimentação ou bolsa alimentação, destaque a gratuidade/isenção do Grupo I prevista nos trechos e NUNCA aplique os valores do Grupo II a beneficiários do auxílio.
5. Seja conciso: no máximo 120 palavras. Copie datas, horários, preparações e valores exatamente como estão nos trechos."""


_CONSULTA_CARDAPIO = re.compile(
    r"\b(?:"
    r"card[aá]pio|prato|pratos|prote[ií]na|salada|sobremesa|sopa|guarni[cç][aã]o|"
    r"acompanhamento|fruta|bebida|refresco|panifica[cç][aã]o|vegetariano|vegetariana|"
    r"vegano|vegana|ovolactovegetariano|alerg[eê]nicos?|gl[uú]ten|trigo|lactose|leite|"
    r"soja|amendoim|oleaginosas?|cogumelos?|su[ií]n[oa]|ovos?|pimenta|mel|derivados\s+de\s+leite|"
    r"o\s+que\s+tem|o\s+que\s+vai\s+ter|servid[oa]|"
    r"(?:qual|que)\s+dia(?:\s+(?:d?esta|d?essa|na|da)\s+semana)?\s+(?:tem|vai\s+ter|servem|servid[oa])|"
    r"(?:almo[cç]o|jantar|caf[eé](?:\s+da\s+manh[aã])?|desjejum)\s+de\s+(?:hoje|amanh[ãa])|"
    r"servem\s+no\s+(?:almo[cç]o|jantar|caf[eé]|desjejum)|"
    r"segunda|ter[cç]a|quarta|quinta|sexta"
    r")\b",
    re.IGNORECASE,
)

_CONSULTA_NAO_CARDAPIO = re.compile(
    r"\b(?:"
    r"quanto\s+custa|pre[cç]o|pre[cç]os|valor|valores|taxa|paga|grupo\s+(?:i{1,3}|iv)|"
    r"isen[cç][aã]o|isento|aux[ií]lio|bolsa|pnaes|edital|catraca|carteirinha|qr\s*code|"
    r"hor[aá]rio|que\s+horas|at[eé]\s+que\s+horas|abre|funciona|funcionamento|documentos"
    r")\b",
    re.IGNORECASE,
)

_CONSULTA_NUTRICIONAL = re.compile(
    r"\b(?:calorias?|kcal|informa[cç][aã]o\s+nutricional|ficha\s+t[eé]cnica)\b",
    re.IGNORECASE,
)

_CONSULTA_POLITICA_ALIMENTAR = re.compile(
    r"\b(?:"
    r"dietas?\s+(?:especializadas?|individualizadas?|restritivas?)|"
    r"doen[cç]a\s+cel[ií]aca|cel[ií]ac[oa]s?|"
    r"atende\s+(?:dieta|intolerante|cel[ií]ac[oa]s?)|"
    r"servi[cç]o\s+de?\s*alimenta[cç][aã]o|restaurante\s+executivo|"
    r"quais\s+alerg[eê]nicos\s+o\s+ru\s+(?:identifica|sinaliza|informa|lista)"
    r")\b",
    re.IGNORECASE,
)

_ESPECIFICA_DATA_OU_REFEICAO = re.compile(
    r"\b(?:"
    r"hoje|amanh[ãa]|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo|"
    r"almo[cç]o|jantar|janta|caf[eé](?:\s+da\s+manh[aã])?|desjejum"
    r")\b|\b\d{1,2}/\d{1,2}\b",
    re.IGNORECASE,
)


def _eh_pergunta_cardapio(pergunta: str) -> bool:
    """Identifica perguntas sobre o cardápio/alergênicos (separando de preços, horários e normas)."""
    if _CONSULTA_NUTRICIONAL.search(pergunta):
        return False
    if _CONSULTA_POLITICA_ALIMENTAR.search(pergunta) and not _ESPECIFICA_DATA_OU_REFEICAO.search(pergunta):
        return False
    if not _CONSULTA_CARDAPIO.search(pergunta):
        return False
    if _CONSULTA_NAO_CARDAPIO.search(pergunta) and not re.search(
        r"\b(?:card[aá]pio|prato|prote[ií]na|alerg[eê]nicos?|gl[uú]ten|trigo|lactose|leite|"
        r"soja|amendoim|oleaginosas?|cogumelos?|su[ií]n[oa]|ovos?|pimenta|mel|derivados\s+de\s+leite|o\s+que\s+tem)\b",
        pergunta,
        re.IGNORECASE,
    ):
        return False
    return True


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

        if _eh_pergunta_cardapio(pergunta):
            from ..coleta import cardapio

            dados_semana, motivo = cardapio.carregar_semana_atual()
            if dados_semana is None:
                return {
                    "agente": self.nome,
                    "eixo": self.eixo,
                    "pergunta": pergunta,
                    "encontrou": False,
                    "trechos": [],
                    "fontes": [],
                    "aviso_cardapio": motivo,
                }
            trechos = cardapio.trechos_da_semana(dados_semana, pergunta)
        else:
            eh_grupo_i = bool(
                re.search(
                    r"\b(?:(?:aux[ií]lio|bolsa)\s+alimenta[cç][aã]o|grupo\s+i(?![iv]))\b",
                    pergunta,
                    re.I,
                )
                and re.search(
                    r"\b(?:pre[cç]o|valor|subsidiad[oa]|quanto\s+custa|paga|isento|isen[cç][aã]o)\b",
                    pergunta,
                    re.I,
                )
            )
            # Busca restrita aos documentos normativos/informativos do eixo RU.
            with _LOCK_INDICE:
                trechos = indice.buscar(
                    pergunta,
                    k=self.k,
                    modo=self.modo,
                    eixo=self.eixo,
                    decompor_pergunta=False,
                )
                if eh_grupo_i:
                    extras = indice.buscar(
                        "Programa Auxílio Alimentação gratuidade isenção Grupo I",
                        k=2,
                        modo=self.modo,
                        eixo=self.eixo,
                        decompor_pergunta=False,
                    )
                    vistos = {t.get("chunk_id") for t in extras}
                    trechos = (extras + [t for t in trechos if t.get("chunk_id") not in vistos])[:self.k]

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
        duracao_ferr = round(time.monotonic() - t0, 3)

        backend = contexto.get("backend", config.BACKEND)
        texto_final, duracao_ger, alertas_final, redigido_llm = ferramentas.redigir_com_ferramenta(
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
        contexto["tempo_busca_s"] = duracao_ferr
        contexto["tempo_geracao_s"] = duracao_ger
        return Resposta(
            conteudo=texto_final,
            fontes=list(res.fontes),
            confianca=0.0 if res.recusado else 1.0,
            alertas=alertas_final,
        )

    def executar(self, mensagem: Mensagem) -> Resposta:
        """Executa ferramenta estruturada quando aplicável ou segue busca RAG + geração."""
        resposta_ferr = self.responder_ferramenta(mensagem)
        if resposta_ferr is not None:
            return resposta_ferr
        return executar_agente_dominio(self, mensagem)
