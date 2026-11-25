"""Grafo curricular determinístico multi-curso em `networkx.DiGraph` (#61).

Cobre os 5 cursos de graduação da FCTE (Engenharia de Software, Aeroespacial,
Eletrônica, Automotiva e Energia) a partir das fontes oficiais na base, com suporte
a vigência do currículo (coexistência de matrizes antigas e novas) e equivalências.

Regras inegociáveis:
- Arestas sólidas (`incerta=False`) formam o DAG validado em `self.grafo`.
- Relações tracejadas (`incerta=True`) permanecem em `self.grafo_completo` e pedem confirmação no SIGAA.
- Cursos cuja fonte na base ainda não traz códigos SIGAA ou pré-requisitos (Automotiva/Energia)
  recebem `codigo_oficial=False` e `cobertura_prerequisitos="indisponivel_na_base"` — nada é inventado.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

import networkx as nx

from . import config
from .texto import normalizar_texto as _normalizar, slugify

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

FONTE_F17 = {
    "doc_id": "F17",
    "titulo": "Projeto Pedagógico do Curso de Engenharia Aeroespacial (PPC 2025)",
    "orgao": "UnB · FCTE · Engenharia Aeroespacial",
    "pagina": 74,
    "url": "https://aeroespacial.unb.br/wp-content/uploads/2026/05/PPC_Aero_2025.pdf",
}

FONTE_F21 = {
    "doc_id": "F21",
    "titulo": "Projeto Pedagógico do Curso de Engenharia Eletrônica (PPC 2023)",
    "orgao": "UnB · FCTE · Engenharia Eletrônica",
    "pagina": 60,
    "url": "https://eletronica.unb.br/wp-content/uploads/2025/03/PPC_eletronica2023_2.pdf",
}

FONTE_F19 = {
    "doc_id": "F19",
    "titulo": "Engenharia Automotiva — estrutura curricular (ingressantes a partir de 2027)",
    "orgao": "UnB · FCTE · Engenharia Automotiva",
    "pagina": 1,
    "url": "https://automotiva.unb.br/estrutura_curricular/",
}

FONTE_F23 = {
    "doc_id": "F23",
    "titulo": "Matriz curricular de Engenharia de Energia (251 créditos) — transcrição",
    "orgao": "UnB · FCTE (transcrição do Grupo 04)",
    "pagina": 1,
    "url": "https://fcte.unb.br/engenharia-de-energia/",
}

# Software (F16)
_CABECALHO_SEMESTRE = re.compile(r"^##\s+(\d+)[º°]\s+semestre.*\((\d+)\s+créditos\)", re.I)
_DISCIPLINA = re.compile(
    r"^-\s+(?P<codigo>[A-Z]{2,4}\d{3,4})\s+(?P<nome>.+?)\s+—\s+"
    r"\d+-\d+-\d+-(?P<creditos>\d+)(?:\s+\((?P<nota>.*)\))?$"
)
_ANTIGO_CODIGO = re.compile(r"\bantigo(?:\s+c[oó]digo)?\s+(?P<codigo>[A-Z]{2,4}\d{3,4})\b", re.I)
_PRE_REQUISITO = re.compile(
    r"^-\s+Para cursar (?P<destino>.+?)\s+\((?P<codigo_destino>[A-Z]{2,4}\d{3,4})\),"
    r"\s+é preciso ter cursado antes(?:\s+\([^)]+\))?:\s+(?P<origens>.+)\.$",
    re.I,
)
_REFERENCIA = re.compile(
    r"(?P<nome>[^;()]+?(?:\s+\([^()]+\))?)\s+\((?P<codigo>[A-Z]{2,4}\d{3,4})\)"
    r"(?:\s+\((?P<marca>seta cheia|seta tracejada)\))?",
    re.I,
)
_CORREQUISITO = re.compile(
    r"^-\s+(?P<nome_a>.+?)\s+\((?P<codigo_a>[A-Z]{2,4}\d{3,4})\)"
    r"\s+é correquisito de\s+(?P<nome_b>.+?)\s+\((?P<codigo_b>[A-Z]{2,4}\d{3,4})\):",
    re.I,
)

_STOPWORDS_SIGLA = frozenset({
    "a", "as", "o", "os", "de", "da", "das", "do", "dos", "e", "em", "na", "nas",
    "no", "nos", "para", "por", "com", "ao", "aos", "um", "uma",
})
_SIGLAS_BLOQUEADAS = frozenset({
    "de", "da", "do", "em", "no", "na", "se", "ou", "os", "as", "um", "ao",
    "eu", "me", "te", "ja", "so", "ha", "ir", "ru", "unb", "fga", "fcte",
    "ppc", "sigaa", "ira", "sim", "nao", "que", "com", "por", "sem", "mas",
    "mais", "tem", "ter", "ser", "ver", "vez", "dia", "mes", "ano", "ate",
    "qual", "quais", "como", "onde", "para", "pela", "pelo", "esta", "este",
    "essa", "esse", "isso", "tudo", "cada", "aqui", "hoje", "curso", "grade",
    "fluxo", "matriz", "nome", "nota", "data", "hora",
    "desenvolvimento", "teste", "testes", "projeto", "sistema", "sistemas",
    "engenharia", "computacao", "computadores", "software", "pratica", "teoria",
})
_SUFIXOS_CURTOS = (
    " aplicada a engenharia",
    " aplicado a engenharia",
    " de software",
    " para engenharia",
    " de engenharia",
    " de computadores",
)

# Aeroespacial (F17) e Eletrônica (F21)
_SEMESTRES_ORDINAIS = {
    "PRIMEIRO": 1,
    "SEGUNDO": 2,
    "TERCEIRO": 3,
    "QUARTO": 4,
    "QUINTO": 5,
    "SEXTO": 6,
    "SETIMO": 7,
    "OITAVO": 8,
    "NONO": 9,
    "DECIMO": 10,
}
_LINHA_TABELA_PPC = re.compile(
    r"^(?P<codigo>[A-Z]{2,4}\d{3,4})\s+"
    r"(?P<nome>.+?)\s+"
    r"(?P<tipo>DISCIPLINA|ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL TCC|ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL ESTÁGIO|ATIVIDADE)\s+"
    r"(?P<n1>\d+|-)\s+(?P<n2>\d+|-)\s+(?P<n3>\d+|-)\s+(?P<tot>\d+)\s+"
    r"(?P<prereq>.+?)\s*$"
)
_NIVEL_ELETRONICA = re.compile(r"^(\d+)[oº°]\.?\s+N[ií]vel\b", re.I)
_TABELA_24_EQUIV = re.compile(
    r"^(?P<codigo>[A-Z]{2,4}\d{3,4})\s+(?P<nome>.+?)\s+(?P<nivel>\d+[º°])\s+(?P<equiv>[A-Z]{2,4}\d{3,4}|-)\s*$"
)

# Energia (F23) e Automotiva (F19)
_SEMESTRE_ENERGIA = re.compile(r"^##\s+Ano\s+\d+\s+·\s+(\d+)[º°]\s+semestre", re.I)
_DISC_ENERGIA = re.compile(
    r"^-\s+(?P<nome>.+?)\s+—\s+(?P<a>\d+)·(?P<b>\d+)·(?P<c>\d+)\s*(?:\((?P<nucleo>[^)]+)\))?$"
)

# Nomes de cursos e apelidos aceitos em consultas
_PADROES_CURSO: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("software", re.compile(r"\beng(?:enharia)?\s+(?:de\s+)?software\b|\bsoftware\b|\besw\b", re.I)),
    ("aeroespacial", re.compile(r"\beng(?:enharia)?\s+aeroespacial\b|\baeroespacial\b|\baero\b", re.I)),
    ("eletronica", re.compile(r"\beng(?:enharia)?\s+eletronica\b|\beletronica\b", re.I)),
    ("automotiva", re.compile(r"\beng(?:enharia)?\s+automotiva\b|\bautomotiva\b", re.I)),
    ("energia", re.compile(r"\beng(?:enharia)?\s+(?:de\s+)?energia\b|\benergia\b", re.I)),
)


def _slug(texto: str) -> str:
    return slugify(texto, padrao="disciplina")


@dataclass(frozen=True)
class Disciplina:
    codigo: str
    nome: str
    creditos: int
    semestre: int
    evidencia: str
    carga_horaria: int | None = None
    codigo_oficial: bool = True


@dataclass(frozen=True)
class Aresta:
    origem: str
    destino: str
    relacao: str
    incerta: bool
    evidencia: str
    alternativas: tuple[str, ...] = ()


@dataclass(frozen=True)
class Equivalencia:
    codigo: str
    equivalentes: tuple[str, ...]
    tipo: str
    bidirecional: bool
    observacao: str
    evidencia: str


@dataclass(frozen=True)
class ConsultaGrafo:
    conteudo: str
    evidencia: str
    alertas: tuple[str, ...] = ()


def _metadados_padrao_f16() -> dict:
    return {
        "curriculo_id": "software-2024-2",
        "curso_slug": "software",
        "curso": "Engenharia de Software",
        "vigencia": {
            "inicio": "2024/2",
            "fim": None,
            "ativa": True,
            "descricao": "Ingressantes após 2024/2 (235 créditos)",
        },
        "versao_curriculo": "após 2024/2",
        "total_creditos": 235,
        "carga_horaria_total": 3525,
        "cobertura_prerequisitos": "completa",
        "cobertura_equivalencias": "parcial",
        "fonte": dict(FONTE_PADRAO_F16),
    }


def _normalizar_metadados(metadados: dict | None) -> dict:
    padrao = _metadados_padrao_f16()
    if not metadados:
        return padrao
    saida = {**padrao, **metadados}
    if "fonte" in metadados:
        saida["fonte"] = dict(metadados["fonte"])
    if "vigencia" in metadados and isinstance(metadados["vigencia"], dict):
        saida["vigencia"] = dict(metadados["vigencia"])
    elif "versao_curriculo" in metadados and "vigencia" not in metadados:
        saida["vigencia"] = {
            "inicio": str(metadados["versao_curriculo"]),
            "fim": None,
            "ativa": True,
            "descricao": str(metadados["versao_curriculo"]),
        }
    return saida


class GrafoCurricular:
    """Consultas em `networkx.DiGraph` a um currículo da FCTE (pré-requisitos, vigência e equivalências)."""

    def __init__(
        self,
        disciplinas: dict[str, Disciplina],
        arestas: list[Aresta] | tuple[Aresta, ...],
        metadados: dict | None = None,
        equivalencias: list[Equivalencia] | tuple[Equivalencia, ...] = (),
    ):
        self.disciplinas = dict(disciplinas)
        self.arestas = tuple(arestas)
        self.equivalencias = tuple(equivalencias)
        self.metadados = _normalizar_metadados(metadados)

        self.grafo = nx.DiGraph()
        self.grafo_completo = nx.DiGraph()
        for codigo, disc in self.disciplinas.items():
            attrs = asdict(disc)
            self.grafo.add_node(codigo, **attrs)
            self.grafo_completo.add_node(codigo, **attrs)

        for aresta in self.arestas:
            if aresta.relacao != "pre_requisito":
                continue
            attrs = {
                "relacao": aresta.relacao,
                "incerta": aresta.incerta,
                "alternativas": tuple(aresta.alternativas),
                "evidencia": aresta.evidencia,
            }
            self.grafo_completo.add_edge(aresta.origem, aresta.destino, **attrs)
            if not aresta.incerta:
                self.grafo.add_edge(aresta.origem, aresta.destino, **attrs)

        if not nx.is_directed_acyclic_graph(self.grafo):
            raise ValueError(
                f"Grafo de pré-requisitos ({self.curriculo_id}) contém ciclo."
            )

        self.grafo_equivalencias = nx.Graph()
        self._equiv_por_codigo: dict[str, list[Equivalencia]] = {}
        for eq in self.equivalencias:
            self._equiv_por_codigo.setdefault(eq.codigo, []).append(eq)
            for alt in eq.equivalentes:
                self.grafo_equivalencias.add_edge(
                    eq.codigo,
                    alt,
                    tipo=eq.tipo,
                    bidirecional=eq.bidirecional,
                    observacao=eq.observacao,
                    evidencia=eq.evidencia,
                )
                if eq.bidirecional:
                    self._equiv_por_codigo.setdefault(alt, []).append(eq)

        self._construir_indices_busca()

    @property
    def curriculo_id(self) -> str:
        return self.metadados["curriculo_id"]

    @property
    def curso(self) -> str:
        return self.metadados["curso"]

    @property
    def curso_slug(self) -> str:
        return self.metadados["curso_slug"]

    @property
    def vigencia(self) -> dict:
        return self.metadados["vigencia"]

    @property
    def cobertura_prerequisitos(self) -> str:
        return self.metadados["cobertura_prerequisitos"]

    @property
    def cobertura_equivalencias(self) -> str:
        return self.metadados["cobertura_equivalencias"]

    # ------------------------------------------------------------------ construtores por fonte oficial

    @classmethod
    def de_markdown(cls, texto: str) -> "GrafoCurricular":
        """Extrai Engenharia de Software a partir da transcrição curada `F16`."""
        disciplinas: dict[str, Disciplina] = {}
        arestas: list[Aresta] = []
        equivalencias: list[Equivalencia] = []
        semestre_atual: int | None = None

        for linha in texto.splitlines():
            cabecalho = _CABECALHO_SEMESTRE.match(linha)
            if cabecalho:
                semestre_atual = int(cabecalho.group(1))
                continue

            disciplina = _DISCIPLINA.match(linha)
            if disciplina and semestre_atual is not None:
                codigo = disciplina.group("codigo").upper()
                creditos = int(disciplina.group("creditos"))
                evid = linha.removeprefix("- ").strip()
                disciplinas[codigo] = Disciplina(
                    codigo=codigo,
                    nome=disciplina.group("nome").strip(),
                    creditos=creditos,
                    carga_horaria=creditos * 15,
                    semestre=semestre_atual,
                    codigo_oficial=True,
                    evidencia=evid,
                )
                nota = disciplina.group("nota") or ""
                antigo = _ANTIGO_CODIGO.search(nota)
                if antigo:
                    cod_antigo = antigo.group("codigo").upper()
                    equivalencias.append(
                        Equivalencia(
                            codigo=codigo,
                            equivalentes=(cod_antigo,),
                            tipo="codigo_antigo",
                            bidirecional=True,
                            observacao=f"Código atualizado após inclusão de extensão ({cod_antigo} → {codigo}).",
                            evidencia=evid,
                        )
                    )
                continue

            prereq = _PRE_REQUISITO.match(linha)
            if prereq:
                destino = prereq.group("codigo_destino").upper()
                eh_ou_linha = "alternativo ou" in _normalizar(linha)
                for segmento in prereq.group("origens").split(";"):
                    seg_norm = _normalizar(segmento)
                    incerta_seg = "seta tracejada" in seg_norm
                    refs = list(_REFERENCIA.finditer(segmento))
                    if len(refs) >= 2 and (eh_ou_linha or re.search(r"\bou\b", seg_norm)):
                        cod_prim = refs[0].group("codigo").upper()
                        cod_alts = tuple(r.group("codigo").upper() for r in refs[1:])
                        arestas.append(
                            Aresta(
                                origem=cod_prim,
                                destino=destino,
                                relacao="pre_requisito",
                                incerta=incerta_seg,
                                alternativas=cod_alts,
                                evidencia=linha.removeprefix("- ").strip(),
                            )
                        )
                    else:
                        for referencia in refs:
                            marca = _normalizar(referencia.group("marca") or "")
                            codigo_origem = referencia.group("codigo").upper()
                            arestas.append(
                                Aresta(
                                    origem=codigo_origem,
                                    destino=destino,
                                    relacao="pre_requisito",
                                    incerta=incerta_seg or marca == "seta tracejada",
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
        return cls(disciplinas, arestas, metadados=_metadados_padrao_f16(), equivalencias=equivalencias)

    @classmethod
    def de_ppc_aeroespacial(cls, texto: str) -> "GrafoCurricular":
        """Extrai Engenharia Aeroespacial (PPC 2025, Tabela 16 + substituições pp. 72-73 de `F17`)."""
        linhas = texto.splitlines()
        inicio = next(
            (i for i, ln in enumerate(linhas) if "Tabela 16" in ln and "Fluxograma" in ln),
            None,
        )
        if inicio is None:
            raise ValueError("Tabela 16 (Fluxograma de Engenharia Aeroespacial) não encontrada em F17.")
        fim = next(
            (i for i in range(inicio + 1, len(linhas)) if linhas[i].startswith("15.3.2")),
            len(linhas),
        )

        disciplinas: dict[str, Disciplina] = {}
        brutos_prereq: list[tuple[str, str, str]] = []
        semestre_atual: int | None = None

        for linha in linhas[inicio + 1 : fim]:
            limpa = linha.strip()
            if not limpa:
                continue
            limpa_norm = _normalizar(limpa).replace(" ", "")
            for chave, num in _SEMESTRES_ORDINAIS.items():
                if limpa_norm == f"{chave.casefold()}semestre":
                    semestre_atual = num
                    break

            m = _LINHA_TABELA_PPC.match(limpa)
            if m and semestre_atual is not None:
                codigo = m.group("codigo").upper()
                total_h = int(m.group("tot"))
                disciplinas[codigo] = Disciplina(
                    codigo=codigo,
                    nome=m.group("nome").strip().title() if m.group("nome").isupper() else m.group("nome").strip(),
                    creditos=total_h // 15,
                    carga_horaria=total_h,
                    semestre=semestre_atual,
                    codigo_oficial=True,
                    evidencia=limpa,
                )
                prereq_col = m.group("prereq").strip()
                if prereq_col != "-":
                    brutos_prereq.append((codigo, prereq_col, limpa))

        if not disciplinas:
            raise ValueError("Nenhuma disciplina extraída da Tabela 16 de Engenharia Aeroespacial (F17).")

        arestas: list[Aresta] = []
        for destino, prereq_col, evid in brutos_prereq:
            for orig in CODIGO.findall(prereq_col.upper()):
                if orig in disciplinas and orig != destino:
                    arestas.append(Aresta(orig, destino, "pre_requisito", False, evid))

        # Correquisitos entre teoria e prática documentados em F17 (p. 72)
        for a, b, desc in (
            ("FGA0086", "FGA0087", "Teoria e Laboratório de Eletricidade Aplicada (F17, p. 72)."),
            ("FGA0119", "FGA0120", "Teoria e Prática de Eletromagnetismo (F17, p. 72)."),
            ("FGA0078", "FGA0075", "Teoria e Laboratório de Materiais de Construção (F17, p. 72)."),
        ):
            if a in disciplinas and b in disciplinas:
                arestas.append(Aresta(b, a, "correquisito", False, desc))

        equivalencias = [
            Equivalencia(
                codigo="FGA0102",
                equivalentes=("FGA0187",),
                tipo="substituicao_ppc",
                bidirecional=True,
                observacao="Sinais e Sistemas (90h) substitui Métodos Matemáticos para Engenharia (60h) no PPC 2025.",
                evidencia="Sinais e Sistemas para Engenharia substitui a disciplina Métodos Matemáticos para Engenharia e amplia o seu escopo com o aumento de 30 horas (F17, p. 72).",
            ),
            Equivalencia(
                codigo="FGA0093",
                equivalentes=("FGA0197",),
                tipo="substituicao_ppc",
                bidirecional=True,
                observacao="Princípios de Controle (75h) substitui Sistemas de Controle (60h) no PPC 2025.",
                evidencia="Sistemas de Controle é substituída por Princípios de Controle com a inclusão de 15 horas de laboratório, e passa do sexto semestre para o quinto semestre (F17, p. 73).",
            ),
        ]

        metadados = {
            "curriculo_id": "aeroespacial-2025",
            "curso_slug": "aeroespacial",
            "curso": "Engenharia Aeroespacial",
            "vigencia": {
                "inicio": "2025/1",
                "fim": None,
                "ativa": True,
                "descricao": "Nova Matriz Curricular — PPC 2025 (3.900h)",
            },
            "versao_curriculo": "PPC 2025 (3.900h)",
            "total_creditos": 260,
            "carga_horaria_total": 3900,
            "cobertura_prerequisitos": "completa",
            "cobertura_equivalencias": "parcial",
            "fonte": dict(FONTE_F17),
        }
        return cls(disciplinas, arestas, metadados=metadados, equivalencias=equivalencias)

    @classmethod
    def de_ppc_eletronica(cls, texto: str) -> "GrafoCurricular":
        """Extrai Engenharia Eletrônica (PPC 2023, Tabelas 23 e 24 de `F21`)."""
        linhas = texto.splitlines()
        inicio = next(
            (i for i, ln in enumerate(linhas) if "Tabela 23" in ln and "Fluxograma" in ln),
            None,
        )
        if inicio is None:
            raise ValueError("Tabela 23 (Fluxograma de Engenharia Eletrônica) não encontrada em F21.")
        idx_t24 = next(
            (i for i in range(inicio + 1, len(linhas)) if "Tabela 24" in linhas[i]),
            None,
        )
        fim_t23 = idx_t24 if idx_t24 is not None else len(linhas)

        disciplinas: dict[str, Disciplina] = {}
        brutos_prereq: list[tuple[str, str, str]] = []
        semestre_atual: int | None = None

        for linha in linhas[inicio + 1 : fim_t23]:
            limpa = linha.strip()
            if not limpa:
                continue
            m_niv = _NIVEL_ELETRONICA.match(limpa)
            if m_niv:
                semestre_atual = int(m_niv.group(1))
                continue

            m = _LINHA_TABELA_PPC.match(limpa)
            if m and semestre_atual is not None:
                codigo = m.group("codigo").upper()
                total_h = int(m.group("tot"))
                disciplinas[codigo] = Disciplina(
                    codigo=codigo,
                    nome=m.group("nome").strip().title() if m.group("nome").isupper() else m.group("nome").strip(),
                    creditos=total_h // 15,
                    carga_horaria=total_h,
                    semestre=semestre_atual,
                    codigo_oficial=True,
                    evidencia=limpa,
                )
                prereq_col = m.group("prereq").strip()
                if prereq_col != "-":
                    brutos_prereq.append((codigo, prereq_col, limpa))

        if not disciplinas:
            raise ValueError("Nenhuma disciplina extraída da Tabela 23 de Engenharia Eletrônica (F21).")

        # Identifica requisitos diretos e pares mútuos (que são correquisitos na Tabela 23)
        pares_brutos: list[tuple[str, str, tuple[str, ...], str]] = []
        direcoes: set[tuple[str, str]] = set()
        equivalencias: list[Equivalencia] = []
        eq_vistas: set[tuple[str, tuple[str, ...], str]] = set()

        for destino, prereq_col, evid in brutos_prereq:
            clausulas = [c.strip() for c in re.split(r"\s+E\s+", prereq_col.upper()) if c.strip()]
            for cl in clausulas:
                cods = CODIGO.findall(cl)
                if not cods:
                    continue
                if "OU" in cl and len(cods) >= 2:
                    internos = [c for c in cods if c in disciplinas]
                    externos = tuple(c for c in cods if c not in disciplinas)
                    orig = internos[0] if internos else cods[0]
                    alts = tuple(c for c in cods if c != orig)
                    if orig in disciplinas and orig != destino:
                        pares_brutos.append((orig, destino, alts, evid))
                        direcoes.add((orig, destino))
                    if externos and orig in disciplinas:
                        chave = (orig, externos, "equivalencia_oficial")
                        if chave not in eq_vistas:
                            eq_vistas.add(chave)
                            equivalencias.append(
                                Equivalencia(
                                    codigo=orig,
                                    equivalentes=externos,
                                    tipo="equivalencia_oficial",
                                    bidirecional=True,
                                    observacao=f"Pré-requisito aceito em alternativa: {cl} (F21, Tabela 23).",
                                    evidencia=evid,
                                )
                            )
                else:
                    for orig in cods:
                        if orig in disciplinas and orig != destino:
                            pares_brutos.append((orig, destino, (), evid))
                            direcoes.add((orig, destino))

        arestas: list[Aresta] = []
        coreqs_vistos: set[tuple[str, str]] = set()
        for orig, destino, alts, evid in pares_brutos:
            if (destino, orig) in direcoes:
                par = tuple(sorted((orig, destino)))
                if par not in coreqs_vistos:
                    coreqs_vistos.add(par)
                    arestas.append(Aresta(par[0], par[1], "correquisito", False, evid))
            else:
                arestas.append(Aresta(orig, destino, "pre_requisito", False, evid, alternativas=alts))

        # Tabela 24: Novas Componentes Extensionistas e suas Equivalências
        if idx_t24 is not None:
            fim_t24 = next(
                (i for i in range(idx_t24 + 1, len(linhas)) if linhas[i].startswith("13.4")),
                len(linhas),
            )
            for linha in linhas[idx_t24 + 1 : fim_t24]:
                limpa = linha.strip()
                m_eq = _TABELA_24_EQUIV.match(limpa)
                if m_eq and m_eq.group("equiv") != "-":
                    cod_novo = m_eq.group("codigo").upper()
                    cod_eq = m_eq.group("equiv").upper()
                    chave = (cod_novo, (cod_eq,), "equivalencia_oficial")
                    if chave not in eq_vistas:
                        eq_vistas.add(chave)
                        equivalencias.append(
                            Equivalencia(
                                codigo=cod_novo,
                                equivalentes=(cod_eq,),
                                tipo="equivalencia_oficial",
                                bidirecional=True,
                                observacao=f"Tabela 24 (PPC 2023): componente extensionista {cod_novo} equivale a {cod_eq}.",
                                evidencia=limpa,
                            )
                        )

        metadados = {
            "curriculo_id": "eletronica-2023",
            "curso_slug": "eletronica",
            "curso": "Engenharia Eletrônica",
            "vigencia": {
                "inicio": "2023/1",
                "fim": None,
                "ativa": True,
                "descricao": "Matriz Curricular com Extensão — PPC 2023 (3.795h)",
            },
            "versao_curriculo": "PPC 2023 (3.795h)",
            "total_creditos": 253,
            "carga_horaria_total": 3795,
            "cobertura_prerequisitos": "completa",
            "cobertura_equivalencias": "parcial",
            "fonte": dict(FONTE_F21),
        }
        return cls(disciplinas, arestas, metadados=metadados, equivalencias=equivalencias)

    @classmethod
    def de_estruturas_automotiva(cls, texto: str) -> list["GrafoCurricular"]:
        """Extrai as duas vigências coexistentes de Engenharia Automotiva em `F19`."""
        specs = [
            (
                "# Para ingressantes a partir de 2027",
                "automotiva-2027",
                {
                    "inicio": "2027/1",
                    "fim": None,
                    "ativa": True,
                    "descricao": "Ingressantes a partir de 2027 (3.930h)",
                },
                "ingressantes a partir de 2027",
                262,
                3930,
            ),
            (
                "# Para ingressantes entre 2018 e 2026",
                "automotiva-2018-2026",
                {
                    "inicio": "2018/1",
                    "fim": "2026/2",
                    "ativa": True,
                    "descricao": "Ingressantes entre 2018 e 2026",
                },
                "ingressantes entre 2018 e 2026",
                None,
                None,
            ),
        ]
        linhas = texto.splitlines()
        grafos: list[GrafoCurricular] = []

        for idx_spec, (marcador, cid, vig, versao, tot_cred, tot_h) in enumerate(specs):
            start = next((i for i, ln in enumerate(linhas) if ln.strip() == marcador), None)
            if start is None:
                continue
            if idx_spec + 1 < len(specs):
                prox_m = specs[idx_spec + 1][0]
                end = next((i for i in range(start + 1, len(linhas)) if linhas[i].strip() == prox_m), len(linhas))
            else:
                end = len(linhas)

            disciplinas: dict[str, Disciplina] = {}
            semestre_atual: int | None = None
            for linha in linhas[start + 1 : end]:
                limpa = linha.strip()
                if limpa.startswith("Componentes Optativos"):
                    break
                m_sem = re.match(r"^##\s+(\d+)[º°]\s+N[ií]vel\s*$", limpa, re.I)
                if m_sem:
                    semestre_atual = int(m_sem.group(1))
                    continue
                if limpa.startswith("- ") and semestre_atual is not None:
                    nome_bruto = limpa[2:].strip()
                    if not nome_bruto:
                        continue
                    nome = nome_bruto.title() if nome_bruto.isupper() else nome_bruto
                    codigo = f"SEM-CODIGO:{_slug(nome)}"
                    if codigo in disciplinas:
                        codigo = f"{codigo}-n{semestre_atual}"
                    disciplinas[codigo] = Disciplina(
                        codigo=codigo,
                        nome=nome,
                        creditos=0,
                        carga_horaria=None,
                        semestre=semestre_atual,
                        codigo_oficial=False,
                        evidencia=f"{semestre_atual}º Nível ({versao}): {nome}",
                    )

            if disciplinas:
                metadados = {
                    "curriculo_id": cid,
                    "curso_slug": "automotiva",
                    "curso": "Engenharia Automotiva",
                    "vigencia": vig,
                    "versao_curriculo": versao,
                    "total_creditos": tot_cred,
                    "carga_horaria_total": tot_h,
                    "cobertura_prerequisitos": "indisponivel_na_base",
                    "cobertura_equivalencias": "indisponivel_na_base",
                    "fonte": dict(FONTE_F19),
                }
                grafos.append(cls(disciplinas, [], metadados=metadados))

        if not grafos:
            raise ValueError("Nenhuma estrutura curricular de Engenharia Automotiva encontrada em F19.")
        return grafos

    @classmethod
    def de_matriz_energia(cls, texto: str) -> "GrafoCurricular":
        """Extrai Engenharia de Energia a partir da matriz curada `F23`."""
        disciplinas: dict[str, Disciplina] = {}
        semestre_atual: int | None = None

        for linha in texto.splitlines():
            limpa = linha.strip()
            m_sem = _SEMESTRE_ENERGIA.match(limpa)
            if m_sem:
                semestre_atual = int(m_sem.group(1))
                continue
            m_disc = _DISC_ENERGIA.match(limpa)
            if m_disc and semestre_atual is not None:
                nome = m_disc.group("nome").strip()
                a, b, c = int(m_disc.group("a")), int(m_disc.group("b")), int(m_disc.group("c"))
                cred = c if c > 0 else (a + b)
                codigo = f"SEM-CODIGO:{_slug(nome)}"
                if codigo in disciplinas:
                    codigo = f"{codigo}-s{semestre_atual}"
                disciplinas[codigo] = Disciplina(
                    codigo=codigo,
                    nome=nome,
                    creditos=cred,
                    carga_horaria=cred * 15,
                    semestre=semestre_atual,
                    codigo_oficial=False,
                    evidencia=limpa.removeprefix("- ").strip(),
                )

        if not disciplinas:
            raise ValueError("Nenhuma disciplina reconhecível encontrada em F23 (Engenharia de Energia).")

        metadados = {
            "curriculo_id": "energia-2024",
            "curso_slug": "energia",
            "curso": "Engenharia de Energia",
            "vigencia": {
                "inicio": "2024/2",
                "fim": None,
                "ativa": True,
                "descricao": "Matriz Curricular Atual (publicada em 26/08/2024, 251 créditos)",
            },
            "versao_curriculo": "Matriz 2024 (251 créditos)",
            "total_creditos": 251,
            "carga_horaria_total": 3765,
            "cobertura_prerequisitos": "indisponivel_na_base",
            "cobertura_equivalencias": "indisponivel_na_base",
            "fonte": dict(FONTE_F23),
        }
        return cls(disciplinas, [], metadados=metadados)

    # ------------------------------------------------------------------ serialização e carregamento

    def para_dict(self) -> dict:
        nos = [
            asdict(self.disciplinas[c])
            for c in sorted(self.disciplinas, key=lambda x: (self.disciplinas[x].semestre, x))
        ]
        arestas = [
            {
                "origem": a.origem,
                "destino": a.destino,
                "relacao": a.relacao,
                "incerta": a.incerta,
                "alternativas": list(a.alternativas),
                "evidencia": a.evidencia,
            }
            for a in self.arestas
        ]
        equivalencias = [
            {
                "codigo": eq.codigo,
                "equivalentes": list(eq.equivalentes),
                "tipo": eq.tipo,
                "bidirecional": eq.bidirecional,
                "observacao": eq.observacao,
                "evidencia": eq.evidencia,
            }
            for eq in self.equivalencias
        ]
        return {
            "curriculo_id": self.metadados["curriculo_id"],
            "curso_slug": self.metadados["curso_slug"],
            "curso": self.metadados["curso"],
            "vigencia": dict(self.metadados["vigencia"]),
            "versao_curriculo": self.metadados["versao_curriculo"],
            "total_creditos": self.metadados["total_creditos"],
            "carga_horaria_total": self.metadados["carga_horaria_total"],
            "cobertura_prerequisitos": self.metadados["cobertura_prerequisitos"],
            "cobertura_equivalencias": self.metadados["cobertura_equivalencias"],
            "fonte": dict(self.metadados["fonte"]),
            "nos": nos,
            "arestas": arestas,
            "equivalencias": equivalencias,
        }

    @staticmethod
    def validar_json(dados: dict) -> None:
        import jsonschema

        schema = json.loads(SCHEMA_GRAFO.read_text(encoding="utf-8"))
        jsonschema.validate(dados, schema)

    @classmethod
    def de_dict(cls, dados: dict, curriculo_id: str = "software-2024-2") -> "GrafoCurricular":
        if "curriculos" in dados:
            return RepositorioGrafos.de_dict(dados).por_id(curriculo_id)
        cls.validar_json(dados)
        disciplinas = {n["codigo"]: Disciplina(**n) for n in dados["nos"]}
        arestas = [
            Aresta(
                origem=a["origem"],
                destino=a["destino"],
                relacao=a["relacao"],
                incerta=a["incerta"],
                evidencia=a["evidencia"],
                alternativas=tuple(a.get("alternativas") or ()),
            )
            for a in dados["arestas"]
        ]
        equivalencias = [
            Equivalencia(
                codigo=eq["codigo"],
                equivalentes=tuple(eq["equivalentes"]),
                tipo=eq["tipo"],
                bidirecional=eq["bidirecional"],
                observacao=eq.get("observacao", ""),
                evidencia=eq["evidencia"],
            )
            for eq in dados.get("equivalencias", [])
        ]
        metadados = {
            k: dados[k]
            for k in (
                "curriculo_id",
                "curso_slug",
                "curso",
                "vigencia",
                "versao_curriculo",
                "total_creditos",
                "carga_horaria_total",
                "cobertura_prerequisitos",
                "cobertura_equivalencias",
                "fonte",
            )
            if k in dados
        }
        return cls(disciplinas, arestas, metadados=metadados, equivalencias=equivalencias)

    def salvar_json(self, destino: Path = GRAFO_JSON) -> Path:
        dados = self.para_dict()
        self.validar_json(dados)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destino

    @classmethod
    def carregar_json(cls, caminho: Path = GRAFO_JSON, curriculo_id: str = "software-2024-2") -> "GrafoCurricular":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls.de_dict(dados, curriculo_id=curriculo_id)

    @classmethod
    def carregar_f16(cls, caminho: Path | None = None) -> "GrafoCurricular":
        if caminho is None and GRAFO_JSON.exists():
            return cls.carregar_json(GRAFO_JSON, curriculo_id="software-2024-2")
        fonte = caminho or (config.DADOS / "curados" / "F16_fluxograma_software.md")
        return cls.de_markdown(fonte.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ consultas

    def _construir_indices_busca(self) -> None:
        """Deriva dinamicamente siglas e nomes curtos únicos a partir das disciplinas do currículo."""
        candidatos_sigla: dict[str, set[str]] = {}
        candidatos_curto: dict[str, set[str]] = {}
        originais_sigla: dict[str, str] = {}

        def _reg_sigla(chave: str, cod: str, texto_orig: str | None = None) -> None:
            chave_norm = " ".join(chave.lower().split())
            if len(chave_norm) < 2 or chave_norm in _SIGLAS_BLOQUEADAS:
                return
            candidatos_sigla.setdefault(chave_norm, set()).add(cod)
            if texto_orig:
                originais_sigla[chave_norm] = texto_orig

        def _reg_curto(chave: str, cod: str) -> None:
            chave_norm = " ".join(chave.strip().split())
            if len(chave_norm) < 5 or chave_norm in _SIGLAS_BLOQUEADAS:
                return
            candidatos_curto.setdefault(chave_norm, set()).add(cod)

        for cod, disc in self.disciplinas.items():
            # 1) Siglas explícitas entre parênteses, ex.: "(APC)", "(MDS)", "(GCES)"
            for m_par in re.finditer(r"\(([A-Za-z0-9]{2,8})\)", disc.nome):
                tok = m_par.group(1)
                _reg_sigla(tok, cod, texto_orig=tok)

            sem_paren = re.sub(r"\([^)]*\)", "", disc.nome).strip()
            sem_paren_norm = _normalizar(sem_paren)
            if sem_paren_norm and sem_paren_norm != _normalizar(disc.nome):
                _reg_curto(sem_paren_norm, cod)

            # 2) Nomes curtos removendo sufixos genéricos no final quando únicos no currículo
            for suf in _SUFIXOS_CURTOS:
                if sem_paren_norm.endswith(suf):
                    prefixo = sem_paren_norm[: -len(suf)].strip()
                    _reg_curto(prefixo, cod)

            # 3) Siglas derivadas pelas iniciais de palavras significativas (ignorando stopwords)
            palavras = [p for p in sem_paren_norm.split() if p not in _STOPWORDS_SIGLA]
            if len(palavras) >= 2:
                letras_sigla: list[str] = []
                sufixo_digito = ""
                for idx_p, p in enumerate(palavras):
                    if idx_p == len(palavras) - 1 and re.fullmatch(r"\d+", p):
                        sufixo_digito = p
                    elif p:
                        letras_sigla.append(p[0])
                base_sigla = "".join(letras_sigla)
                if sufixo_digito and base_sigla:
                    _reg_sigla(base_sigla + sufixo_digito, cod)
                    _reg_sigla(f"{base_sigla} {sufixo_digito}", cod)
                elif len(base_sigla) >= 2:
                    _reg_sigla(base_sigla, cod, texto_orig=base_sigla.upper())

        self._siglas_curtas: dict[str, tuple[str, bool]] = {
            chave: (
                next(iter(cods)),
                len(chave) == 2 and not any(ch.isdigit() for ch in chave),
            )
            for chave, cods in candidatos_sigla.items()
            if len(cods) == 1
        }
        self._nomes_curtos: dict[str, str] = {
            chave: next(iter(cods))
            for chave, cods in candidatos_curto.items()
            if len(cods) == 1
        }

    def equivalentes_de(self, codigo: str) -> list[Equivalencia]:
        return list(self._equiv_por_codigo.get(codigo.upper(), []))

    def buscar_disciplinas(self, consulta: str) -> list[Disciplina]:
        consulta_norm = _normalizar(consulta)
        codigos = [c.upper() for c in CODIGO.findall(consulta)]
        encontradas: dict[str, Disciplina] = {}
        for codigo in codigos:
            if codigo in self.disciplinas:
                encontradas[codigo] = self.disciplinas[codigo]
                continue
            for eq in self.equivalentes_de(codigo):
                if eq.codigo in self.disciplinas:
                    encontradas[eq.codigo] = self.disciplinas[eq.codigo]
        restante = consulta_norm
        nomes = sorted(self.disciplinas.values(), key=lambda d: len(d.nome), reverse=True)
        for disciplina in nomes:
            nome = _normalizar(disciplina.nome)
            if nome and nome in restante:
                encontradas[disciplina.codigo] = disciplina
                restante = restante.replace(nome, " ")

        restante_apelidos = re.sub(
            r"\b(?:pre|co)-?requisitos?\b|\b(?:teste|testes)\s+de\s+(?:mesa|unidade|sistema)\b",
            " ",
            restante,
        )
        for curto in sorted(self._nomes_curtos, key=len, reverse=True):
            if re.search(rf"(?<![a-z0-9-]){re.escape(curto)}(?![a-z0-9-])", restante_apelidos):
                cod_alvo = self._nomes_curtos[curto]
                encontradas.setdefault(cod_alvo, self.disciplinas[cod_alvo])
                restante_apelidos = re.sub(
                    rf"(?<![a-z0-9-]){re.escape(curto)}(?![a-z0-9-])",
                    " ",
                    restante_apelidos,
                )

        # Siglas derivadas dinamicamente (siglas de 2 letras sem dígito exigem MAIÚSCULAS no texto original)
        consulta_mascarada_orig = re.sub(
            r"\b(?:pr[eé]|co)-?requisitos?\b",
            " ",
            consulta,
            flags=re.I,
        )
        for sigla, (cod_alvo, exige_maiuscula) in sorted(
            self._siglas_curtas.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if exige_maiuscula:
                sigla_upper = sigla.upper()
                if re.search(rf"(?<![A-Za-zÀ-ÿ0-9]){re.escape(sigla_upper)}(?![A-Za-zÀ-ÿ0-9])", consulta_mascarada_orig):
                    encontradas.setdefault(cod_alvo, self.disciplinas[cod_alvo])
            else:
                if re.search(rf"(?<![a-z0-9]){re.escape(sigla)}(?![a-z0-9])", restante_apelidos):
                    encontradas.setdefault(cod_alvo, self.disciplinas[cod_alvo])
                    restante_apelidos = re.sub(
                        rf"(?<![a-z0-9]){re.escape(sigla)}(?![a-z0-9])",
                        " ",
                        restante_apelidos,
                    )

        return sorted(encontradas.values(), key=lambda d: (d.semestre, d.codigo))

    def _to_aresta(self, origem: str, destino: str, attrs: dict) -> Aresta:
        return Aresta(
            origem=origem,
            destino=destino,
            relacao=attrs.get("relacao", "pre_requisito"),
            incerta=bool(attrs.get("incerta", False)),
            alternativas=tuple(attrs.get("alternativas") or ()),
            evidencia=attrs.get("evidencia", ""),
        )

    def _to_aresta_out(self, codigo: str) -> list[Aresta]:
        return [
            self._to_aresta(u, v, attrs)
            for u, v, attrs in self.grafo.out_edges(codigo, data=True)
        ]

    def _rotulo_disciplina(self, disc: Disciplina) -> str:
        return f"{disc.nome} ({disc.codigo})" if disc.codigo_oficial else disc.nome

    def _texto_vigencia(self) -> str:
        desc = self.vigencia.get("descricao") or self.metadados["versao_curriculo"]
        if self.curriculo_id == "software-2024-2":
            return "Esta transcrição vale para ingressantes após 2024/2."
        return f"Vigência do currículo consultado ({self.curso}): {desc}."

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

    def correquisitos_de(self, codigo: str) -> list[Aresta]:
        codigo = codigo.upper()
        return [
            a for a in self.arestas
            if a.relacao == "correquisito" and codigo in (a.origem, a.destino)
        ]

    def _evidencia(self, codigos: set[str], arestas: list[Aresta] | tuple[Aresta, ...], extras: list[str] = ()) -> str:
        doc_id = self.metadados["fonte"]["doc_id"]
        linhas = [self.disciplinas[c].evidencia for c in sorted(codigos) if c in self.disciplinas]
        linhas.extend(a.evidencia for a in arestas if a.evidencia)
        linhas.extend(e for e in extras if e)
        linhas.append(f"Currículo: {self.curso} ({doc_id}) — vigência: {self.vigencia['descricao']}.")
        return "\n".join(dict.fromkeys(linhas))

    def _dependentes_no_grafo(self, grafo_alvo: nx.DiGraph, codigo: str) -> set[str]:
        bloqueados = {codigo}
        mudou = True
        while mudou:
            mudou = False
            for destino in grafo_alvo.nodes():
                if destino in bloqueados:
                    continue
                for orig, _, attrs in grafo_alvo.in_edges(destino, data=True):
                    grupo = {orig} | {
                        alt for alt in (attrs.get("alternativas") or ()) if alt in self.disciplinas
                    }
                    if grupo <= bloqueados:
                        bloqueados.add(destino)
                        mudou = True
                        break
        return bloqueados - {codigo}

    def dependentes(self, codigo: str) -> tuple[list[str], list[str]]:
        codigo = codigo.upper()
        if codigo not in self.grafo:
            return [], []
        confirmados = self._dependentes_no_grafo(self.grafo, codigo)
        todos = self._dependentes_no_grafo(self.grafo_completo, codigo)
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

    def _clausula_satisfeita(self, aresta: Aresta, aprovadas: set[str]) -> bool:
        opcoes = {aresta.origem, *aresta.alternativas}
        return bool(opcoes & aprovadas)

    def disciplinas_que_abrem(self, aprovadas: set[str]) -> tuple[list[str], list[str]]:
        aprovadas = {c.upper() for c in aprovadas}
        abertas: list[str] = []
        incertas: list[str] = []
        for codigo in self.grafo_completo:
            if codigo in aprovadas:
                continue
            confirmados, duvidosos = self.prerequisitos(codigo)
            if confirmados:
                if all(self._clausula_satisfeita(a, aprovadas) for a in confirmados):
                    (incertas if duvidosos else abertas).append(codigo)
            elif duvidosos and any(self._clausula_satisfeita(a, aprovadas) for a in duvidosos):
                incertas.append(codigo)
        return (
            sorted(abertas, key=lambda c: (self.disciplinas[c].semestre, c)),
            sorted(incertas, key=lambda c: (self.disciplinas[c].semestre, c)),
        )

    def caminho_critico(self) -> list[str]:
        if not self.grafo.number_of_nodes() or not self.grafo.number_of_edges():
            return []
        return list(nx.dag_longest_path(self.grafo))

    def _fonte_dict(self) -> dict:
        fonte = dict(self.metadados["fonte"])
        fonte.setdefault("secao", f"Grafo curricular · {self.curso}")
        fonte.setdefault("chunk_id", f"{fonte['doc_id']}-grafo-{self.curriculo_id}")
        return fonte

    def _no_resumo(self, codigo: str) -> dict:
        d = self.disciplinas[codigo]
        return {
            "codigo": d.codigo,
            "nome": d.nome,
            "semestre": d.semestre,
            "creditos": d.creditos,
            "carga_horaria": d.carga_horaria,
            "codigo_oficial": d.codigo_oficial,
        }

    def _metadados_consulta(self) -> dict:
        return {
            "curriculo_id": self.curriculo_id,
            "curso": self.curso,
            "curso_slug": self.curso_slug,
            "vigencia": dict(self.vigencia),
            "cobertura_prerequisitos": self.cobertura_prerequisitos,
            "cobertura_equivalencias": self.cobertura_equivalencias,
        }

    def _nota_resolucao_equivalencia(self, codigos_mencionados: list[str]) -> str:
        notas: list[str] = []
        for cod in codigos_mencionados:
            if cod not in self.disciplinas and self.equivalentes_de(cod):
                eq = self.equivalentes_de(cod)[0]
                if eq.codigo in self.disciplinas:
                    alvo = self.disciplinas[eq.codigo]
                    notas.append(f"Observação: o código {cod} equivale a {alvo.nome} ({alvo.codigo}) neste currículo.")
        return " ".join(notas)

    def _resposta_prerequisitos_indisponiveis(self, pergunta: str, disciplinas: list[Disciplina]) -> dict:
        doc_id = self.metadados["fonte"]["doc_id"]
        fonte = self._fonte_dict()
        extras = [d.evidencia for d in disciplinas]
        evidencia = self._evidencia(
            {d.codigo for d in disciplinas},
            [],
            extras=extras or [f"{self.curso} ({doc_id}) — {self.vigencia['descricao']}."],
        )
        if disciplinas:
            d0 = disciplinas[-1]
            trecho_disc = f" A disciplina '{d0.nome}' consta no {d0.semestre}º nível desse currículo."
        else:
            trecho_disc = ""
        texto = (
            f"O documento oficial de {self.curso} na base ({doc_id}, vigência: {self.vigencia['descricao']}) "
            f"lista as disciplinas por semestre,{trecho_disc or ' '} mas não informa os códigos SIGAA nem as relações de "
            f"pré-requisito entre elas. [1] Confirme os pré-requisitos diretamente no Projeto Pedagógico completo ou no SIGAA. [1]"
        ).replace(" ,", ",")
        return {
            "tipo_consulta": "prerequisitos_indisponiveis",
            "dados": {
                **self._metadados_consulta(),
                "disciplinas": [self._no_resumo(d.codigo) for d in disciplinas],
                "fallback_rag": False,
            },
            "texto": texto,
            "evidencia": evidencia,
            "fonte": fonte,
            "alertas": [
                f"Base sem grafo de pré-requisitos para {self.curso} ({doc_id})."
            ],
        }

    def _consultar_equivalencias(
        self,
        disciplinas: list[Disciplina],
        codigos_consulta: list[str],
    ) -> dict:
        doc_id = self.metadados["fonte"]["doc_id"]
        fonte = self._fonte_dict()
        codigos = {d.codigo for d in disciplinas}
        itens_eq: list[Equivalencia] = []
        if disciplinas or codigos_consulta:
            vistos: set[tuple[str, tuple[str, ...]]] = set()
            for cod in [d.codigo for d in disciplinas] + codigos_consulta:
                for eq in self.equivalentes_de(cod):
                    chave = (eq.codigo, eq.equivalentes)
                    if chave not in vistos:
                        vistos.add(chave)
                        itens_eq.append(eq)
        else:
            itens_eq = list(self.equivalencias)

        if not itens_eq:
            alerta = (
                f"Nenhuma equivalência encontrada para a consulta em {self.curso} "
                f"({doc_id}, cobertura: {self.cobertura_equivalencias})."
            )
            return {
                "tipo_consulta": "equivalencias",
                "dados": {
                    **self._metadados_consulta(),
                    "equivalencias": [],
                    "fallback_rag": False,
                },
                "texto": (
                    f"A fonte oficial de {self.curso} na base ({doc_id}, vigência: {self.vigencia['descricao']}) "
                    f"não registra equivalência para os termos informados (cobertura na base: "
                    f"{self.cobertura_equivalencias}). [1] Confirme a tabela completa de equivalências no SIGAA. [1]"
                ),
                "evidencia": self._evidencia(codigos, [], extras=[eq.evidencia for eq in self.equivalencias[:5]]),
                "fonte": fonte,
                "alertas": [alerta],
            }

        partes_eq: list[str] = []
        payload_eq: list[dict] = []
        evid_cods: set[str] = set()
        for eq in itens_eq:
            evid_cods.add(eq.codigo)
            disc = self.disciplinas.get(eq.codigo)
            nome_disc = f"{disc.nome} ({eq.codigo})" if disc else eq.codigo
            equivs_txt = ", ".join(eq.equivalentes)
            seta = "↔" if eq.bidirecional else "→"
            partes_eq.append(f"{nome_disc} {seta} {equivs_txt} ({eq.observacao})")
            payload_eq.append({
                "codigo": eq.codigo,
                "nome": disc.nome if disc else eq.codigo,
                "equivalentes": list(eq.equivalentes),
                "tipo": eq.tipo,
                "bidirecional": eq.bidirecional,
                "observacao": eq.observacao,
            })

        aviso_cobertura = (
            " Como o documento traz apenas as equivalências destacadas na reforma/fluxograma, "
            "confirme outras equivalências no SIGAA. [1]"
            if self.cobertura_equivalencias != "completa"
            else ""
        )
        resposta = (
            f"Equivalências registradas para {self.curso} ({doc_id}, vigência: {self.vigencia['descricao']}): "
            + "; ".join(partes_eq)
            + ". [1]"
            + aviso_cobertura
        )
        alertas = (
            []
            if self.cobertura_equivalencias == "completa"
            else ["Cobertura parcial de equivalências; confirmar tabela completa no SIGAA."]
        )
        return {
            "tipo_consulta": "equivalencias",
            "dados": {
                **self._metadados_consulta(),
                "equivalencias": payload_eq,
            },
            "texto": resposta,
            "evidencia": self._evidencia(evid_cods, [], extras=[eq.evidencia for eq in itens_eq]),
            "fonte": fonte,
            "alertas": alertas,
        }

    def _consultar_caminho_critico(self) -> dict | None:
        caminho = self.caminho_critico()
        if not caminho:
            return None
        doc_id = self.metadados["fonte"]["doc_id"]
        nomes = " → ".join(f"{self.disciplinas[c].nome} ({c})" for c in caminho)
        arestas_caminho = [
            self._to_aresta(u, v, attrs)
            for u, v, attrs in self.grafo.edges(data=True)
            if u in caminho and v in caminho
        ]
        evidencia = self._evidencia(set(caminho), arestas_caminho)
        resposta = (
            f"A maior cadeia de pré-requisitos confirmados em {self.curso} ({doc_id}) é: {nomes}. [1] "
            "Isso representa a cadeia mais longa registrada no grafo, não uma previsão "
            "de semestres até a formatura; oferta de turmas e requisitos fora do documento "
            f"devem ser confirmados no SIGAA. {self._texto_vigencia()} [1]"
        )
        return {
            "tipo_consulta": "caminho_critico",
            "dados": {
                **self._metadados_consulta(),
                "comprimento": len(caminho),
                "cadeia": [self._no_resumo(c) for c in caminho],
            },
            "texto": resposta,
            "evidencia": evidencia,
            "fonte": self._fonte_dict(),
            "alertas": [],
        }

    def _consultar_gargalos(self) -> dict | None:
        ranking = self.gargalos()
        if not ranking:
            return None
        doc_id = self.metadados["fonte"]["doc_id"]
        quantidade = ranking[0][1]
        todas_arestas: list[Aresta] = []
        itens_gargalo: list[dict] = []
        partes_texto: list[str] = []
        for disciplina, _ in ranking:
            arestas = self._to_aresta_out(disciplina.codigo)
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
                f"Pelo número de dependências diretas confirmadas em {self.curso} ({doc_id}), {d0.nome} "
                f"({d0.codigo}) é o principal gargalo: destrava {quantidade} disciplina(s) "
                f"diretamente ({dest0}). [1] A contagem considera apenas setas cheias; "
                f"ligações tracejadas não entram no ranking. {self._texto_vigencia()} [1]"
            )
        else:
            resumo = "; ".join(partes_texto)
            resposta = (
                f"Pelo número de dependências diretas confirmadas em {self.curso} ({doc_id}), há empate no topo "
                f"com {quantidade} disciplina(s) destravada(s) diretamente cada: {resumo}. [1] "
                "A contagem considera apenas setas cheias; ligações tracejadas não entram no "
                f"ranking. {self._texto_vigencia()} [1]"
            )
        return {
            "tipo_consulta": "gargalo",
            "dados": {
                **self._metadados_consulta(),
                "grau_saida_max": quantidade,
                "gargalos": itens_gargalo,
            },
            "texto": resposta,
            "evidencia": evidencia,
            "fonte": self._fonte_dict(),
            "alertas": [],
        }

    def _consultar_disciplinas_que_abrem(
        self,
        codigos: set[str],
        codigos_consulta: list[str],
    ) -> dict:
        doc_id = self.metadados["fonte"]["doc_id"]
        abertas, incertas = self.disciplinas_que_abrem(codigos)
        aprovadas_txt = ", ".join(sorted(codigos))
        arestas_usadas = [
            a for a in self.arestas
            if a.destino in abertas + incertas
            and a.relacao == "pre_requisito"
            and (a.origem in codigos or bool(set(a.alternativas) & codigos))
        ]
        evidencia = self._evidencia(codigos | set(abertas) | set(incertas), arestas_usadas)
        if abertas:
            nomes = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in abertas)
            resposta = f"Com aprovação em {aprovadas_txt} ({self.curso}), ficam liberadas pelo grafo: {nomes}. [1]"
        else:
            resposta = (
                f"Com aprovação em {aprovadas_txt} ({self.curso}), não identifiquei novas disciplinas "
                f"liberadas apenas por pré-requisitos confirmados no {doc_id}. [1]"
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
        nota_eq = self._nota_resolucao_equivalencia(codigos_consulta)
        if nota_eq:
            resposta += f" {nota_eq}"
        resposta += f" {self._texto_vigencia()} [1]"
        return {
            "tipo_consulta": "disciplinas_que_abrem",
            "dados": {
                **self._metadados_consulta(),
                "aprovadas": sorted(codigos),
                "abertas_confirmadas": [self._no_resumo(c) for c in abertas],
                "relacoes_incertas": [self._no_resumo(c) for c in incertas],
            },
            "texto": resposta,
            "evidencia": evidencia,
            "fonte": self._fonte_dict(),
            "alertas": [],
        }

    def _consultar_dependentes(
        self,
        inicio: Disciplina,
        codigos_consulta: list[str],
    ) -> dict:
        doc_id = self.metadados["fonte"]["doc_id"]
        confirmados, incertos = self.dependentes(inicio.codigo)
        nos_envolvidos = {inicio.codigo, *confirmados, *incertos}
        arestas_usadas_obj = [
            self._to_aresta(u, v, attrs)
            for u, v, attrs in self.grafo_completo.edges(data=True)
            if u in nos_envolvidos and v in nos_envolvidos
        ]
        arestas_ou_rel = [
            a for a in self.arestas
            if a.relacao == "pre_requisito"
            and not a.incerta
            and a.alternativas
            and (a.origem == inicio.codigo or inicio.codigo in a.alternativas)
            and a.destino not in confirmados
        ]
        for a_ou in arestas_ou_rel:
            nos_envolvidos.update((a_ou.origem, a_ou.destino, *a_ou.alternativas))
            arestas_usadas_obj.append(a_ou)
        if confirmados:
            nomes = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in confirmados)
            resposta = (
                f"Se você reprovar em {inicio.nome} ({inicio.codigo}) em {self.curso}, as disciplinas "
                f"alcançáveis por uma cadeia de pré-requisitos confirmados são: {nomes}. [1]"
            )
        else:
            resposta = (
                f"Não encontrei dependentes alcançáveis por bloqueio direto a partir de "
                f"{inicio.nome} ({inicio.codigo}) em {self.curso} ({doc_id}). [1]"
            )
        if arestas_ou_rel:
            notas_ou = []
            for a_ou in arestas_ou_rel:
                dest_disc = self.disciplinas[a_ou.destino]
                opcoes = [a_ou.origem, *(alt for alt in a_ou.alternativas if alt in self.disciplinas)]
                opcoes_txt = " ou ".join(f"{self.disciplinas[c].nome} ({c})" for c in opcoes)
                notas_ou.append(
                    f"Nota: {dest_disc.nome} ({dest_disc.codigo}) aceita pré-requisito alternativo "
                    f"({opcoes_txt}), portanto reprovar apenas em {inicio.nome} ({inicio.codigo}) "
                    "não a bloqueia se a alternativa já tiver sido cursada. [1]"
                )
            resposta += " " + " ".join(notas_ou)
        if incertos:
            nomes_inc = ", ".join(f"{self.disciplinas[c].nome} ({c})" for c in incertos)
            resposta += (
                f" A cadeia também pode alcançar {nomes_inc} por ligação tracejada; "
                "não é possível afirmar que bloqueia. Confirme no SIGAA. [1]"
            )
        nota_eq = self._nota_resolucao_equivalencia(codigos_consulta)
        if nota_eq:
            resposta += f" {nota_eq}"
        resposta += f" {self._texto_vigencia()} [1]"
        return {
            "tipo_consulta": "dependentes",
            "dados": {
                **self._metadados_consulta(),
                "origem": self._no_resumo(inicio.codigo),
                "dependentes_confirmados": [self._no_resumo(c) for c in confirmados],
                "dependentes_incertos": [self._no_resumo(c) for c in incertos],
            },
            "texto": resposta,
            "evidencia": self._evidencia(nos_envolvidos, arestas_usadas_obj),
            "fonte": self._fonte_dict(),
            "alertas": [],
        }

    def _consultar_prerequisitos(
        self,
        alvo: Disciplina,
        codigos_consulta: list[str],
    ) -> dict:
        doc_id = self.metadados["fonte"]["doc_id"]
        confirmados, incertos = self.prerequisitos(alvo.codigo)
        coreqs = self.correquisitos_de(alvo.codigo)
        partes: list[str] = []
        if confirmados:
            nomes_list = []
            for a in confirmados:
                txt_orig = f"{self.disciplinas[a.origem].nome} ({a.origem})"
                if a.alternativas:
                    alts_txt = " ou ".join(
                        f"{self.disciplinas[alt].nome} ({alt})"
                        if alt in self.disciplinas
                        else alt
                        for alt in a.alternativas
                    )
                    txt_orig += f" ou {alts_txt}"
                nomes_list.append(txt_orig)
            partes.append(f"Pré-requisitos confirmados de {alvo.nome} ({alvo.codigo}) em {self.curso}: {', '.join(nomes_list)}.")
        else:
            partes.append(
                f"A fonte {doc_id} ({self.curso}) não registra seta cheia de pré-requisito para "
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
        if coreqs:
            pares_cr = [
                f"{self.disciplinas[outro].nome} ({outro})"
                for c in coreqs
                if (outro := c.destino if c.origem == alvo.codigo else c.origem) in self.disciplinas
            ]
            if pares_cr:
                partes.append(f"Correquisito(s): {', '.join(pares_cr)}.")
        nota_eq = self._nota_resolucao_equivalencia(codigos_consulta)
        if nota_eq:
            partes.append(nota_eq)
        partes.append(self._texto_vigencia())

        cods_ev = {alvo.codigo, *(a.origem for a in confirmados + incertos)}
        for a in confirmados + incertos:
            cods_ev.update(a.alternativas)
        for c in coreqs:
            cods_ev.update((c.origem, c.destino))
        confirmados_payload = []
        for a in confirmados:
            item_conf = self._no_resumo(a.origem)
            if a.alternativas:
                item_conf["alternativas"] = [
                    self._no_resumo(alt) if alt in self.disciplinas else {"codigo": alt}
                    for alt in a.alternativas
                ]
            confirmados_payload.append(item_conf)
        return {
            "tipo_consulta": "prerequisitos",
            "dados": {
                **self._metadados_consulta(),
                "disciplina": self._no_resumo(alvo.codigo),
                "confirmados": confirmados_payload,
                "incertos": [self._no_resumo(a.origem) for a in incertos],
                "correquisitos": [
                    self._no_resumo(c.destino if c.origem == alvo.codigo else c.origem)
                    for c in coreqs
                    if (c.destino if c.origem == alvo.codigo else c.origem) in self.disciplinas
                ],
            },
            "texto": " ".join(p + " [1]" for p in partes),
            "evidencia": self._evidencia(cods_ev, confirmados + incertos + coreqs),
            "fonte": self._fonte_dict(),
            "alertas": [],
        }

    def _consultar_vigencia_ou_semestre(self, sem_num: int | None) -> dict:
        doc_id = self.metadados["fonte"]["doc_id"]
        fonte = self._fonte_dict()
        if sem_num is not None:
            do_sem = sorted(
                [d for d in self.disciplinas.values() if d.semestre == sem_num],
                key=lambda d: d.codigo,
            )
            nomes = ", ".join(self._rotulo_disciplina(d) for d in do_sem)
            resposta = (
                f"No {sem_num}º semestre/nível de {self.curso} ({doc_id}, vigência: {self.vigencia['descricao']}), "
                f"constam {len(do_sem)} componente(s): {nomes or 'nenhum registrado'}. [1]"
            )
            return {
                "tipo_consulta": "vigencia_curriculo",
                "dados": {
                    **self._metadados_consulta(),
                    "semestre": sem_num,
                    "disciplinas": [self._no_resumo(d.codigo) for d in do_sem],
                },
                "texto": resposta,
                "evidencia": self._evidencia({d.codigo for d in do_sem}, []),
                "fonte": fonte,
                "alertas": [],
            }

        evidencia = f"{self.curso} ({doc_id}) — vigência: {self.vigencia['descricao']} · {len(self.disciplinas)} disciplinas obrigatórias."
        ch = f", carga horária total {self.metadados['carga_horaria_total']}h" if self.metadados["carga_horaria_total"] else ""
        cred = f", {self.metadados['total_creditos']} créditos" if self.metadados["total_creditos"] else ""
        resposta = (
            f"Currículo de {self.curso} ({self.curriculo_id}, {doc_id}): vigência '{self.vigencia['descricao']}' "
            f"(início {self.vigencia['inicio']}"
            + (f", fim {self.vigencia['fim']}" if self.vigencia.get("fim") else ", sem data de término")
            + f"{cred}{ch}), com {len(self.disciplinas)} disciplinas obrigatórias, cobertura de pré-requisitos "
            f"'{self.cobertura_prerequisitos}' e de equivalências '{self.cobertura_equivalencias}'. [1]"
        )
        return {
            "tipo_consulta": "vigencia_curriculo",
            "dados": {
                **self._metadados_consulta(),
                "total_disciplinas": len(self.disciplinas),
            },
            "texto": resposta,
            "evidencia": evidencia,
            "fonte": fonte,
            "alertas": [],
        }

    def consultar_estruturado(self, pergunta: str) -> dict | None:
        """Executa consulta no grafo e devolve payload estruturado + texto + evidência."""
        texto = _normalizar(pergunta)
        disciplinas = self.buscar_disciplinas(pergunta)
        codigos_consulta = [c.upper() for c in CODIGO.findall(pergunta)]
        codigos = {d.codigo for d in disciplinas}

        if re.search(r"\bequival[eê]nc|c[oó]digo\s+antigo|substitu", texto):
            return self._consultar_equivalencias(disciplinas, codigos_consulta)

        eh_prereq_op = bool(
            re.search(
                r"caminho critico|quantos semestres.*formar|tempo.*formar"
                r"|gargalo|destrava.*mais|mais (?:materias|disciplinas)|maior numero"
                r"|passando|passei|aprovad[oa]s?|o que abre|quais.*abre"
                r"|reprov|trava|bloque|dependente|depende de"
                r"|pre-?requisito|co-?requisito",
                texto,
            )
        )
        if eh_prereq_op and self.cobertura_prerequisitos == "indisponivel_na_base":
            return self._resposta_prerequisitos_indisponiveis(pergunta, disciplinas)

        if re.search(r"caminho critico|quantos semestres.*formar|tempo.*formar", texto):
            return self._consultar_caminho_critico()
        if re.search(r"gargalo|destrava.*mais|mais (?:materias|disciplinas)|maior numero", texto):
            return self._consultar_gargalos()
        if re.search(r"passando|passei|aprovad[oa]s?|o que abre|quais.*abre", texto):
            return self._consultar_disciplinas_que_abrem(codigos, codigos_consulta) if codigos else None
        if re.search(r"reprov|trava|bloque|dependente|depende de", texto) and disciplinas:
            return self._consultar_dependentes(disciplinas[0], codigos_consulta)
        if re.search(r"pre-?requisito|co-?requisito", texto) and disciplinas:
            return self._consultar_prerequisitos(disciplinas[-1], codigos_consulta)

        m_sem_grade = re.search(
            r"\b(?:disciplinas?|materias?|grade)\s+do\s+(\d+)[º°o]?\s*(?:semestre|nivel)\b",
            texto,
        )
        if m_sem_grade or re.search(r"\bvig[eê]nc|\bqual\s+curr[ií]culo\b|\bcurr[ií]culo\s+(?:antigo|novo|vigente|atual)\b", texto):
            return self._consultar_vigencia_ou_semestre(int(m_sem_grade.group(1)) if m_sem_grade else None)

        return None

    def consultar(self, pergunta: str) -> ConsultaGrafo | None:
        res = self.consultar_estruturado(pergunta)
        if res is None:
            return None
        return ConsultaGrafo(res["texto"], res["evidencia"], tuple(res["alertas"]))


class RepositorioGrafos:
    """Catálogo multi-curso e multi-vigência dos grafos curriculares da FCTE."""

    def __init__(self, grafos: list[GrafoCurricular] | tuple[GrafoCurricular, ...]):
        self.curriculos: dict[str, GrafoCurricular] = {}
        for g in grafos:
            if g.curriculo_id in self.curriculos:
                raise ValueError(f"curriculo_id duplicado: {g.curriculo_id}")
            self.curriculos[g.curriculo_id] = g
        self._consultar_cache = lru_cache(maxsize=128)(self._consultar_estruturado_uncached)

    def por_id(self, curriculo_id: str) -> GrafoCurricular:
        if curriculo_id not in self.curriculos:
            raise KeyError(f"Currículo desconhecido: {curriculo_id!r}")
        return self.curriculos[curriculo_id]

    def listar_curriculos(self, curso: str | None = None) -> list[dict]:
        slug_filtro = _resolver_slug_curso(curso) if curso else None
        saida = []
        for g in self.curriculos.values():
            if slug_filtro and g.curso_slug != slug_filtro:
                continue
            saida.append({
                "curriculo_id": g.curriculo_id,
                "curso_slug": g.curso_slug,
                "curso": g.curso,
                "vigencia": dict(g.vigencia),
                "total_creditos": g.metadados["total_creditos"],
                "carga_horaria_total": g.metadados["carga_horaria_total"],
                "nos": len(g.disciplinas),
                "arestas": len(g.arestas),
                "equivalencias": len(g.equivalencias),
                "cobertura_prerequisitos": g.cobertura_prerequisitos,
                "cobertura_equivalencias": g.cobertura_equivalencias,
                "doc_id": g.metadados["fonte"]["doc_id"],
            })
        return saida

    @classmethod
    def construir_todos_fcte(cls, dados_dir: Path | None = None) -> "RepositorioGrafos":
        base = dados_dir or config.DADOS
        f16 = (base / "curados" / "F16_fluxograma_software.md").read_text(encoding="utf-8")
        f17 = (base / "texto" / "F17.txt").read_text(encoding="utf-8")
        f21 = (base / "texto" / "F21.txt").read_text(encoding="utf-8")
        f19 = (base / "texto" / "F19.txt").read_text(encoding="utf-8")
        f23 = (base / "curados" / "F23_matriz_energia.md").read_text(encoding="utf-8")

        grafos = [
            GrafoCurricular.de_markdown(f16),
            GrafoCurricular.de_ppc_aeroespacial(f17),
            GrafoCurricular.de_ppc_eletronica(f21),
            *GrafoCurricular.de_estruturas_automotiva(f19),
            GrafoCurricular.de_matriz_energia(f23),
        ]
        repo = cls(grafos)
        GrafoCurricular.validar_json(repo.para_dict())
        return repo

    def para_dict(self) -> dict:
        return {
            "versao_schema": "2.0",
            "instituicao": "UnB · Faculdade de Ciências e Tecnologias em Engenharia (FCTE)",
            "curriculos": [g.para_dict() for g in self.curriculos.values()],
        }

    @classmethod
    def de_dict(cls, dados: dict) -> "RepositorioGrafos":
        GrafoCurricular.validar_json(dados)
        if "curriculos" in dados:
            return cls([GrafoCurricular.de_dict(item) for item in dados["curriculos"]])
        return cls([GrafoCurricular.de_dict(dados)])

    def salvar_json(self, destino: Path = GRAFO_JSON) -> Path:
        dados = self.para_dict()
        GrafoCurricular.validar_json(dados)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destino

    @classmethod
    def carregar_json(cls, caminho: Path = GRAFO_JSON) -> "RepositorioGrafos":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return cls.de_dict(dados)

    def _candidatos_por_vigencia(self, lista: list[GrafoCurricular], texto: str) -> list[GrafoCurricular]:
        if len(lista) <= 1:
            return lista
        norm = _normalizar(texto)
        anos = re.findall(r"\b(20\d{2}(?:/[12])?)\b", norm)
        if anos:
            alvo = anos[-1]
            filtrados = []
            for g in lista:
                ini = str(g.vigencia.get("inicio", ""))
                fim = str(g.vigencia.get("fim") or "")
                desc = _normalizar(str(g.vigencia.get("descricao", "")))
                if alvo in ini or alvo in fim or alvo in desc:
                    filtrados.append(g)
                    continue
                m_alvo = re.match(r"(20\d{2})", alvo)
                m_ini = re.match(r"(20\d{2})", ini)
                m_fim = re.match(r"(20\d{2})", fim)
                if m_alvo and m_ini:
                    y_a, y_i = int(m_alvo.group(1)), int(m_ini.group(1))
                    y_f = int(m_fim.group(1)) if m_fim else 9999
                    if y_i <= y_a <= y_f:
                        filtrados.append(g)
            if filtrados:
                return filtrados
        if re.search(r"\bantig[oa]|\banterior", norm):
            antigos = [g for g in lista if g.vigencia.get("fim") is not None]
            if antigos:
                return antigos
        if re.search(r"\bnov[oa]|\batual|\bvigente", norm):
            novos = [g for g in lista if g.vigencia.get("fim") is None and g.vigencia.get("ativa")]
            if novos:
                return novos
        return lista

    def selecionar(
        self,
        consulta: str,
        curso: str | None = None,
        curriculo_id: str | None = None,
        vigencia: str | None = None,
    ) -> list[GrafoCurricular]:
        if curriculo_id and curriculo_id in self.curriculos:
            return [self.curriculos[curriculo_id]]

        slug = _resolver_slug_curso(curso) if curso else _resolver_slug_curso(consulta)
        texto_vig = f"{vigencia or ''} {consulta}"
        if slug:
            do_curso = [g for g in self.curriculos.values() if g.curso_slug == slug]
            return self._candidatos_por_vigencia(do_curso, texto_vig)

        # Sem curso explícito: tenta casar por código/nome de disciplina ou equivalência
        pontuados: list[tuple[int, int, GrafoCurricular]] = []
        for idx, g in enumerate(self.curriculos.values()):
            discs = g.buscar_disciplinas(consulta)
            if discs:
                # Prioriza software-2024-2 em empates para preservar comportamento padrão (F16)
                prio = 0 if g.curriculo_id == "software-2024-2" else 1
                pontuados.append((-len(discs), prio, idx, g))
        if pontuados:
            pontuados.sort(key=lambda t: (t[0], t[1], t[2]))
            melhor_n = pontuados[0][0]
            candidatos = [t[3] for t in pontuados if t[0] == melhor_n]
            if len(candidatos) > 1 and any(g.curriculo_id == "software-2024-2" for g in candidatos):
                return [self.curriculos["software-2024-2"]]
            return candidatos

        # Perguntas genéricas (ex.: "caminho crítico", "gargalo") sem curso -> F16 por compatibilidade
        if "software-2024-2" in self.curriculos:
            return [self.curriculos["software-2024-2"]]
        return list(self.curriculos.values())[:1]

    def _consultar_estruturado_uncached(
        self,
        pergunta: str,
        curso: str | None = None,
        curriculo_id: str | None = None,
        vigencia: str | None = None,
    ) -> dict | None:
        candidatos = self.selecionar(
            pergunta, curso=curso, curriculo_id=curriculo_id, vigencia=vigencia
        )
        for grafo in candidatos:
            res = grafo.consultar_estruturado(pergunta)
            if res is None:
                continue
            mesmo_curso = [g for g in self.curriculos.values() if g.curso_slug == grafo.curso_slug]
            outras = [
                {"curriculo_id": g.curriculo_id, "vigencia": dict(g.vigencia)}
                for g in mesmo_curso
                if g.curriculo_id != grafo.curriculo_id
            ]
            if outras:
                res["dados"]["outras_vigencias"] = outras
                res["texto"] += (
                    " Observação: este curso possui outra vigência cadastrada ("
                    + ", ".join(o["vigencia"]["descricao"] for o in outras)
                    + ")."
                )
            return res
        return None

    def consultar_estruturado(
        self,
        pergunta: str,
        curso: str | None = None,
        curriculo_id: str | None = None,
        vigencia: str | None = None,
    ) -> dict | None:
        res = self._consultar_cache(pergunta, curso, curriculo_id, vigencia)
        return copy.deepcopy(res) if res is not None else None


def _resolver_slug_curso(texto: str | None) -> str | None:
    if not texto:
        return None
    norm = _normalizar(texto)
    for slug, padrao in _PADROES_CURSO:
        if padrao.search(norm):
            return slug
    return None


@lru_cache(maxsize=1)
def carregar_grafo_f16() -> GrafoCurricular:
    """Carrega uma única vez por processo o grafo curricular de Engenharia de Software (F16)."""
    return GrafoCurricular.carregar_f16()


@lru_cache(maxsize=1)
def carregar_repositorio_grafos() -> RepositorioGrafos:
    """Carrega uma única vez por processo o repositório multi-curso da FCTE."""
    if GRAFO_JSON.exists():
        dados = json.loads(GRAFO_JSON.read_text(encoding="utf-8"))
        if "curriculos" in dados:
            return RepositorioGrafos.de_dict(dados)
    return RepositorioGrafos.construir_todos_fcte()
