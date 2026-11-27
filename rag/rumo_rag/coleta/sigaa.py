"""Coleta nas páginas públicas do SIGAA/UnB (issues #52 e #56 · RF02 · épico E5).

Duas consultas abertas, sem login:

- **Consulta de turmas** (``/public/turmas/listar.jsf``): a oferta de um semestre por unidade,
  com código, turma, horário por extenso e local. É a fonte da oferta de turmas (#56).
- **Componentes curriculares** (``/public/componentes/busca_componentes.jsf``): a ficha de cada
  disciplina, com a expressão de pré-requisito, os correquisitos, as equivalências e o
  histórico de vigência das expressões. É a fonte textual dos pré-requisitos (#52).

O que fica de fora de propósito:

- nada que exija login (RNF06): só as páginas que qualquer visitante abre;
- nome de docente e número de vagas, que a página mostra mas o RUmo não usa.

O SIGAA é JSF: cada busca é um POST com o ``javax.faces.ViewState`` da página. O
balanceador só prende a sessão a um servidor a partir da **segunda** visita (é quando o
cookie ganha o prefixo ``appN~``); sem isso, o POST cai em outro servidor e a resposta é
"a página que se está tentando acessar não está mais ativa". Por isso :meth:`Sessao.formulario`
abre a página duas vezes antes de enviar.

Educação com o site: uma requisição por vez, pausa entre elas, User-Agent do projeto e
nenhuma nova tentativa automática.
"""
from __future__ import annotations

import html
import http.cookiejar
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .. import config

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

BASE = "https://sigaa.unb.br/sigaa/public"
URL_TURMAS = BASE + "/turmas/listar.jsf"
URL_COMPONENTES = BASE + "/componentes/busca_componentes.jsf"
UNIDADE_FCTE = "673"  # "CAMPUS UNB GAMA: FACULDADE DE CIÊNCIAS E TECNOLOGIAS EM ENGENHARIA"
ORGAO = "UnB · SIGAA (consulta pública)"
USER_AGENT = ("RUmo/1.0 (Residência em IA UnB/FCTE, Grupo 04; consulta pública do SIGAA; "
              "+https://github.com/maykonjuso/residencia-grupo-4)")
TIMEOUT = 60
PAUSA = 1.0
BRUTOS = config.DADOS / "brutos" / "sigaa"

_CODIGO = re.compile(r"\b([A-Z]{3,4}\d{4})\b")
_DIAS = {
    "segunda": "segunda", "terca": "terça", "quarta": "quarta",
    "quinta": "quinta", "sexta": "sexta", "sabado": "sábado", "domingo": "domingo",
}


class ErroSigaa(Exception):
    """Falha esperada da coleta no SIGAA. Mensagem para humanos."""


def _texto(fragmento: str) -> str:
    """HTML → texto de uma linha."""
    sem_tags = re.sub(r"<br\s*/?>", "\n", fragmento, flags=re.I)
    sem_tags = re.sub(r"<script\b.*?</script>", " ", sem_tags, flags=re.I | re.S)
    sem_tags = re.sub(r"<[^>]+>", " ", sem_tags)
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(sem_tags)).strip()


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


_MINUSCULAS = {"a", "à", "ao", "aos", "as", "às", "com", "da", "das", "de", "do", "dos", "e", "em",
               "na", "nas", "no", "nos", "o", "os", "para", "por"}
_ROMANOS = re.compile(r"^(i{1,3}|iv|v|vi{0,3}|ix|x)$")


def titulo(nome: str | None) -> str | None:
    """'TESTES DE SOFTWARE' → 'Testes de Software' (o SIGAA publica tudo em maiúsculas)."""
    if not nome:
        return None
    palavras = nome.lower().split()
    saida = []
    for i, p in enumerate(palavras):
        if _ROMANOS.match(p):
            saida.append(p.upper())
        elif i > 0 and p in _MINUSCULAS:
            saida.append(p)
        else:
            saida.append(p[:1].upper() + p[1:])
    return " ".join(saida)


