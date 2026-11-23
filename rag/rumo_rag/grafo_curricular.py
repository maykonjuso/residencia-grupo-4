"""Grafo curricular determinístico em `networkx.DiGraph` persistido em JSON (#61).

As arestas sólidas (`incerta=False`) representam pré-requisitos explícitos em `self.grafo` (DAG).
Relações tracejadas (`incerta=True`) permanecem em `self.grafo_completo` e nunca entram em
cálculos de bloqueio confirmado, sendo sinalizadas ao estudante para confirmação no SIGAA.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

import networkx as nx

from . import config

CODIGO = re.compile(r"\b[A-Z]{2,4}\d{3,4}\b")
SCHEMA_GRAFO = Path(__file__).with_name("schema_grafo.json")
GRAFO_JSON = config.DADOS / "grafo_curricular.json"
FONTE_PADRAO_F16 = {
    "doc_id": "F16",
    "titulo": "Fluxograma de Engenharia de Software (235 créditos) — transcrição",
    "orgao": "UnB · FCTE · Engenharia de Software (transcrição do Grupo 04)",
    "pagina": 1,
    "url": "https://software.unb.br/matriz-curricular/",
}

_CABECALHO_SEMESTRE = re.compile(r"^##\s+(\d+)[º°]\s+semestre.*\((\d+)\s+créditos\)", re.I)
_DISCIPLINA = re.compile(
    r"^-\s+(?P<codigo>[A-Z]{2,4}\d{3,4})\s+(?P<nome>.+?)\s+—\s+"
    r"\d+-\d+-\d+-(?P<creditos>\d+)(?:\s+\(.*\))?$"
)
_PRE_REQUISITO = re.compile(
    r"^-\s+Para cursar (?P<destino>.+?)\s+\((?P<codigo_destino>[A-Z]{2,4}\d{3,4})\),"
    r"\s+é preciso ter cursado antes:\s+(?P<origens>.+)\.$",
    re.I,
)
_REFERENCIA = re.compile(
    r"(?P<nome>[^;()]+?)\s+\((?P<codigo>[A-Z]{2,4}\d{3,4})\)"
    r"(?:\s+\((?P<marca>seta cheia|seta tracejada)\))?",
    re.I,
)
_CORREQUISITO = re.compile(
    r"^-\s+(?P<nome_a>.+?)\s+\((?P<codigo_a>[A-Z]{2,4}\d{3,4})\)"
    r"\s+é correquisito de\s+(?P<nome_b>.+?)\s+\((?P<codigo_b>[A-Z]{2,4}\d{3,4})\):",
    re.I,
)


def _normalizar(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in sem_acentos if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class Disciplina:
    codigo: str
    nome: str
    creditos: int
    semestre: int
    evidencia: str


@dataclass(frozen=True)
class Aresta:
    origem: str
    destino: str
    relacao: str
    incerta: bool
    evidencia: str


@dataclass(frozen=True)
class ConsultaGrafo:
    conteudo: str
    evidencia: str
    alertas: tuple[str, ...] = ()


class GrafoCurricular:
    """Consultas em `networkx.DiGraph` ao grafo curricular de `F16_fluxograma_software.md`."""

    def __init__(
        self,
        disciplinas: dict[str, Disciplina],
        arestas: list[Aresta],
        metadados: dict | None = None,
    ):
        self.disciplinas = dict(disciplinas)
        self.arestas = tuple(arestas)
        self.metadados = metadados or {
            "curso": "Engenharia de Software",
            "versao_curriculo": "após 2024/2",
            "total_creditos": 235,
            "fonte": dict(FONTE_PADRAO_F16),
        }

        self.grafo = nx.DiGraph()
        self.grafo_completo = nx.DiGraph()
        for codigo, disc in self.disciplinas.items():
            attrs = asdict(disc)
            self.grafo.add_node(codigo, **attrs)
            self.grafo_completo.add_node(codigo, **attrs)

        for aresta in self.arestas:
            if aresta.relacao != "pre_requisito":
                continue
            attrs = {"relacao": aresta.relacao, "incerta": aresta.incerta, "evidencia": aresta.evidencia}
            self.grafo_completo.add_edge(aresta.origem, aresta.destino, **attrs)
            if not aresta.incerta:
                self.grafo.add_edge(aresta.origem, aresta.destino, **attrs)

        if not nx.is_directed_acyclic_graph(self.grafo):
            raise ValueError("Grafo de pré-requisitos contém ciclo.")

    @classmethod
    def de_markdown(cls, texto: str) -> "GrafoCurricular":
        disciplinas: dict[str, Disciplina] = {}
        arestas: list[Aresta] = []
        semestre_atual: int | None = None

        for linha in texto.splitlines():
            cabecalho = _CABECALHO_SEMESTRE.match(linha)
            if cabecalho:
                semestre_atual = int(cabecalho.group(1))
                continue

            disciplina = _DISCIPLINA.match(linha)
            if disciplina and semestre_atual is not None:
                codigo = disciplina.group("codigo").upper()
                disciplinas[codigo] = Disciplina(
                    codigo=codigo,
                    nome=disciplina.group("nome").strip(),
                    creditos=int(disciplina.group("creditos")),
                    semestre=semestre_atual,
                    evidencia=linha.removeprefix("- ").strip(),
                )
                continue

            prereq = _PRE_REQUISITO.match(linha)
            if prereq:
                destino = prereq.group("codigo_destino").upper()
                for segmento in prereq.group("origens").split(";"):
                    incerta = "seta tracejada" in _normalizar(segmento)
                    for referencia in _REFERENCIA.finditer(segmento):
                        marca = (referencia.group("marca") or "").casefold()
                        codigo_origem = referencia.group("codigo").upper()
                        arestas.append(
                            Aresta(
                                origem=codigo_origem,
                                destino=destino,
                                relacao="pre_requisito",
                                incerta=incerta or marca == "seta tracejada",
                                evidencia=linha.removeprefix("- ").strip(),
                            )
                        )
                continue

            coreq = _CORREQUISITO.match(linha)
            if coreq:
                arestas.append(
                    Aresta(
                        origem=coreq.group("codigo_a").upper(),
                        destino=coreq.group("codigo_b").upper(),
                        relacao="correquisito",
                        incerta=False,
                        evidencia=linha.removeprefix("- ").strip(),
                    )
                )

        if not disciplinas:
            raise ValueError("A transcrição F16 não contém disciplinas reconhecíveis.")
        desconhecidos = sorted(
            {c for a in arestas for c in (a.origem, a.destino) if c not in disciplinas}
        )
        if desconhecidos:
            raise ValueError(
                "Arestas F16 apontam para códigos que não aparecem na lista de disciplinas: "
                + ", ".join(desconhecidos)
            )
        return cls(disciplinas, arestas)

    def para_dict(self) -> dict:
        nos = [
            asdict(self.disciplinas[c])
            for c in sorted(self.disciplinas, key=lambda x: (self.disciplinas[x].semestre, x))
        ]
        arestas = [asdict(a) for a in self.arestas]
        return {
            "curso": self.metadados["curso"],
            "versao_curriculo": self.metadados["versao_curriculo"],
            "total_creditos": self.metadados["total_creditos"],
            "fonte": dict(self.metadados["fonte"]),
            "nos": nos,
            "arestas": arestas,
        }

    @staticmethod
    def validar_json(dados: dict) -> None:
        import jsonschema

        schema = json.loads(SCHEMA_GRAFO.read_text(encoding="utf-8"))
        jsonschema.validate(dados, schema)

    @classmethod
    def de_dict(cls, dados: dict) -> "GrafoCurricular":
        cls.validar_json(dados)
        disciplinas = {n["codigo"]: Disciplina(**n) for n in dados["nos"]}
        arestas = [Aresta(**a) for a in dados["arestas"]]
        metadados = {
            "curso": dados["curso"],
            "versao_curriculo": dados["versao_curriculo"],
            "total_creditos": dados["total_creditos"],
            "fonte": dict(dados["fonte"]),
        }
        return cls(disciplinas, arestas, metadados=metadados)

    def salvar_json(self, destino: Path = GRAFO_JSON) -> Path:
        dados = self.para_dict()
        self.validar_json(dados)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destino

    @classmethod
    def carregar_json(cls, caminho: Path = GRAFO_JSON) -> "GrafoCurricular":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls.de_dict(dados)

    @classmethod
    def carregar_f16(cls, caminho: Path | None = None) -> "GrafoCurricular":
        if caminho is None and GRAFO_JSON.exists():
            return cls.carregar_json(GRAFO_JSON)
        fonte = caminho or (config.DADOS / "curados" / "F16_fluxograma_software.md")
        return cls.de_markdown(fonte.read_text(encoding="utf-8"))

    def buscar_disciplinas(self, consulta: str) -> list[Disciplina]:
        consulta_norm = _normalizar(consulta)
        codigos = [c.upper() for c in CODIGO.findall(consulta)]
        encontradas: dict[str, Disciplina] = {
            codigo: self.disciplinas[codigo]
            for codigo in codigos
            if codigo in self.disciplinas
        }
        nomes = sorted(self.disciplinas.values(), key=lambda d: len(d.nome), reverse=True)
        for disciplina in nomes:
            nome = _normalizar(disciplina.nome)
            if nome and nome in consulta_norm:
                encontradas[disciplina.codigo] = disciplina
        return sorted(encontradas.values(), key=lambda d: (d.semestre, d.codigo))

    def _to_aresta(self, origem: str, destino: str, attrs: dict) -> Aresta:
        return Aresta(
            origem=origem,
            destino=destino,
            relacao=attrs.get("relacao", "pre_requisito"),
            incerta=bool(attrs.get("incerta", False)),
            evidencia=attrs.get("evidencia", ""),
        )

    def prerequisitos(self, codigo: str) -> tuple[list[Aresta], list[Aresta]]:
        codigo = codigo.upper()
        if codigo not in self.grafo_completo:
            return [], []
        confirmados: list[Aresta] = []
        incertos: list[Aresta] = []
        for origem, destino, attrs in self.grafo_completo.in_edges(codigo, data=True):
            aresta = self._to_aresta(origem, destino, attrs)
            (incertos if aresta.incerta else confirmados).append(aresta)
        return confirmados, incertos

    def _evidencia(self, codigos: set[str], arestas: list[Aresta] | tuple[Aresta, ...]) -> str:
        linhas = [self.disciplinas[c].evidencia for c in sorted(codigos) if c in self.disciplinas]
        linhas.extend(a.evidencia for a in arestas if a.evidencia)
        return "\n".join(dict.fromkeys(linhas)) or "Consulta calculada pelas relações registradas no F16."

    def dependentes(self, codigo: str) -> tuple[list[str], list[str]]:
        """Retorna dependentes alcançáveis por arestas sólidas e por caminhos incertos."""
        codigo = codigo.upper()
        if codigo not in self.grafo:
            return [], []
        confirmados = nx.descendants(self.grafo, codigo)
        todos = nx.descendants(self.grafo_completo, codigo)
        incertos = todos - confirmados
        ordenar = lambda codigos: sorted(  # noqa: E731
            codigos, key=lambda c: (self.disciplinas[c].semestre, c)
        )
        return ordenar(confirmados), ordenar(incertos)

    def gargalos(self) -> list[tuple[Disciplina, int]]:
        saidas = dict(self.grafo.out_degree())
        maior = max(saidas.values(), default=0)
        if maior == 0:
            return []
        return sorted(
            [(self.disciplinas[c], n) for c, n in saidas.items() if n == maior],
            key=lambda item: (item[0].semestre, item[0].codigo),
        )

    def disciplinas_que_abrem(self, aprovadas: set[str]) -> tuple[list[str], list[str]]:
        aprovadas = {c.upper() for c in aprovadas}
        abertas: list[str] = []
        incertas: list[str] = []
        for codigo in self.grafo:
            confirmados = list(self.grafo.predecessors(codigo))
            if not confirmados or codigo in aprovadas:
                continue
            if all(orig in aprovadas for orig in confirmados):
                _, duvidosos = self.prerequisitos(codigo)
                (incertas if duvidosos else abertas).append(codigo)
        return (
            sorted(abertas, key=lambda c: (self.disciplinas[c].semestre, c)),
            sorted(incertas, key=lambda c: (self.disciplinas[c].semestre, c)),
        )

    def caminho_critico(self) -> list[str]:
        """Maior cadeia de pré-requisitos confirmados via `nx.dag_longest_path`."""
        if not self.grafo.number_of_nodes():
            return []
        return list(nx.dag_longest_path(self.grafo))

    def _fonte_dict(self) -> dict:
        fonte = dict(self.metadados.get("fonte") or FONTE_PADRAO_F16)
        fonte.setdefault("secao", "Grafo de pré-requisitos")
        fonte.setdefault("chunk_id", "F16-grafo-curricular")
        return fonte

    def _no_resumo(self, codigo: str) -> dict:
        d = self.disciplinas[codigo]
        return {"codigo": d.codigo, "nome": d.nome, "semestre": d.semestre, "creditos": d.creditos}

    def consultar_estruturado(self, pergunta: str) -> dict | None:
        """Executa consulta no grafo e devolve payload estruturado + texto + evidência."""
        texto = _normalizar(pergunta)
        disciplinas = self.buscar_disciplinas(pergunta)
        codigos = {d.codigo for d in disciplinas}
        fonte = self._fonte_dict()

        if re.search(r"caminho critico|quantos semestres.*formar|tempo.*formar", texto):
            caminho = self.caminho_critico()
            if not caminho:
                return None
            nomes = " → ".join(f"{self.disciplinas[c].nome} ({c})" for c in caminho)
            arestas_caminho = [
                self._to_aresta(u, v, attrs)
                for u, v, attrs in self.grafo.edges(data=True)
                if u in caminho and v in caminho
            ]
            evidencia = self._evidencia(set(caminho), arestas_caminho)
            resposta = (
                f"A maior cadeia de pré-requisitos confirmados na transcrição é: {nomes}. [1] "
                "Isso representa a cadeia mais longa registrada no grafo, não uma previsão "
                "de semestres até a formatura; oferta de turmas e requisitos fora da transcrição "
                "devem ser confirmados no SIGAA. Esta transcrição vale para ingressantes após "
                "2024/2. [1]"
            )
            return {
                "tipo_consulta": "caminho_critico",
                "dados": {
                    "comprimento": len(caminho),
                    "cadeia": [self._no_resumo(c) for c in caminho],
                },
                "texto": resposta,
                "evidencia": evidencia,
                "fonte": fonte,
                "alertas": [],
            }

        if re.search(r"gargalo|destrava.*mais|mais (?:materias|disciplinas)|maior numero", texto):
            ranking = self.gargalos()
            if not ranking:
                return None
            quantidade = ranking[0][1]
            todas_arestas: list[Aresta] = []
            itens_gargalo: list[dict] = []
            partes_texto: list[str] = []
            for disciplina, _ in ranking:
                arestas = [
                    self._to_aresta(u, v, attrs)
                    for u, v, attrs in self.grafo.out_edges(disciplina.codigo, data=True)
                ]
                todas_arestas.extend(arestas)
                destinos_nomes = ", ".join(
                    f"{self.disciplinas[a.destino].nome} ({a.destino})" for a in arestas
                )
                itens_gargalo.append({
                    **self._no_resumo(disciplina.codigo),
                    "grau_saida": quantidade,
                    "destinos": [self._no_resumo(a.destino) for a in arestas],
                })
                partes_texto.append(f"{disciplina.nome} ({disciplina.codigo}) → {destinos_nomes}")

            cods_ev = {it["codigo"] for it in itens_gargalo} | {a.destino for a in todas_arestas}
            evidencia = self._evidencia(cods_ev, todas_arestas)
            if len(ranking) == 1:
                d0 = ranking[0][0]
                dest0 = ", ".join(
                    f"{self.disciplinas[a.destino].nome} ({a.destino})"
                    for a in self._to_aresta_out(d0.codigo)
                )
                resposta = (
                    f"Pelo número de dependências diretas confirmadas no F16, {d0.nome} "
                    f"({d0.codigo}) é o principal gargalo: destrava {quantidade} disciplina(s) "
                    f"diretamente ({dest0}). [1] A contagem considera apenas setas cheias; "
                    "ligações tracejadas não entram no ranking. Esta transcrição vale para "
                    "ingressantes após 2024/2. [1]"
                )
            else:
                resumo = "; ".join(partes_texto)
                resposta = (
                    f"Pelo número de dependências diretas confirmadas no F16, há empate no topo "
                    f"com {quantidade} disciplina(s) destravada(s) diretamente cada: {resumo}. [1] "
                    "A contagem considera apenas setas cheias; ligações tracejadas não entram no "
                    "ranking. Esta transcrição vale para ingressantes após 2024/2. [1]"
                )
            return {
                "tipo_consulta": "gargalo",
                "dados": {"grau_saida_max": quantidade, "gargalos": itens_gargalo},
                "texto": resposta,
                "evidencia": evidencia,
                "fonte": fonte,
                "alertas": [],
            }

        if re.search(r"passando|passei|aprovad[oa]s?|o que abre|quais.*abre", texto):
            if not codigos:
                return None
            abertas, incertas = self.disciplinas_que_abrem(codigos)
            aprovadas_txt = ", ".join(sorted(codigos))
            arestas_usadas = [
                a for a in self.arestas
                if a.destino in abertas + incertas and a.origem in codigos
                and a.relacao == "pre_requisito"
            ]
            evidencia = self._evidencia(codigos | set(abertas) | set(incertas), arestas_usadas)
            if abertas:
                nomes = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in abertas)
                resposta = f"Com aprovação em {aprovadas_txt}, ficam liberadas pelo grafo: {nomes}. [1]"
            else:
                resposta = (
                    f"Com aprovação em {aprovadas_txt}, não identifiquei novas disciplinas "
                    "liberadas apenas por pré-requisitos confirmados no F16. [1]"
                )
            if incertas:
                nomes_inc = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in incertas)
                resposta += (
                    f" Há também possível relação com {nomes_inc}, mas a ligação é tracejada; "
                    "confirme no SIGAA se é pré-requisito ou correquisito. [1]"
                )
                arestas_tracejadas = [
                    a for a in self.arestas
                    if a.destino in incertas and a.incerta and a.relacao == "pre_requisito"
                ]
                evidencia = self._evidencia(
                    codigos | set(abertas) | set(incertas), arestas_usadas + arestas_tracejadas
                )
            resposta += " Esta transcrição vale para ingressantes após 2024/2. [1]"
            return {
                "tipo_consulta": "disciplinas_que_abrem",
                "dados": {
                    "aprovadas": sorted(codigos),
                    "abertas_confirmadas": [self._no_resumo(c) for c in abertas],
                    "relacoes_incertas": [self._no_resumo(c) for c in incertas],
                },
                "texto": resposta,
                "evidencia": evidencia,
                "fonte": fonte,
                "alertas": [],
            }

        if re.search(r"reprov|trava|bloque|dependente|depende de", texto) and disciplinas:
            inicio = disciplinas[0]
            confirmados, incertos = self.dependentes(inicio.codigo)
            nos_envolvidos = {inicio.codigo, *confirmados, *incertos}
            arestas_usadas_obj = [
                self._to_aresta(u, v, attrs)
                for u, v, attrs in self.grafo_completo.edges(data=True)
                if u in nos_envolvidos and v in nos_envolvidos
            ]
            if confirmados:
                nomes = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in confirmados)
                resposta = (
                    f"Se você reprovar em {inicio.nome} ({inicio.codigo}), as disciplinas "
                    f"alcançáveis por uma cadeia de pré-requisitos confirmados são: {nomes}. [1]"
                )
            else:
                resposta = (
                    f"Não encontrei dependentes alcançáveis por setas cheias a partir de "
                    f"{inicio.nome} ({inicio.codigo}) na transcrição F16. [1]"
                )
            if incertos:
                nomes_inc = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in incertos)
                resposta += (
                    f" A cadeia também pode alcançar {nomes_inc} por ligação tracejada; "
                    "não é possível afirmar que bloqueia. Confirme no SIGAA. [1]"
                )
            resposta += " Esta transcrição vale para ingressantes após 2024/2. [1]"
            evidencia = self._evidencia(nos_envolvidos, arestas_usadas_obj)
            return {
                "tipo_consulta": "dependentes",
                "dados": {
                    "origem": self._no_resumo(inicio.codigo),
                    "dependentes_confirmados": [self._no_resumo(c) for c in confirmados],
                    "dependentes_incertos": [self._no_resumo(c) for c in incertos],
                },
                "texto": resposta,
                "evidencia": evidencia,
                "fonte": fonte,
                "alertas": [],
            }

        if re.search(r"pre-?requisito", texto) and disciplinas:
            alvo = disciplinas[-1]
            confirmados, incertos = self.prerequisitos(alvo.codigo)
            partes: list[str] = []
            if confirmados:
                nomes = ", ".join(
                    f"{self.disciplinas[a.origem].nome} ({a.origem})" for a in confirmados
                )
                partes.append(f"Pré-requisitos confirmados de {alvo.nome} ({alvo.codigo}): {nomes}.")
            else:
                partes.append(
                    f"A transcrição F16 não registra seta cheia de pré-requisito para "
                    f"{alvo.nome} ({alvo.codigo})."
                )
            if incertos:
                nomes_inc = ", ".join(
                    f"{self.disciplinas[a.origem].nome} ({a.origem})" for a in incertos
                )
                partes.append(
                    f"O fluxograma também mostra ligação tracejada com {nomes_inc}; confirme no SIGAA "
                    "se é pré-requisito ou correquisito."
                )
            partes.append("A transcrição vale para ingressantes após 2024/2.")
            evidencia = self._evidencia(
                {alvo.codigo, *(a.origem for a in confirmados + incertos)},
                confirmados + incertos,
            )
            return {
                "tipo_consulta": "prerequisitos",
                "dados": {
                    "disciplina": self._no_resumo(alvo.codigo),
                    "confirmados": [self._no_resumo(a.origem) for a in confirmados],
                    "incertos": [self._no_resumo(a.origem) for a in incertos],
                },
                "texto": " ".join(p + " [1]" for p in partes),
                "evidencia": evidencia,
                "fonte": fonte,
                "alertas": [],
            }

        return None

    def _to_aresta_out(self, codigo: str) -> list[Aresta]:
        return [
            self._to_aresta(u, v, attrs)
            for u, v, attrs in self.grafo.out_edges(codigo, data=True)
        ]

    def consultar(self, pergunta: str) -> ConsultaGrafo | None:
        """Executa deterministicamente uma consulta reconhecida; None pede fallback RAG."""
        res = self.consultar_estruturado(pergunta)
        if res is None:
            return None
        return ConsultaGrafo(res["texto"], res["evidencia"], tuple(res["alertas"]))


@lru_cache(maxsize=1)
def carregar_grafo_f16() -> GrafoCurricular:
    """Carrega uma única vez por processo o grafo curricular (JSON persistido ou F16)."""
    return GrafoCurricular.carregar_f16()
