"""Grafo curricular determinístico extraído da transcrição curada F16.

As arestas sólidas representam pré-requisitos explícitos. Relações tracejadas
continuam marcadas como incertas e não entram em cálculos de bloqueio confirmado.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from . import config

CODIGO = re.compile(r"\b[A-Z]{2,4}\d{3,4}\b")
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
    """Consultas ao grafo de disciplinas descrito em `F16_fluxograma_software.md`."""

    def __init__(self, disciplinas: dict[str, Disciplina], arestas: list[Aresta]):
        self.disciplinas = disciplinas
        self.arestas = tuple(arestas)

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
                # A transcrição expressa a primeira relação entre parênteses,
                # mas a ligação tracejada de Testes aparece como prosa após `;`.
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
                # O texto descreve uma relação simultânea; a orientação é apenas
                # de armazenamento e nunca é usada para inferir bloqueios.
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

    @classmethod
    def carregar_f16(cls, caminho: Path | None = None) -> "GrafoCurricular":
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

    def prerequisitos(self, codigo: str) -> tuple[list[Aresta], list[Aresta]]:
        codigo = codigo.upper()
        confirmados = [
            a for a in self.arestas
            if a.destino == codigo and a.relacao == "pre_requisito" and not a.incerta
        ]
        incertos = [
            a for a in self.arestas
            if a.destino == codigo and a.relacao == "pre_requisito" and a.incerta
        ]
        return confirmados, incertos

    def _evidencia(self, codigos: set[str], arestas: list[Aresta] | tuple[Aresta, ...]) -> str:
        linhas = [self.disciplinas[c].evidencia for c in sorted(codigos) if c in self.disciplinas]
        linhas.extend(a.evidencia for a in arestas)
        return "\n".join(dict.fromkeys(linhas)) or "Consulta calculada pelas relações registradas no F16."

    def dependentes(self, codigo: str) -> tuple[list[str], list[str]]:
        """Retorna dependentes alcançáveis por arestas sólidas e por caminhos incertos."""
        codigo = codigo.upper()
        fila = deque([(codigo, False)])
        visitados = {(codigo, False)}
        estado: dict[str, bool] = {}
        while fila:
            atual, caminho_incerto = fila.popleft()
            for aresta in self.arestas:
                if aresta.origem != atual or aresta.relacao != "pre_requisito":
                    continue
                incerto = caminho_incerto or aresta.incerta
                estado[aresta.destino] = estado.get(aresta.destino, True) and incerto
                par = (aresta.destino, incerto)
                if par not in visitados:
                    visitados.add(par)
                    fila.append(par)
        ordenar = lambda codigos: sorted(  # noqa: E731 - ordenação local simples
            codigos, key=lambda c: (self.disciplinas[c].semestre, c)
        )
        return ordenar([c for c, incerto in estado.items() if not incerto]), ordenar(
            [c for c, incerto in estado.items() if incerto]
        )

    def gargalos(self) -> list[tuple[Disciplina, int]]:
        saidas = {codigo: 0 for codigo in self.disciplinas}
        for aresta in self.arestas:
            if aresta.relacao == "pre_requisito" and not aresta.incerta:
                saidas[aresta.origem] += 1
        maior = max(saidas.values(), default=0)
        if maior == 0:
            return []
        return sorted(
            [(self.disciplinas[c], n) for c, n in saidas.items() if n == maior],
            key=lambda item: item[0].codigo,
        )

    def disciplinas_que_abrem(self, aprovadas: set[str]) -> tuple[list[str], list[str]]:
        aprovadas = {c.upper() for c in aprovadas}
        abertas: list[str] = []
        incertas: list[str] = []
        for codigo in self.disciplinas:
            confirmados, duvidosos = self.prerequisitos(codigo)
            if not confirmados or codigo in aprovadas:
                continue
            if all(a.origem in aprovadas for a in confirmados):
                (incertas if duvidosos else abertas).append(codigo)
        return (
            sorted(abertas, key=lambda c: (self.disciplinas[c].semestre, c)),
            sorted(incertas, key=lambda c: (self.disciplinas[c].semestre, c)),
        )

    def caminho_critico(self) -> list[str]:
        """Maior cadeia de pré-requisitos confirmados, em quantidade de disciplinas."""
        ordem = sorted(self.disciplinas, key=lambda c: (self.disciplinas[c].semestre, c))
        melhor: dict[str, list[str]] = {c: [c] for c in ordem}
        for codigo in ordem:
            for aresta in self.arestas:
                if (
                    aresta.origem == codigo
                    and aresta.relacao == "pre_requisito"
                    and not aresta.incerta
                    and len(melhor[aresta.origem]) + 1 > len(melhor[aresta.destino])
                ):
                    melhor[aresta.destino] = melhor[aresta.origem] + [aresta.destino]
        return max(melhor.values(), key=len, default=[])

    def consultar(self, pergunta: str) -> ConsultaGrafo | None:
        """Executa deterministicamente uma consulta reconhecida; None pede fallback RAG."""
        texto = _normalizar(pergunta)
        disciplinas = self.buscar_disciplinas(pergunta)
        codigos = {d.codigo for d in disciplinas}

        if re.search(r"caminho critico|quantos semestres.*formar|tempo.*formar", texto):
            caminho = self.caminho_critico()
            if not caminho:
                return None
            nomes = " → ".join(
                f"{self.disciplinas[c].nome} ({c})" for c in caminho
            )
            arestas_caminho = [
                a for a in self.arestas
                if a.origem in caminho and a.destino in caminho
                and a.relacao == "pre_requisito" and not a.incerta
            ]
            evidencia = self._evidencia(set(caminho), arestas_caminho)
            resposta = (
                f"A maior cadeia de pré-requisitos confirmados na transcrição é: {nomes}. [1] "
                "Isso representa a cadeia mais longa registrada no grafo, não uma previsão "
                "de semestres até a formatura; oferta de turmas e requisitos fora da transcrição "
                "devem ser confirmados no SIGAA. Esta transcrição vale para ingressantes após "
                "2024/2. [1]"
            )
            return ConsultaGrafo(resposta, evidencia)

        if re.search(r"gargalo|destrava.*mais|mais (?:mat[eé]rias|disciplinas)|maior n[uú]mero", texto):
            ranking = self.gargalos()
            if not ranking:
                return None
            disciplina, quantidade = ranking[0]
            arestas = [
                a for a in self.arestas
                if a.origem == disciplina.codigo
                and a.relacao == "pre_requisito" and not a.incerta
            ]
            destinos = ", ".join(
                f"{self.disciplinas[a.destino].nome} ({a.destino})" for a in arestas
            )
            evidencia = self._evidencia(
                {disciplina.codigo, *(a.destino for a in arestas)}, arestas
            )
            resposta = (
                f"Pelo número de dependências diretas confirmadas no F16, {disciplina.nome} "
                f"({disciplina.codigo}) é o principal gargalo: destrava {quantidade} disciplina(s) "
                f"diretamente ({destinos}). [1] A contagem considera apenas setas cheias; "
                "ligações tracejadas não entram no ranking. Esta transcrição vale para "
                "ingressantes após 2024/2. [1]"
            )
            return ConsultaGrafo(resposta, evidencia)

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
                resposta = f"Com aprovação em {aprovadas_txt}, não identifiquei novas disciplinas liberadas apenas por pré-requisitos confirmados no F16. [1]"
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
            return ConsultaGrafo(resposta, evidencia or "Consulta calculada pelas relações registradas no F16.")

        if re.search(r"reprov|trava|bloque|dependente|depende de", texto) and disciplinas:
            inicio = disciplinas[0]
            confirmados, incertos = self.dependentes(inicio.codigo)
            arestas_usadas = [
                a.evidencia for a in self.arestas
                if a.relacao == "pre_requisito" and (
                    (a.origem in {inicio.codigo, *confirmados, *incertos})
                    and (a.destino in {*confirmados, *incertos})
                )
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
            arestas_usadas_obj = [
                a for a in self.arestas if a.evidencia in arestas_usadas
            ]
            evidencia = self._evidencia(
                {inicio.codigo, *confirmados, *incertos}, arestas_usadas_obj
            )
            return ConsultaGrafo(resposta, evidencia)

        if re.search(r"pr[eé]-?requisito", texto) and disciplinas:
            alvo = disciplinas[-1]
            confirmados, incertos = self.prerequisitos(alvo.codigo)
            partes: list[str] = []
            if confirmados:
                nomes = ", ".join(
                    f"{self.disciplinas[a.origem].nome} ({a.origem})" for a in confirmados
                )
                partes.append(f"Pré-requisitos confirmados de {alvo.nome} ({alvo.codigo}): {nomes}.")
            else:
                partes.append(f"A transcrição F16 não registra seta cheia de pré-requisito para {alvo.nome} ({alvo.codigo}).")
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
            return ConsultaGrafo(" ".join(p + " [1]" for p in partes), evidencia or "Consulta feita na transcrição F16.")

        return None


@lru_cache(maxsize=1)
def carregar_grafo_f16() -> GrafoCurricular:
    """Carrega uma única vez por processo a transcrição curada F16."""
    return GrafoCurricular.carregar_f16()