# --------------------------------------------------------------------------- sessão HTTP

class Sessao:
    """Sessão com cookie, pausa entre requisições e detecção de sessão perdida."""

    def __init__(self, pausa: float = PAUSA):
        self.pausa = pausa
        self._ultimo = 0.0
        self._abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def pedir(self, url: str, campos: dict | None = None) -> str:
        espera = self.pausa - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        dados = urllib.parse.urlencode(campos).encode() if campos is not None else None
        req = urllib.request.Request(url, data=dados, headers={"User-Agent": USER_AGENT})
        try:
            with self._abridor.open(req, timeout=TIMEOUT) as r:
                corpo = r.read()
                final = r.geturl()
                charset = r.headers.get_content_charset() or "iso-8859-1"
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErroSigaa(f"Não consegui acessar {url}: {e}") from e
        finally:
            self._ultimo = time.monotonic()
        if campos is not None and "home.jsf" in final:
            raise ErroSigaa("O SIGAA descartou a sessão no meio da consulta (voltou para a página "
                            "inicial). Rode de novo; se repetir, o formulário mudou.")
        return corpo.decode(charset, errors="replace")

    def formulario(self, url: str, form_id: str) -> tuple[dict, str]:
        """Abre a página duas vezes (ver docstring do módulo) e devolve os campos ocultos do form."""
        self.pedir(url)
        pagina = self.pedir(url)
        return campos_ocultos(pagina, form_id), pagina


def campos_ocultos(pagina: str, form_id: str) -> dict:
    m = re.search(r'<form\b[^>]*\bid="%s".*?</form>' % re.escape(form_id), pagina, re.S)
    if not m:
        raise ErroSigaa(f"Formulário {form_id!r} não encontrado: o layout do SIGAA mudou.")
    campos = {}
    for tag in re.findall(r"<input\b[^>]*>", m.group(0)):
        tipo = re.search(r'type="([^"]*)"', tag)
        nome = re.search(r'name="([^"]*)"', tag)
        if nome and tipo and tipo.group(1) == "hidden":
            valor = re.search(r'value="([^"]*)"', tag)
            campos[nome.group(1)] = html.unescape(valor.group(1)) if valor else ""
    return campos


def _botao(pagina: str, form_id: str, rotulo: str) -> str:
    m = re.search(r'<form\b[^>]*\bid="%s".*?</form>' % re.escape(form_id), pagina, re.S)
    for tag in re.findall(r'<input\b[^>]*type="submit"[^>]*>', m.group(0) if m else ""):
        if f'value="{rotulo}"' in tag:
            return re.search(r'name="([^"]*)"', tag).group(1)
    raise ErroSigaa(f"Botão {rotulo!r} não encontrado: o layout do SIGAA mudou.")


def _campo_texto(pagina: str, rotulo: str) -> str:
    """Nome do input de texto que está na mesma linha do rótulo (os ids do JSF são gerados)."""
    m = re.search(re.escape(rotulo) + r".*?<input\b[^>]*type=\"text\"[^>]*name=\"([^\"]+)\"",
                  html.unescape(pagina), re.S)
    if not m:
        raise ErroSigaa(f"Campo {rotulo!r} não encontrado: o layout do SIGAA mudou.")
    return m.group(1)


# --------------------------------------------------------------------------- turmas (#56)

_PERIODO = re.compile(r"\((\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})\)")
_AULA = re.compile(r"([A-Za-zÀ-ÿ]+)-feira\s+(\d{2}:\d{2})\s+(?:às|as|a)\s+(\d{2}:\d{2})"
                   r"|(S[áa]bado|Domingo)\s+(\d{2}:\d{2})\s+(?:às|as|a)\s+(\d{2}:\d{2})", re.I)


def _dia(nome: str) -> str:
    return _DIAS.get(_sem_acento(nome), _sem_acento(nome))


