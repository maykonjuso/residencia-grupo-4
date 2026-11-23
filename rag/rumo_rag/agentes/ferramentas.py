"""Camada de ferramentas estruturadas dos agentes RUmo (#62).

Cada ferramenta retorna ``ResultadoFerramenta`` contendo dados estruturados
e procedência documental, permitindo ao agente redigir com base factual e
à interface desenhar componentes a partir da mesma fonte de verdade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

from .. import config, geracao
from ..coleta import cardapio
from ..grafo_curricular import carregar_grafo_f16

_DIAS_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

_DIAS_CURTOS = {
    "segunda": "segunda-feira",
    "segunda-feira": "segunda-feira",
    "terca": "terça-feira",
    "terca-feira": "terça-feira",
    "quarta": "quarta-feira",
    "quarta-feira": "quarta-feira",
    "quinta": "quinta-feira",
    "quinta-feira": "quinta-feira",
    "sexta": "sexta-feira",
    "sexta-feira": "sexta-feira",
    "sabado": "sábado",
    "domingo": "domingo",
}

_MAPA_SEMANA_IDX = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}

_RESTRICAO_NAO_SUPORTADA = re.compile(
    r"\b(?:calor\w*|kcal|prote[ií]na\w*\s+em\s+gramas?|gramas?\s+de\s+prote[ií]na|"
    r"carboidrat\w*|low[\s-]?carb|cetog[eê]nic\w*|s[oó]dio|hiposs[oó]dic\w*|"
    r"diab[eé]t\w*|hipertens\w*|gordura\w*|macro(?:nutriente)?s?|emagrec\w*|"
    r"dieta\s+especial\w*|sem\s+a[cç][uú]car|zero\s+a[cç][uú]car)\b",
    re.I,
)

_EXCLUSAO_ALERGENICOS = (
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de|alergi\w*\s+a)\s+(?:leite|lactose|laticin\w*)\b", re.I), "leite"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de|alergi\w*\s+a)\s+(?:gluten|trigo)\b|\bceliac\w*\b", re.I), "gluten"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de|alergi\w*\s+a)\s+soja\b", re.I), "soja"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de|alergi\w*\s+a)\s+ovos?\b", re.I), "ovo"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de)\s+(?:suin[oa]|porco)\b", re.I), "suino"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de|alergi\w*\s+a)\s+amendoim\b", re.I), "amendoim"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de)\s+pimenta\b", re.I), "pimenta"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de)\s+cogumelos?\b", re.I), "cogumelo"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de)\s+mel\b", re.I), "mel"),
    (re.compile(r"\b(?:sem|nao\s+contem|livre\s+de|alergi\w*\s+a)\s+oleaginosas?\b", re.I), "oleaginosa"),
)


def _norm(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in sem if not unicodedata.combining(c)).split())


@dataclass
class ResultadoFerramenta:
    """Retorno estruturado e com procedência de uma ferramenta de agente."""

    ferramenta: str
    argumentos: dict[str, Any]
    dono: str
    sucesso: bool
    recusado: bool
    motivo_recusa: str | None = None
    dados: dict[str, Any] = field(default_factory=dict)
    fontes: list[dict[str, Any]] = field(default_factory=list)
    trechos_evidencia: list[dict[str, Any]] = field(default_factory=list)
    texto_base: str = ""
    alertas: list[str] = field(default_factory=list)

    def para_trace(self) -> dict[str, Any]:
        return {
            "nome": self.ferramenta,
            "argumentos": dict(self.argumentos),
            "dono": self.dono,
            "sucesso": self.sucesso,
            "recusado": self.recusado,
            "motivo_recusa": self.motivo_recusa,
        }

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalizar_data(valor: str | date | None, hoje: date | None = None) -> str:
    ref = hoje or date.today()
    if valor is None:
        return ref.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    bruto = _norm(str(valor).strip())
    if not bruto or bruto == "hoje":
        return ref.isoformat()
    if bruto == "amanha":
        return (ref + timedelta(days=1)).isoformat()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", bruto):
        date.fromisoformat(bruto)
        return bruto
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", bruto):
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})", bruto):
        return date(ref.year, int(m.group(2)), int(m.group(1))).isoformat()
    for chave, alvo_idx in _MAPA_SEMANA_IDX.items():
        if bruto.startswith(chave):
            inicio_semana = ref - timedelta(days=ref.weekday())
            return (inicio_semana + timedelta(days=alvo_idx)).isoformat()
    raise ValueError(f"Data inválida para ferramenta de cardápio: {valor!r}")


def _na_semana_atual(data_iso: str, hoje: date | None = None) -> bool:
    ref = hoje or date.today()
    inicio = ref - timedelta(days=ref.weekday())
    fim = inicio + timedelta(days=6)
    return inicio <= date.fromisoformat(data_iso) <= fim


def _filtrar_refeicoes(dados: dict, data_iso: str, ref_norm: str | None) -> list[dict]:
    return [
        r for r in dados.get("refeicoes", [])
        if r.get("data") == data_iso and (not ref_norm or r.get("refeicao") == ref_norm)
    ]


def _carregar_cardapios(
    data_iso: str,
    ref_norm: str | None,
    atualizar_se_ausente: bool | None = None,
) -> tuple[list[dict], dict | None]:
    caminho_semanal = getattr(config, "CARDAPIO_SEMANAL_JSON", config.DADOS / "cardapio_semanal.json")
    dados_local, _ = cardapio.ler_semana_json(caminho_semanal if isinstance(caminho_semanal, Path) else None)
    semana_local = dict(dados_local["semana"]) if dados_local else None
    if dados_local:
        encontrados = _filtrar_refeicoes(dados_local, data_iso, ref_norm)
        if encontrados:
            return encontrados, {
                "status": "atualizado_cache",
                "semana_local": semana_local,
                "motivo": None,
                "ultima_semana_publicada": semana_local,
            }

    deve_atualizar = getattr(config, "CARDAPIO_AUTO_FETCH", True) if atualizar_se_ausente is None else atualizar_se_ausente
    info_sync: dict | None = None
    if deve_atualizar and _na_semana_atual(data_iso):
        dados_novos, info_sync = cardapio.sincronizar_semana_atual(
            referencia=date.fromisoformat(data_iso),
            caminho=caminho_semanal if isinstance(caminho_semanal, Path) else None,
        )
        if dados_novos:
            encontrados = _filtrar_refeicoes(dados_novos, data_iso, ref_norm)
            if encontrados:
                return encontrados, info_sync

    if config.CHUNKS.exists():
        chunks = cardapio.carregar_chunks_cardapio()
        encontrados = cardapio.buscar(data_iso, ref_norm, chunks=chunks)
        if encontrados:
            return encontrados, info_sync

    if not info_sync and semana_local:
        info_sync = {
            "status": "desatualizado_local",
            "semana_local": semana_local,
            "motivo": None,
            "ultima_semana_publicada": None,
        }
    return [], info_sync


def _fontes_e_trechos_cardapio(resultados: list[dict], data_iso: str) -> tuple[list[dict], list[dict], str]:
    fontes: list[dict] = []
    trechos: list[dict] = []
    linhas_texto: list[str] = []
    dt = date.fromisoformat(data_iso)
    data_br = f"{dt:%d/%m/%Y}"
    dia_nome = _DIAS_SEMANA[dt.weekday()]

    for idx, r in enumerate(resultados, start=1):
        f = dict(r.get("fonte") or {})
        ref_nome = cardapio.REFEICOES.get(r.get("refeicao", ""), r.get("refeicao", ""))
        secao = f"{ref_nome} · {dia_nome} {data_br}"
        fonte = {
            "n": idx,
            "doc_id": f.get("doc_id") or "",
            "titulo": f"Cardápio semanal do RU Gama — {secao}",
            "orgao": "UnB · Diretoria do RU",
            "pagina": f.get("pagina") or 1,
            "secao": secao,
            "url": f.get("url") or "",
            "chunk_id": f.get("chunk_id") or "",
        }
        fontes.append(fonte)

        partes_comp = [f"Cardápio do RU Gama — {secao}:"]
        for comp in r.get("compartimentos", []):
            itens_txt = []
            for o in comp.get("opcoes", []):
                trilha = f" ({o['trilha']})" if o.get("trilha") not in (None, "todas") else ""
                alerg = f" [Alergênicos: {', '.join(o['alergenicos'])}]" if o.get("alergenicos") else ""
                itens_txt.append(f"{o['nome']}{trilha}{alerg}")
            partes_comp.append(f"- {comp['titulo']}: {'; '.join(itens_txt)}")
        if r.get("mesa_apoio"):
            partes_comp.append(f"Mesa de apoio: {', '.join(r['mesa_apoio'])}.")
        evidencia = "\n".join(partes_comp)
        trechos.append({**fonte, "texto": evidencia, "similaridade": 1.0})
        linhas_texto.append(f"{ref_nome} ({dia_nome}, {data_br}) [{idx}]: " + " | ".join(partes_comp[1:]))

    return fontes, trechos, "\n".join(linhas_texto)


def _formatar_intervalo_br(sem: dict | None) -> str | None:
    if not sem or "inicio" not in sem or "fim" not in sem:
        return None
    try:
        ini = date.fromisoformat(sem["inicio"])
        fim = date.fromisoformat(sem["fim"])
        return f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}"
    except Exception:
        return None


def _motivo_ausencia_cardapio(data_iso: str, ref_norm: str | None, info_sync: dict | None) -> str:
    sufixo_ref = f" ({ref_norm})" if ref_norm else ""
    if info_sync:
        status = info_sync.get("status")
        origem = info_sync.get("status_origem")
        efetivo = origem if status == "em_cooldown" and origem else status
        intervalo_pub = _formatar_intervalo_br(info_sync.get("ultima_semana_publicada"))
        intervalo_loc = _formatar_intervalo_br(info_sync.get("semana_local"))
        if efetivo == "unb_nao_publicou":
            detalhe = f" Última semana publicada: {intervalo_pub}." if intervalo_pub else ""
            return (
                f"A UnB ainda não publicou o cardápio oficial do RU Gama para a semana de "
                f"{data_iso}{sufixo_ref}.{detalhe}"
            )
        if efetivo == "erro_coleta":
            motivo = info_sync.get("motivo") or "falha de rede ao consultar o site da UnB"
            return (
                f"Não há cardápio registrado na base para {data_iso}{sufixo_ref} e não foi possível "
                f"consultar o site da UnB ({motivo})."
            )
        if intervalo_loc:
            return (
                f"Não há cardápio registrado na base para {data_iso}{sufixo_ref} "
                f"(o cardápio local disponível cobre {intervalo_loc})."
            )
    return f"Não há cardápio registrado na base para {data_iso}" + (f" ({ref_norm})." if ref_norm else ".")


def cardapio_do_dia(
    data: str | date | None = None,
    refeicao: str | None = None,
    atualizar_se_ausente: bool | None = None,
) -> ResultadoFerramenta:
    """Devolve compartimentos, opções estruturadas e procedência para `data` e `refeicao`."""
    try:
        data_iso = _normalizar_data(data)
        ref_norm = cardapio.normalizar_refeicao(refeicao) if refeicao else None
    except ValueError as exc:
        msg = str(exc)
        return ResultadoFerramenta(
            ferramenta="cardapio_do_dia",
            argumentos={"data": str(data), "refeicao": refeicao},
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=msg,
            dados={"data": str(data), "refeicao": refeicao, "cardapios": []},
            texto_base=geracao.RECUSA,
            alertas=[msg],
        )

    args = {"data": data_iso, "refeicao": ref_norm}
    resultados, info_sync = _carregar_cardapios(data_iso, ref_norm, atualizar_se_ausente=atualizar_se_ausente)
    if not resultados:
        motivo = _motivo_ausencia_cardapio(data_iso, ref_norm, info_sync)
        dados_recusa: dict[str, Any] = {"data": data_iso, "refeicao": ref_norm, "cardapios": []}
        if info_sync:
            dados_recusa["sincronizacao"] = info_sync
        return ResultadoFerramenta(
            ferramenta="cardapio_do_dia",
            argumentos=args,
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo,
            dados=dados_recusa,
            texto_base=geracao.RECUSA,
            alertas=[motivo],
        )

    fontes, trechos, texto_base = _fontes_e_trechos_cardapio(resultados, data_iso)
    dados_ok: dict[str, Any] = {"data": data_iso, "refeicao": ref_norm, "cardapios": resultados}
    if info_sync:
        dados_ok["sincronizacao"] = info_sync
    return ResultadoFerramenta(
        ferramenta="cardapio_do_dia",
        argumentos=args,
        dono="Agente RU",
        sucesso=True,
        recusado=False,
        dados=dados_ok,
        fontes=fontes,
        trechos_evidencia=trechos,
        texto_base=texto_base,
    )


def _interpretar_restricoes(restricoes: list[str] | tuple[str, ...] | None) -> tuple[str | None, set[str], str | None]:
    """Retorna (trilha_preferida, alergenicos_evitar, motivo_nao_suportado)."""
    lista = [str(r).strip() for r in (restricoes or []) if str(r).strip()]
    trilha: str | None = None
    evitar: set[str] = set()
    for item in lista:
        norm = _norm(item)
        if _RESTRICAO_NAO_SUPORTADA.search(norm):
            return (
                None,
                set(),
                (
                    f"Restrição '{item}' exige dados nutricionais ou calóricos que não constam "
                    "nas fontes oficiais do RU."
                ),
            )
        if "vegano" in norm or "vegetariano estrito" in norm:
            trilha = "vegano"
            evitar.update({"leite", "ovo", "mel", "suino"})
        elif "ovolacto" in norm or "vegetariano" in norm:
            trilha = "ovolacto"
            evitar.add("suino")
        elif "padrao" in norm:
            trilha = "padrao"

        for padrao, alerg_id in _EXCLUSAO_ALERGENICOS:
            if padrao.search(norm):
                evitar.add(alerg_id)
        for alerg_id in ("leite", "gluten", "soja", "ovo", "suino", "amendoim", "pimenta", "cogumelo", "mel", "oleaginosa"):
            if norm == f"sem {alerg_id}" or norm == alerg_id:
                evitar.add(alerg_id)
    return trilha, evitar, None


def _justificativa_opcao(opcao: dict, comp_titulo: str, trilha_pedida: str | None, evitar: set[str]) -> str:
    partes: list[str] = [f"{comp_titulo}: {opcao['nome']}"]
    trilha_op = opcao.get("trilha", "todas")
    if trilha_pedida == "vegano":
        if trilha_op == "vegano":
            partes.append("selecionado da trilha vegetariano estrito (vegano)")
        else:
            partes.append("compatível com a trilha vegana (sem ingredientes de origem animal anotados)")
    elif trilha_pedida == "ovolacto":
        if trilha_op in ("ovolacto", "vegano"):
            partes.append(f"compatível com a trilha ovolactovegetariana ({trilha_op})")
        else:
            partes.append("item neutro do compartimento")
    elif trilha_op != "todas":
        partes.append(f"trilha {trilha_op}")
    else:
        partes.append("item disponível no compartimento")

    alergs_op = opcao.get("alergenicos") or []
    if evitar:
        partes.append("sem restrições de " + ", ".join(sorted(evitar)))
    elif alergs_op:
        partes.append("contém alergênicos anotados: " + ", ".join(alergs_op))
    return "; ".join(partes) + "."


def montar_prato(
    data: str | date | None = None,
    refeicao: str = "almoco",
    restricoes: list[str] | tuple[str, ...] | None = None,
    atualizar_se_ausente: bool | None = None,
) -> ResultadoFerramenta:
    """Monta um prato compatível a partir do cardápio estruturado, justificando cada escolha."""
    lista_restr = [str(r).strip() for r in (restricoes or []) if str(r).strip()]
    try:
        data_iso = _normalizar_data(data)
        ref_norm = cardapio.normalizar_refeicao(refeicao or "almoco")
    except ValueError as exc:
        msg = str(exc)
        return ResultadoFerramenta(
            ferramenta="montar_prato",
            argumentos={"data": str(data), "refeicao": refeicao, "restricoes": lista_restr},
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=msg,
            dados={"data": str(data), "refeicao": refeicao, "restricoes": lista_restr, "prato": []},
            texto_base=geracao.RECUSA,
            alertas=[msg],
        )

    args = {"data": data_iso, "refeicao": ref_norm, "restricoes": lista_restr}
    trilha_pedida, evitar, motivo_nao_suportado = _interpretar_restricoes(lista_restr)
    if motivo_nao_suportado:
        return ResultadoFerramenta(
            ferramenta="montar_prato",
            argumentos=args,
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo_nao_suportado,
            dados={**args, "prato": [], "motivo_recusa": motivo_nao_suportado},
            texto_base=geracao.RECUSA,
            alertas=[motivo_nao_suportado],
        )

    res_card = cardapio_do_dia(data=data_iso, refeicao=ref_norm, atualizar_se_ausente=atualizar_se_ausente)
    if res_card.recusado or not res_card.dados.get("cardapios"):
        dados_recusa = {**args, "prato": []}
        if "sincronizacao" in res_card.dados:
            dados_recusa["sincronizacao"] = res_card.dados["sincronizacao"]
        return ResultadoFerramenta(
            ferramenta="montar_prato",
            argumentos=args,
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=res_card.motivo_recusa,
            dados=dados_recusa,
            texto_base=geracao.RECUSA,
            alertas=list(res_card.alertas),
        )

    card_ref = res_card.dados["cardapios"][0]
    alerg_meta = card_ref.get("alergenicos") or {}
    # Se foi pedida exclusão específica de alergênico (não só trilha) e o cardápio não tem anotação, recusa.
    exclusao_explicitamente_pedida = any(
        pad.search(_norm(r)) for r in lista_restr for pad, _ in _EXCLUSAO_ALERGENICOS
    )
    if exclusao_explicitamente_pedida and not alerg_meta.get("disponivel", False):
        motivo = (
            "Não é possível garantir a exclusão de alergênicos porque o cardápio desta data não "
            "possui notações de alergênicos por preparação na fonte."
        )
        return ResultadoFerramenta(
            ferramenta="montar_prato",
            argumentos=args,
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo,
            dados={**args, "prato": [], "motivo_recusa": motivo},
            texto_base=geracao.RECUSA,
            alertas=[motivo],
        )

    trilhas_aceitas = {
        "vegano": ("vegano", "todas"),
        "ovolacto": ("ovolacto", "vegano", "todas"),
        "padrao": ("padrao", "todas"),
        None: ("padrao", "ovolacto", "vegano", "todas"),
    }[trilha_pedida]

    escolhas: list[dict[str, Any]] = []
    evidencia_linhas: list[str] = []
    for comp in card_ref.get("compartimentos", []):
        compatíveis: list[dict] = []
        for op in comp.get("opcoes", []):
            if op.get("trilha", "todas") not in trilhas_aceitas:
                continue
            alergs_op = set(op.get("alergenicos") or [])
            if evitar and (alergs_op & evitar):
                continue
            if trilha_pedida == "vegano" and comp["slot"] in ("bebida", "panificacao", "gordura"):
                # Em café da manhã/compartimentos mistos, filtra palavras claramente animais quando não há ícone
                nome_low = _norm(op.get("nome", ""))
                if any(p in nome_low for p in ("manteiga", "queijo", "ricota", "ovo", "frango", "carne")):
                    continue
                if "leite" in nome_low and "soja" not in nome_low and "vegetal" not in nome_low:
                    continue
            compatíveis.append(op)

        if not compatíveis:
            continue

        # Prioriza opção específica da trilha pedida quando existir
        if trilha_pedida:
            compatíveis.sort(key=lambda o: 0 if o.get("trilha") == trilha_pedida else 1)

        selecionadas = compatíveis[: comp.get("max", 1)]
        for op in selecionadas:
            just = _justificativa_opcao(op, comp["titulo"], trilha_pedida, evitar)
            escolhas.append({
                "slot": comp["slot"],
                "titulo": comp["titulo"],
                "opcao_id": op["id"],
                "nome": op["nome"],
                "trilha": op.get("trilha", "todas"),
                "alergenicos": list(op.get("alergenicos") or []),
                "justificativa": just,
                "fonte": dict(op.get("fonte") or card_ref.get("fonte") or {}),
            })
            evidencia_linhas.append(f"- {comp['titulo']}: {op['nome']}")

    if not escolhas:
        motivo = "Nenhuma opção do cardápio atende às restrições informadas."
        return ResultadoFerramenta(
            ferramenta="montar_prato",
            argumentos=args,
            dono="Agente RU",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo,
            dados={**args, "prato": []},
            texto_base=geracao.RECUSA,
            alertas=[motivo],
        )

    dt = date.fromisoformat(data_iso)
    nome_ref = cardapio.REFEICOES.get(ref_norm, ref_norm)
    dia_nome = _DIAS_SEMANA[dt.weekday()]
    fonte = dict(res_card.fontes[0])
    trecho = {
        **fonte,
        "texto": f"Cardápio do RU Gama — {nome_ref} de {dia_nome}, {dt:%d/%m/%Y}:\n" + "\n".join(evidencia_linhas),
        "similaridade": 1.0,
    }
    cab = f"Prato montado para {nome_ref} de {dia_nome} ({dt:%d/%m/%Y})" + (
        f" · restrições: {', '.join(lista_restr)}" if lista_restr else ""
    )
    linhas_resp = [cab + " [1]:"] + [f"- {e['justificativa']} [1]" for e in escolhas]
    return ResultadoFerramenta(
        ferramenta="montar_prato",
        argumentos=args,
        dono="Agente RU",
        sucesso=True,
        recusado=False,
        dados={
            "data": data_iso,
            "refeicao": ref_norm,
            "restricoes": lista_restr,
            "prato": escolhas,
            "mesa_apoio": list(card_ref.get("mesa_apoio") or []),
        },
        fontes=[fonte],
        trechos_evidencia=[trecho],
        texto_base="\n".join(linhas_resp),
    )


def grafo_fluxo(consulta: str) -> ResultadoFerramenta:
    """Consulta determinística ao grafo curricular de pré-requisitos (`F16`)."""
    args = {"consulta": consulta}
    res = carregar_grafo_f16().consultar_estruturado(consulta)
    if res is None:
        motivo = "Consulta fora das operações suportadas pelo grafo curricular do F16."
        return ResultadoFerramenta(
            ferramenta="grafo_fluxo",
            argumentos=args,
            dono="Agente Fluxo",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo,
            dados={},
            texto_base=geracao.RECUSA,
            alertas=[motivo],
        )

    fonte = {"n": 1, **res["fonte"]}
    trecho = {**fonte, "texto": res["evidencia"], "similaridade": 1.0}
    return ResultadoFerramenta(
        ferramenta="grafo_fluxo",
        argumentos=args,
        dono="Agente Fluxo",
        sucesso=True,
        recusado=False,
        dados={"tipo_consulta": res["tipo_consulta"], **res["dados"]},
        fontes=[fonte],
        trechos_evidencia=[trecho],
        texto_base=res["texto"],
        alertas=list(res.get("alertas") or []),
    )


def _normalizar_dia_semana(dia: str | None, hoje: date | None = None) -> str:
    ref = hoje or date.today()
    if not dia:
        return _DIAS_SEMANA[ref.weekday()]
    bruto = _norm(dia)
    if bruto == "hoje":
        return _DIAS_SEMANA[ref.weekday()]
    if bruto == "amanha":
        return _DIAS_SEMANA[(ref + timedelta(days=1)).weekday()]
    return _DIAS_CURTOS.get(bruto, dia.strip().lower())


def minha_agenda(dia: str | None = None, perfil: dict[str, Any] | None = None) -> ResultadoFerramenta:
    """Retorna as aulas do dia com horário e sala a partir do perfil local do estudante."""
    dia_norm = _normalizar_dia_semana(dia)
    args = {"dia": dia_norm, "perfil_informado": bool(perfil and perfil.get("aulas"))}
    aulas_brutas = (perfil or {}).get("aulas") if isinstance(perfil, dict) else None
    if not isinstance(aulas_brutas, list) or not aulas_brutas:
        motivo = "Não há aulas cadastradas no perfil do estudante para consultar a agenda."
        return ResultadoFerramenta(
            ferramenta="minha_agenda",
            argumentos=args,
            dono="Agente Fluxo",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo,
            dados={"dia": dia_norm, "aulas": []},
            texto_base=geracao.RECUSA,
            alertas=[motivo],
        )

    dia_cmp = _norm(dia_norm)
    aulas_dia = [
        {
            "dia": str(a.get("dia") or dia_norm),
            "horario": str(a.get("horario") or "").strip(),
            "codigo": str(a.get("codigo") or "").strip(),
            "disciplina": str(a.get("disciplina") or a.get("nome") or "").strip(),
            "sala": str(a.get("sala") or "").strip(),
        }
        for a in aulas_brutas
        if isinstance(a, dict) and _norm(str(a.get("dia") or "")).startswith(dia_cmp.split("-")[0])
    ]
    aulas_dia.sort(key=lambda a: a["horario"])

    if not aulas_dia:
        motivo = f"Não há aulas cadastradas no perfil para {dia_norm}."
        return ResultadoFerramenta(
            ferramenta="minha_agenda",
            argumentos=args,
            dono="Agente Fluxo",
            sucesso=False,
            recusado=True,
            motivo_recusa=motivo,
            dados={"dia": dia_norm, "aulas": []},
            texto_base=geracao.RECUSA,
            alertas=[motivo],
        )

    fonte = {
        "n": 1,
        "doc_id": "PERFIL",
        "titulo": "Agenda informada no perfil local do estudante",
        "orgao": "Perfil local",
        "pagina": 1,
        "secao": dia_norm,
        "url": "",
        "chunk_id": f"PERFIL-{dia_cmp}",
    }
    linhas = [
        f"{a['horario']} · {a['disciplina']} ({a['codigo']}) — Sala {a['sala'] or 'não informada'}"
        if a["codigo"]
        else f"{a['horario']} · {a['disciplina']} — Sala {a['sala'] or 'não informada'}"
        for a in aulas_dia
    ]
    trecho = {**fonte, "texto": f"Agenda de {dia_norm}:\n" + "\n".join(f"- {l}" for l in linhas), "similaridade": 1.0}
    resp = f"Suas aulas em {dia_norm} [1]:\n" + "\n".join(f"- {l} [1]" for l in linhas)
    return ResultadoFerramenta(
        ferramenta="minha_agenda",
        argumentos=args,
        dono="Agente Fluxo",
        sucesso=True,
        recusado=False,
        dados={"dia": dia_norm, "aulas": aulas_dia},
        fontes=[fonte],
        trechos_evidencia=[trecho],
        texto_base=resp,
    )


def _extrair_data_arg(pergunta: str, contexto: dict[str, Any]) -> str | None:
    if contexto.get("data"):
        return str(contexto["data"])
    q = _norm(pergunta)
    if m := re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q):
        return m.group(1)
    if m := re.search(r"\b(\d{1,2}/\d{1,2}(?:/\d{4})?)\b", q):
        return m.group(1)
    if re.search(r"\bamanha\b", q):
        return "amanha"
    for chave in ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"):
        if re.search(rf"\b{chave}(?:-feira)?\b", q):
            return chave
    return None


def _extrair_refeicao_arg(pergunta: str) -> str:
    q = _norm(pergunta)
    if re.search(r"\b(?:cafe(?:\s+da\s+manha)?|desjejum)\b", q):
        return "cafe"
    if re.search(r"\b(?:jantar|janta)\b", q):
        return "jantar"
    return "almoco"


def _extrair_restricoes_arg(pergunta: str) -> list[str]:
    restricoes: list[str] = []
    q = _norm(pergunta)
    if re.search(r"\bvegan[oa]\b|\bvegetariano\s+estrito\b", q):
        restricoes.append("vegano")
    elif re.search(r"\bovolactovegetariano\b|\bvegetarian[oa]\b", q):
        restricoes.append("ovolacto")

    if m := re.search(r"(?:menos\s+de|at[eé]|abaixo\s+de|m[aá]ximo\s+de)?\s*\d+\s*(?:k?cal|calorias?)\b|\bcal[oó]ric\w*\b|\bcalorias?\b", pergunta, re.I):
        restricoes.append(m.group(0).strip())
    for pad, nome_alerg in _EXCLUSAO_ALERGENICOS:
        if pad.search(q):
            restricoes.append(f"sem {nome_alerg}")
    if _RESTRICAO_NAO_SUPORTADA.search(q) and not any(_RESTRICAO_NAO_SUPORTADA.search(_norm(r)) for r in restricoes):
        if m := _RESTRICAO_NAO_SUPORTADA.search(pergunta):
            restricoes.append(m.group(0).strip())
    return restricoes


def extrair_chamada_ru(pergunta: str, contexto: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]] | None:
    """Seleciona a ferramenta do Agente RU quando aplicável."""
    ctx = contexto or {}
    ferr_forcada = ctx.get("ferramenta")
    q = _norm(pergunta)

    if ferr_forcada == "montar_prato" or re.search(
        r"\b(?:mont[aeo]\w*|sugir\w*|escolh\w*|combin\w*)\s+(?:um\s+|o\s+|meu\s+)?(?:prato|bandeja|almoco|jantar|cafe)\b"
        r"|\bmontagem\s+de\s+prato\b"
        r"|\bprato\s+(?:vegan\w*|vegetarian\w*|ovolacto\w*|sem\s+\w+|com\s+menos\s+de)\b",
        q,
    ):
        return (
            "montar_prato",
            {
                "data": _extrair_data_arg(pergunta, ctx),
                "refeicao": _extrair_refeicao_arg(pergunta),
                "restricoes": _extrair_restricoes_arg(pergunta),
            },
        )

    if ferr_forcada == "cardapio_do_dia" or (
        re.search(r"\bcardapio\b", q) and re.search(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{4})?)\b", q)
    ):
        return (
            "cardapio_do_dia",
            {
                "data": _extrair_data_arg(pergunta, ctx),
                "refeicao": _extrair_refeicao_arg(pergunta) if re.search(r"\b(cafe|desjejum|almoco|jantar|janta)\b", q) else None,
            },
        )

    return None


def extrair_chamada_fluxo(pergunta: str, contexto: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]] | None:
    """Seleciona a ferramenta do Agente Fluxo quando aplicável."""
    ctx = contexto or {}
    q = _norm(pergunta)
    if ctx.get("ferramenta") == "minha_agenda" or re.search(
        r"\b(?:minha\s+agenda|minhas?\s+aulas?|agenda\s+de\s+aulas?|qual\s+(?:e\s+)?a\s+sala\s+d[ae])\b",
        q,
    ):
        dia_arg = "hoje"
        if re.search(r"\bamanha\b", q):
            dia_arg = "amanha"
        else:
            for chave in ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"):
                if re.search(rf"\b{chave}(?:-feira)?\b", q):
                    dia_arg = chave
                    break
        return ("minha_agenda", {"dia": dia_arg, "perfil": ctx.get("perfil")})

    if carregar_grafo_f16().consultar_estruturado(pergunta) is not None:
        return ("grafo_fluxo", {"consulta": pergunta})

    return None