def _salas(local: str) -> list[str]:
    """Salas citadas no campo Local, que é texto livre: 'FCTE - S2/I9', 'NIT/LDS(segunda)/I1(sexta)'.

    Tira o prefixo da unidade, as observações entre parênteses e o "Salas" antes de um código.
    O texto original continua em ``local``: quando uma sala vale só para um dia, é lá que isso está.
    """
    resto = re.sub(r"^\s*FCTE\s*[-/]\s*", "", local)
    vistas: list[str] = []
    for parte in resto.split("/"):
        sala = re.sub(r"\([^)]*\)", "", parte)
        sala = re.sub(r"^\s*Salas?\s+(?=[A-Z]\d+\b)", "", sala, flags=re.I)
        sala = re.sub(r"\s+", " ", sala).strip(" -")
        if sala and sala.upper() not in {"FCTE", "UNB"} and sala.upper() not in {v.upper() for v in vistas}:
            vistas.append(sala)
    return vistas


def ler_turmas(pagina: str) -> list[dict]:
    """Lê a tabela da consulta pública de turmas. Não guarda docente nem vagas."""
    tabela = re.search(r'<table\b[^>]*class="listagem".*?</table>', pagina, re.S)
    if not tabela:
        return []
    turmas: list[dict] = []
    codigo = nome = id_componente = None
    for classe, corpo in re.findall(r'<tr\b[^>]*class="\s*(agrupador|linhaPar|linhaImpar)\s*"[^>]*>(.*?)</tr>',
                                    tabela.group(0), re.S):
        if classe == "agrupador":
            cab = re.search(r'class="tituloDisciplina">\s*(.*?)\s*</span>', corpo, re.S)
            ident = re.search(r"'id':'(\d+)'", corpo)
            codigo, _, nome = _texto(cab.group(1)).partition(" - ") if cab else (None, "", None)
            id_componente = ident.group(1) if ident else None
            continue
        celulas = re.findall(r"<td\b[^>]*>(.*?)</td>", corpo, re.S)
        if len(celulas) < 5 or codigo is None:
            continue
        horario_html = celulas[3]
        popup = re.search(r'class="popUp".*?>(.*?)</div>', horario_html, re.S)
        sigla = _texto(re.split(r"<img\b|<span\b", horario_html, maxsplit=1)[0])
        periodo = _PERIODO.search(sigla)
        sigla = _PERIODO.sub("", sigla).strip()
        aulas = []
        for m in _AULA.finditer(_texto(popup.group(1)) if popup else ""):
            dia, ini, fim = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5), m.group(6))
            aulas.append({"dia": _dia(dia), "inicio": ini, "fim": fim})
        local = _texto(celulas[-1])
        turmas.append({
            "codigo": codigo,
            "nome": titulo(nome.strip()) if nome else None,
            "id_componente": id_componente,
            "turma": _texto(celulas[0]),
            "ano_periodo": _texto(celulas[1]),
            "horario_sigaa": sigla or None,
            "aulas": aulas,
            "periodo_letivo": ({"inicio": f"{periodo[3]}-{periodo[2]}-{periodo[1]}",
                                "fim": f"{periodo[6]}-{periodo[5]}-{periodo[4]}"} if periodo else None),
            "local": local or None,
            "salas": _salas(local) if local else [],
        })
    return turmas


def coletar_turmas(ano: int, periodo: int, unidade: str = UNIDADE_FCTE,
                   sessao: Sessao | None = None) -> tuple[list[dict], str]:
    """Busca a oferta de graduação da unidade no semestre. Devolve (turmas, HTML bruto)."""
    s = sessao or Sessao()
    campos, pagina = s.formulario(URL_TURMAS, "formTurma")
    campos.update({
        "formTurma:inputNivel": "G",
        "formTurma:inputDepto": unidade,
        "formTurma:inputAno": str(ano),
        "formTurma:inputPeriodo": str(periodo),
        _botao(pagina, "formTurma", "Buscar"): "Buscar",
    })
    resposta = s.pedir(URL_TURMAS, campos)
    turmas = ler_turmas(resposta)
    if not turmas:
        raise ErroSigaa(f"O SIGAA não devolveu turmas para {ano}.{periodo} na unidade {unidade}.")
    return turmas, resposta


# --------------------------------------------------------------------------- componentes (#52)

def _campo_ficha(pagina: str, rotulo: str) -> str | None:
    m = re.search(r"<th[^>]*>\s*%s\s*</th>\s*<td[^>]*>(.*?)</td>" % re.escape(rotulo), pagina, re.S | re.I)
    if not m:
        return None
    valor = _texto(m.group(1))
    return None if valor in ("", "-") else valor


def _secao_codigos(pagina: str, titulo: str) -> list[str]:
    """Códigos listados numa seção da ficha ("Outros componentes que têm esse componente como ...")."""
    m = re.search(re.escape(titulo) + r"(.*?)</table>", pagina, re.S | re.I)
    return list(dict.fromkeys(_CODIGO.findall(_texto(m.group(1))))) if m else []


def _historico(pagina: str) -> list[dict]:
    m = re.search(r"Hist[óo]rico de Pr[ée]-Requisitos(.*?)</table>", pagina, re.S | re.I)
    linhas = []
    for corpo in re.findall(r"<tr\b[^>]*>(.*?)</tr>", m.group(1) if m else "", re.S):
        cel = [_texto(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", corpo, re.S)]
        if len(cel) >= 3 and _CODIGO.search(cel[0]):
            linhas.append({"expressao": cel[0], "status": cel[1],
                           "inicio": cel[2] or None, "fim": (cel[3] if len(cel) > 3 else "") or None})
    return linhas


def _curriculos(pagina: str) -> list[dict]:
    m = re.search(r"<caption[^>]*>\s*Curr[íi]culos\s*</caption>(.*?)</table>|>\s*Curr[íi]culos\s*<(.*?)</table>",
                  pagina, re.S | re.I)
    trecho = (m.group(1) or m.group(2)) if m else ""
    saida = []
    for corpo in re.findall(r"<tr\b[^>]*>(.*?)</tr>", trecho, re.S):
        cel = [_texto(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", corpo, re.S)]
        if len(cel) >= 6:
            saida.append({"curriculo": cel[0], "implantacao": cel[1], "matriz": cel[2],
                          "obrigatoria": cel[3] == "Sim", "periodo": cel[4] or None, "ativo": cel[5] == "Sim"})
    return saida


def ler_componente(pagina: str) -> dict:
    """Lê a ficha pública de um componente curricular."""
    pagina = html.unescape(pagina)
    codigo = _campo_ficha(pagina, "Código:")
    if not codigo:
        raise ErroSigaa("A ficha do componente não tem código: o layout do SIGAA mudou.")
    pre = _campo_ficha(pagina, "Pré-Requisitos:")
    co = _campo_ficha(pagina, "Co-Requisitos:")
    eq = _campo_ficha(pagina, "Equivalências:")
    return {
        "codigo": codigo,
        "nome": titulo(_campo_ficha(pagina, "Nome:")),
        "pre_requisitos": {"expressao": pre, "cnf": cnf(pre)},
        "co_requisitos": {"expressao": co, "cnf": cnf(co)},
        "equivalencias": {"expressao": eq, "cnf": cnf(eq)},
        "equivalente_de": _secao_codigos(pagina, "Outros componentes que têm esse componente como equivalente"),
        "pre_requisito_de": _secao_codigos(pagina, "Outros componentes que têm esse componente como pré-requisito"),
        "historico_pre_requisitos": _historico(pagina),
        # Disciplina comum (Cálculo, Física) aparece em centenas de currículos da UnB; só os da
        # FCTE interessam ao RUmo, e a lista inteira inchava o relatório para mais de 300 KB.
        "curriculos": [c for c in _curriculos(pagina) if "FCTE" in c["matriz"]],
    }


def coletar_componente(codigo: str, sessao: Sessao) -> tuple[dict, str]:
    """Busca o componente pelo código e abre a ficha. Devolve (ficha, HTML bruto)."""
    campos, pagina = sessao.formulario(URL_COMPONENTES, "form")
    campos.update({
        "form:nivel": "G",
        "form:tipo": "0",       # o navegador manda todo <select>, mesmo sem filtro marcado
        "form:unidades": "0",
        "form:checkCodigo": "on",
        _campo_texto(pagina, "Código do Componente:"): codigo,
        _botao(pagina, "form", "Buscar Componentes"): "Buscar Componentes",
    })
    lista = sessao.pedir(URL_COMPONENTES, campos)
    link = re.search(r"title=\"Detalhes do Componente Curricular\"[^>]*onclick=\"[^\"]*?\{'([^']+)':'[^']+','id':'(\d+)'",
                     lista)
    if not link or f">{codigo}<" not in lista.replace(" ", ""):
        raise ErroSigaa(f"O SIGAA não encontrou o componente {codigo}.")
    campos_lista = campos_ocultos(lista, "formListagemComponentes")
    campos_lista.update({link.group(1): link.group(1), "id": link.group(2), "publico": "public"})
    ficha = sessao.pedir(URL_COMPONENTES, campos_lista)
    return ler_componente(ficha), ficha


# --------------------------------------------------------------------------- expressões

_TOKEN = re.compile(r"\(|\)|\bE\b|\bOU\b|[A-Z]{3,4}\d{4}")


@dataclass
class _Leitor:
    tokens: list[str]
    pos: int = 0
    vistos: list[str] = field(default_factory=list)

    def olhar(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def tomar(self) -> str:
        t = self.tokens[self.pos]
        self.pos += 1
        return t


def _ou(leitor: _Leitor) -> list[frozenset]:
    clausulas = _e(leitor)
    while leitor.olhar() == "OU":
        leitor.tomar()
        direita = _e(leitor)
        clausulas = [a | b for a in clausulas for b in direita]
    return clausulas


def _e(leitor: _Leitor) -> list[frozenset]:
    clausulas = _fator(leitor)
    while leitor.olhar() == "E":
        leitor.tomar()
        clausulas = clausulas + _fator(leitor)
    return clausulas


def _fator(leitor: _Leitor) -> list[frozenset]:
    t = leitor.olhar()
    if t == "(":
        leitor.tomar()
        dentro = _ou(leitor)
        if leitor.olhar() != ")":
            raise ValueError("parêntese sem fechamento")
        leitor.tomar()
        return dentro
    if t and _CODIGO.fullmatch(t):
        return [frozenset([leitor.tomar()])]
    raise ValueError(f"token inesperado: {t!r}")


def _simplificar(clausulas: list[frozenset]) -> list[frozenset]:
    unicas = list(dict.fromkeys(clausulas))
    return [c for c in unicas if not any(o < c for o in unicas)]


def cnf(expressao: str | None) -> list[list[str]]:
    """Expressão do SIGAA → E de grupos OU (forma normal conjuntiva), códigos ordenados.

    ``( FGA0138 OU FGA0313 )`` → ``[["FGA0138", "FGA0313"]]``: um grupo, basta um dos dois.
    ``( A E B ) OU C`` → ``[["A", "C"], ["B", "C"]]``.
    """
    if not expressao:
        return []
    tokens = _TOKEN.findall(expressao.upper())
    if not tokens:
        return []
    leitor = _Leitor(tokens)
    clausulas = _ou(leitor)
    if leitor.olhar() is not None:
        raise ValueError(f"sobrou {leitor.olhar()!r} na expressão {expressao!r}")
    return sorted(sorted(c) for c in _simplificar(clausulas))


# --------------------------------------------------------------------------- comparação com o grafo

def mapa_codigos(curriculo: dict, componentes: list[dict] = ()) -> dict[str, str]:
    """Código antigo → código vigente, pelas equivalências do grafo e das fichas do SIGAA.

    A expressão do SIGAA às vezes ainda cita o código antigo: FGA0314 pede ``FGA0138 OU
    FGA0313``, e FGA0138 é o código antigo de MDS (hoje FGA0312). Sem esse mapa, toda
    disciplina renumerada apareceria como divergência.
    """
    no_curriculo = {n["codigo"] for n in curriculo["nos"]}
    mapa = {}
    for e in curriculo.get("equivalencias", []):
        for antigo in e.get("equivalentes", []):
            mapa[antigo] = e["codigo"]
    for comp in componentes:
        if comp["codigo"] not in no_curriculo:
            continue
        outros = [c for cl in comp["equivalencias"]["cnf"] for c in cl] + comp.get("equivalente_de", [])
        for antigo in outros:
            if antigo not in no_curriculo:
                mapa.setdefault(antigo, comp["codigo"])
    return mapa


def _normalizar(clausulas: list[list[str]], mapa: dict[str, str]) -> list[list[str]]:
    conj = [frozenset(mapa.get(c, c) for c in cl) for cl in clausulas]
    return sorted(sorted(c) for c in _simplificar(conj))


def clausulas_do_grafo(curriculo: dict, destino: str, relacao: str) -> list[list[str]]:
    out = []
    for a in curriculo.get("arestas", []):
        if a["destino"] == destino and a["relacao"] == relacao:
            out.append(frozenset([a["origem"], *a.get("alternativas", [])]))
    return sorted(sorted(c) for c in _simplificar(out))


def comparar(curriculo: dict, componentes: list[dict]) -> list[dict]:
    """Compara, disciplina a disciplina, os requisitos do SIGAA com os do grafo (gabarito F16)."""
    mapa = mapa_codigos(curriculo, componentes)
    por_codigo = {c["codigo"]: c for c in componentes}
    no_curriculo = {n["codigo"] for n in curriculo["nos"]}
    linhas = []
    for no in curriculo["nos"]:
        cod = no["codigo"]
        comp = por_codigo.get(cod)
        for relacao, chave in (("pre_requisito", "pre_requisitos"), ("correquisito", "co_requisitos")):
            grafo = clausulas_do_grafo(curriculo, cod, relacao)
            if comp is None:
                linhas.append({"codigo": cod, "relacao": relacao, "situacao": "sem_ficha",
                               "grafo": grafo, "sigaa": None, "fora_do_curriculo": []})
                continue
            sigaa = _normalizar(comp[chave]["cnf"], mapa)
            fora = sorted({c for cl in sigaa for c in cl} - no_curriculo)
            linhas.append({
                "codigo": cod,
                "relacao": relacao,
                "situacao": "igual" if sigaa == grafo else "diverge",
                "grafo": grafo,
                "sigaa": sigaa,
                "expressao_sigaa": comp[chave]["expressao"],
                "fora_do_curriculo": fora,
            })
    return linhas


# --------------------------------------------------------------------------- gravação

TURMAS = config.DADOS / "turmas"
SCHEMA_TURMAS = Path(__file__).with_name("schema_turmas.json")
_ORDEM_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def montar_oferta(turmas: list[dict], ano: int, periodo: int, coletado_em: str,
                  unidade: str = UNIDADE_FCTE) -> dict:
    return {
        "versao_schema": "1.0",
        "fonte": {
            "orgao": ORGAO,
            "url": URL_TURMAS,
            "consulta": {"nivel": "graduação", "unidade": unidade, "ano": ano, "periodo": periodo},
            "coletado_em": coletado_em,
            "observacao": ("Local e horário como o SIGAA publica na data da coleta; podem mudar "
                           "durante o semestre. Docente e vagas não são guardados."),
        },
        "ano_periodo": f"{ano}.{periodo}",
        "turmas": turmas,
    }


def validar_oferta(oferta: dict) -> None:
    import json

    import jsonschema

    jsonschema.validate(oferta, json.loads(SCHEMA_TURMAS.read_text(encoding="utf-8")))


def _dias_texto(aulas: list[dict]) -> str:
    """Agrupa dias com o mesmo horário: 'terça e quinta, das 08:00 às 09:50'."""
    por_horario: dict[tuple[str, str], list[str]] = {}
    for a in sorted(aulas, key=lambda a: (_ORDEM_DIAS.index(a["dia"]) if a["dia"] in _ORDEM_DIAS else 9)):
        por_horario.setdefault((a["inicio"], a["fim"]), []).append(a["dia"])
    partes = []
    for (ini, fim), dias in por_horario.items():
        nomes = dias[0] if len(dias) == 1 else ", ".join(dias[:-1]) + " e " + dias[-1]
        partes.append(f"{nomes}, das {ini} às {fim}")
    return "; ".join(partes)


def gerar_markdown(oferta: dict) -> str:
    """Texto curado da oferta, para a base do RAG: uma seção por disciplina.

    O texto é seco de propósito. Na primeira versão, cada linha repetia "FCTE" (do campo
    Local) e o título dizia "Oferta de turmas da FCTE"; no BM25, os 133 trechos passaram a
    ganhar de F14 na pergunta "Quantas vagas a FCTE oferta para Engenharia de Software?" (Q24).
    Por isso o título fala em horários e salas, e a linha traz a sala, não o Local inteiro.

    Cada disciplina é um parágrafo completo (código, nome, turmas) sob uma seção única: o
    chunking junta parágrafos vizinhos até o tamanho-alvo. Com uma seção por disciplina, os
    trechos ficavam com ~280 caracteres, baixavam o tamanho médio do BM25 e mudavam a ordem
    de perguntas sem relação com turmas (Q10).
    """
    f = oferta["fonte"]
    ap = oferta["ano_periodo"]
    periodos = {(t["periodo_letivo"]["inicio"], t["periodo_letivo"]["fim"])
                for t in oferta["turmas"] if t.get("periodo_letivo")}
    linhas = [
        f"# Horários e salas das turmas do campus Gama — semestre {ap}",
        "",
        (f"Fonte: consulta pública de turmas do SIGAA da UnB ({f['url']}), unidade "
         f"\"Faculdade de Ciências e Tecnologias em Engenharia\" (FCTE, campus Gama), nível graduação, "
         f"semestre {ap}. Coletado em {f['coletado_em']}. O horário e o local são os que o SIGAA "
         "publicava na data da coleta e podem mudar durante o semestre; confira no SIGAA antes da aula."),
    ]
    if len(periodos) == 1:
        ini, fim = periodos.pop()
        linhas.append(f"Período letivo das turmas: {ini[8:]}/{ini[5:7]}/{ini[:4]} a {fim[8:]}/{fim[5:7]}/{fim[:4]}.")
    linhas.append("")
    por_disc: dict[str, list[dict]] = {}
    for t in oferta["turmas"]:
        por_disc.setdefault(t["codigo"], []).append(t)
    linhas += [f"## Horários e salas por disciplina em {ap}", ""]
    for cod in sorted(por_disc):
        ts = sorted(por_disc[cod], key=lambda t: t["turma"])
        partes = []
        for t in ts:
            quando = _dias_texto(t["aulas"]) if t["aulas"] else (
                f"horário {t['horario_sigaa']}" if t["horario_sigaa"] else "horário a definir")
            if t["salas"]:
                onde = ("sala " if len(t["salas"]) == 1 else "salas ") + ", ".join(t["salas"])
            else:
                onde = t["local"] or "sala a definir"
            partes.append(f"turma {t['turma']}: {quando}, {onde}")
        siglas = ", ".join(t["horario_sigaa"] or "-" for t in ts)
        linhas += [f"{cod} {ts[0]['nome']} — horário das aulas e sala em {ap}: " + "; ".join(partes)
                   + f". (Horário no SIGAA: {siglas}.)", ""]
    return "\n".join(linhas)


def entrada_catalogo_oferta(catalogo_texto: str, ap: str, arquivo: str, coletado_em: str) -> tuple[str, str | None]:
    """(id, bloco YAML) da oferta no catálogo; bloco None se o arquivo já está catalogado."""
    m = re.search(r'^\s*-\s*id:\s*(F\d+)\s*\n(?:(?!^\s*-\s*id:).*\n)*?\s*arquivo:\s*"?' + re.escape(arquivo) + r'"?\s*$',
                  catalogo_texto, re.M)
    if m:
        return m.group(1), None
    numeros = [int(n) for n in re.findall(r"^\s*-\s*id:\s*F(\d+)", catalogo_texto, re.M)]
    novo = f"F{max(numeros, default=0) + 1:02d}"
    bloco = (f"  - id: {novo}\n"
             f'    titulo: "Horários e salas das turmas do campus Gama — {ap} (SIGAA, consulta pública)"\n'
             f'    orgao: "{ORGAO}"\n'
             f"    eixo: fluxo\n"
             f"    tipo: pagina\n"
             f'    data: "{coletado_em}"\n'
             f'    url: "{URL_TURMAS}"\n'
             f"    arquivo: {arquivo}\n"
             f'    coletado_em: "{coletado_em}"  # python -m rumo_rag.coleta turmas (#56)\n')
    return novo, bloco


def gravar_oferta(oferta: dict, bruto: str | None) -> dict:
    """Grava o JSON, o texto curado e, se for semestre novo, a entrada no catálogo."""
    from datetime import datetime
    import json

    from .scraper import gravar_atomico

    validar_oferta(oferta)
    ap = oferta["ano_periodo"].replace(".", "-")
    gravados = []
    if bruto is not None:
        destino = BRUTOS / f"turmas-{ap}-{datetime.now():%Y-%m-%dT%H%M%S}.html"
        gravar_atomico(destino, bruto)
        gravados.append(destino)
    json_destino = TURMAS / f"fcte_{ap}.json"
    gravar_atomico(json_destino, json.dumps(oferta, ensure_ascii=False, indent=2) + "\n")
    arquivo = f"curados/oferta_turmas_fcte_{ap}.md"
    md_destino = config.DADOS / arquivo
    gravar_atomico(md_destino, gerar_markdown(oferta))
    gravados += [json_destino, md_destino]
    catalogo = config.CATALOGO.read_text(encoding="utf-8")
    doc_id, bloco = entrada_catalogo_oferta(catalogo, oferta["ano_periodo"], arquivo, oferta["fonte"]["coletado_em"])
    if bloco:
        gravar_atomico(config.CATALOGO, catalogo + ("" if catalogo.endswith("\n") else "\n") + bloco)
        gravados.append(config.CATALOGO)
    # Política (#53): só a oferta do semestre corrente fica no índice. Semestres antigos
    # competiriam na busca com horários que não valem mais.
    antigos = sorted(set(re.findall(r"arquivo:\s*(curados/oferta_turmas_fcte_[\d-]+\.md)", catalogo)) - {arquivo})
    avisos = [f"o catálogo ainda tem a oferta de outro semestre ({a}); retire a entrada no mesmo PR"
              for a in antigos]
    return {"doc_id": doc_id, "novo": bloco is not None, "arquivos": gravados, "avisos": avisos}


def montar_relatorio_componentes(curriculo: dict, componentes: list[dict], coletado_em: str,
                                 faltando: list[dict]) -> dict:
    linhas = comparar(curriculo, componentes)
    return {
        "fonte": {"orgao": ORGAO, "url": URL_COMPONENTES, "coletado_em": coletado_em},
        "curriculo_id": curriculo["curriculo_id"],
        "gabarito": curriculo["fonte"],
        "resumo": {
            "disciplinas": len(curriculo["nos"]),
            "fichas": len(componentes),
            "iguais": sum(1 for l in linhas if l["situacao"] == "igual"),
            "divergentes": sum(1 for l in linhas if l["situacao"] == "diverge"),
            "sem_ficha": sum(1 for l in linhas if l["situacao"] == "sem_ficha"),
        },
        "comparacao": linhas,
        "falhas_de_coleta": faltando,
        "componentes": componentes,
    }
