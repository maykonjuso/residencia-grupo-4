"""Extração determinística, validação de vigência e consulta do calendário acadêmico (Issue #57)."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import jsonschema
import yaml

from . import config

_SCHEMA_PATH = Path(__file__).resolve().with_name("schema_calendario.json")
_CACHE: dict[tuple[str, float], CalendarioAcademico] = {}

DIAS_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

_MESES = {
    "janeiro": 1,
    "jan": 1,
    "fevereiro": 2,
    "fev": 2,
    "março": 3,
    "marco": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "maio": 5,
    "mai": 5,
    "junho": 6,
    "jun": 6,
    "julho": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "setembro": 9,
    "set": 9,
    "outubro": 10,
    "out": 10,
    "novembro": 11,
    "nov": 11,
    "dezembro": 12,
    "dez": 12,
}

_MESES_EXTENSO = (
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

_RE_TERMOS_CALENDARIO = re.compile(
    r"\b(?:"
    r"feriado|feriados|ponto\s+facultativo|pontos\s+facultativos|"
    r"recesso|semana\s+de\s+provas|calend[aá]rio\s+acad[eê]mico|"
    r"per[ií]odo\s+letivo|semestre\s+letivo|semana\s+universit[aá]ria|"
    r"tem\s+aula|h[aá]\s+aula|haver[aá]\s+aula|vai\s+ter\s+aula|"
    r"in[ií]cio\s+das\s+aulas|t[eé]rmino\s+das\s+aulas|fim\s+das\s+aulas|"
    r"quando\s+come[cç]am\s+as\s+aulas|quando\s+terminam\s+as\s+aulas"
    r")\b",
    re.IGNORECASE,
)

_RE_EXCLUSAO_GRADE = re.compile(
    r"\b(?:disciplina|mat[eé]ria|pr[eé]-?requisito|cr[eé]ditos?|ementa|fluxograma|curso|ru|restaurante|card[aá]pio|almo[cç]o|jantar|desjejum)\b",
    re.IGNORECASE,
)


def _br_para_iso(data_br: str) -> str:
    d, m, y = data_br.strip().split("/")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def _iso_para_date(data_iso: str) -> date:
    return date.fromisoformat(data_iso.strip())


def _iso_para_br(data_iso: str) -> str:
    return _iso_para_date(data_iso).strftime("%d/%m/%Y")


def _parse_data_flexivel(valor: date | str) -> date:
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    texto = str(valor).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return date.fromisoformat(texto)
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        d, m, y = texto.split("/")
        return date(int(y), int(m), int(d))
    raise ValueError(f"Formato de data inválido: {valor!r}")


def _dia_semana_iso(data_iso: str) -> str:
    return DIAS_SEMANA[_iso_para_date(data_iso).weekday()]


def _carregar_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validar_schema(dados: dict[str, Any]) -> None:
    """Valida o dicionário estruturado contra `schema_calendario.json`."""
    jsonschema.validate(instance=dados, schema=_carregar_schema())


def extrair_f57(texto: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Extrai estruturalmente períodos, feriados, pontos facultativos e eventos de F57 (2026.2)."""
    m_let = re.search(
        r"per[íi]odo letivo do (20\d{2}\.\d)\s+vai de\s+(\d{2}/\d{2}/\d{4})\s*\([^)]*\)\s*a\s*(\d{2}/\d{2}/\d{4})",
        texto,
        re.IGNORECASE,
    )
    m_aulas = re.search(
        r"per[íi]odo de aulas começa em\s+(\d{2}/\d{2}/\d{4})[^.\n]*?e termina em\s+(\d{2}/\d{2}/\d{4})",
        texto,
        re.IGNORECASE,
    )
    if not m_let or not m_aulas:
        raise ValueError("Não foi possível extrair período letivo ou de aulas de F57.")

    semestre = m_let.group(1)
    periodo_letivo = {"inicio": _br_para_iso(m_let.group(2)), "fim": _br_para_iso(m_let.group(3))}
    periodo_aulas = {"inicio": _br_para_iso(m_aulas.group(1)), "fim": _br_para_iso(m_aulas.group(2))}

    feriados: list[dict[str, Any]] = []
    pontos_facultativos: list[dict[str, Any]] = []
    eventos: list[dict[str, Any]] = []
    observacoes: list[str] = []

    secao = ""
    for linha_bruta in texto.splitlines():
        linha = linha_bruta.strip()
        if linha.startswith("## "):
            secao = linha[3:].strip().lower()
            continue
        if not linha.startswith("- "):
            continue
        item = linha[2:].strip()

        if "feriados" in secao:
            m = re.search(r"\((\d{2}/\d{2}/\d{4})\)\s*,\s*([^:]+):\s*(.+)$", item)
            if m:
                data_iso = _br_para_iso(m.group(1))
                desc = m.group(3).strip().rstrip(".")
                nome = re.sub(r"^feriado\s+(?:da|de|do)\s+", "", desc, flags=re.I)
                nome = re.sub(r"\s*\([^)]*\)\s*$", "", nome).strip()
                abrangencia = "distrital" if "distrital" in desc.lower() else "nacional"
                feriados.append(
                    {
                        "data": data_iso,
                        "dia_semana": _dia_semana_iso(data_iso),
                        "nome": nome or desc,
                        "abrangencia": abrangencia,
                        "observacao": desc,
                    }
                )
        elif "pontos facultativos" in secao:
            m = re.search(r"\((\d{2}/\d{2}/\d{4})\)\s*,\s*([^:]+):\s*(.+)$", item)
            if m:
                data_iso = _br_para_iso(m.group(1))
                desc = m.group(3).strip()
                m_hora = re.search(r"(ap[oó]s\s+as\s+\d{1,2}h|at[eé]\s+[àa]s?\s+\d{1,2}h)", desc, re.I)
                if "dia do servidor" in desc.lower():
                    nome = "Dia do Servidor"
                elif m.group(1).startswith("24/12"):
                    nome = "Véspera de Natal (ponto facultativo)"
                elif m.group(1).startswith("31/12"):
                    nome = "Véspera de Ano Novo (ponto facultativo)"
                else:
                    nome = desc.split(".")[0].strip()
                pontos_facultativos.append(
                    {
                        "data": data_iso,
                        "dia_semana": _dia_semana_iso(data_iso),
                        "nome": nome,
                        "horario": m_hora.group(1) if m_hora else None,
                        "observacao": desc,
                    }
                )
            elif "ponto facultativo não é feriado" in item.lower():
                observacoes.append(item)
        elif "semana universit" in secao:
            m_interv = re.search(r"\((\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})\)\s*:\s*(.+)$", item)
            if m_interv:
                eventos.append(
                    {
                        "titulo": m_interv.group(3).split(".")[0].strip(),
                        "data": None,
                        "inicio": _br_para_iso(m_interv.group(1)),
                        "fim": _br_para_iso(m_interv.group(2)),
                        "observacao": m_interv.group(3).strip(),
                    }
                )
        elif "período letivo" in secao:
            if "marcos do período de aulas" in item.lower():
                for pct, dt_br in re.findall(r"(\d+%)\s+(?:de realização\s+)?em\s+(\d{2}/\d{2}/\d{4})", item, re.I):
                    eventos.append(
                        {
                            "titulo": f"{pct} de realização das aulas ({semestre})",
                            "data": _br_para_iso(dt_br),
                            "inicio": None,
                            "fim": None,
                            "observacao": item,
                        }
                    )
            elif "recesso" in item.lower() or "semana de provas" in item.lower():
                observacoes.append(item)
            elif "depois do último dia de aulas" in item.lower():
                observacoes.append(item)

    vigencia_meta = meta.get("vigencia") or periodo_letivo
    return {
        "semestre": semestre,
        "doc_id": meta["id"],
        "titulo": meta["titulo"],
        "orgao": meta["orgao"],
        "url": meta.get("url", ""),
        "pagina": 1,
        "vigencia": {
            "inicio": str(vigencia_meta["inicio"]),
            "fim": str(vigencia_meta["fim"]),
        },
        "periodo_letivo": periodo_letivo,
        "periodo_aulas": periodo_aulas,
        "feriados": feriados,
        "pontos_facultativos": pontos_facultativos,
        "eventos": eventos,
        "recesso": [],
        "semana_provas": [],
        "observacoes": observacoes,
    }


def extrair_f58(texto: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Extrai estruturalmente o calendário especial de verão 2027 (2026.4) a partir de F58.txt."""
    m_sem = re.search(r"\b(20\d{2}\.\d)\b", texto) or re.search(r"\b(20\d{2}\.\d)\b", meta.get("titulo", ""))
    m_let = re.search(r"Per[íi]odo letivo:\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})", texto, re.I | re.S)
    m_inicio = re.search(r"(\d{2}/\d{2}/\d{4})\s*-\s*Primeiro dia de aulas", texto, re.I)
    m_fim = re.search(r"(\d{2}/\d{2}/\d{4})\s*-\s*[ÚU]ltimo dia de aulas", texto, re.I)
    if not m_sem or not m_let or not m_inicio or not m_fim:
        raise ValueError("Não foi possível extrair semestre ou períodos de F58.")

    periodo_letivo = {"inicio": _br_para_iso(m_let.group(1)), "fim": _br_para_iso(m_let.group(2))}
    periodo_aulas = {"inicio": _br_para_iso(m_inicio.group(1)), "fim": _br_para_iso(m_fim.group(1))}

    feriados: list[dict[str, Any]] = []
    pontos_facultativos: list[dict[str, Any]] = []
    eventos: list[dict[str, Any]] = []

    for linha_bruta in texto.splitlines():
        linha = linha_bruta.strip()
        m_fp = re.match(r"^(\d{2}/\d{2}/\d{4})\s*-\s*([^\n(]+?)\s*\(([^)]+)\)\s*$", linha)
        if m_fp:
            data_iso = _br_para_iso(m_fp.group(1))
            nome = m_fp.group(2).strip()
            tipo = m_fp.group(3).strip()
            tipo_low = tipo.lower()
            if tipo_low == "feriado":
                feriados.append(
                    {
                        "data": data_iso,
                        "dia_semana": _dia_semana_iso(data_iso),
                        "nome": nome,
                        "abrangencia": "nacional",
                        "observacao": f"{nome} ({tipo}).",
                    }
                )
            elif "ponto facultativo" in tipo_low:
                m_hora = re.search(r"(ap[oó]s\s+as\s+\d{1,2}h|at[eé]\s+[àa]s?\s+\d{1,2}h)", tipo, re.I)
                pontos_facultativos.append(
                    {
                        "data": data_iso,
                        "dia_semana": _dia_semana_iso(data_iso),
                        "nome": nome,
                        "horario": m_hora.group(1) if m_hora else None,
                        "observacao": f"{nome} ({tipo}).",
                    }
                )

    vigencia_meta = meta.get("vigencia") or periodo_letivo
    return {
        "semestre": m_sem.group(1),
        "doc_id": meta["id"],
        "titulo": meta["titulo"],
        "orgao": meta["orgao"],
        "url": meta.get("url", ""),
        "pagina": 1,
        "vigencia": {
            "inicio": str(vigencia_meta["inicio"]),
            "fim": str(vigencia_meta["fim"]),
        },
        "periodo_letivo": periodo_letivo,
        "periodo_aulas": periodo_aulas,
        "feriados": feriados,
        "pontos_facultativos": pontos_facultativos,
        "eventos": eventos,
        "recesso": [],
        "semana_provas": [],
        "observacoes": [
            "Calendário especial de verão 2027 (2026.4) — turmas de férias (DEG/SAA UnB).",
        ],
    }


def verificar_vigencia_catalogo(
    referencia: date | str,
    documentos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Audita a vigência de todos os documentos `tipo: calendario` frente a uma data de referência."""
    ref = _parse_data_flexivel(referencia)
    ref_iso = ref.isoformat()
    relatorio: list[dict[str, Any]] = []
    for doc in documentos:
        vig = doc.get("vigencia")
        if not vig or not vig.get("inicio") or not vig.get("fim"):
            status = "sem_vigencia"
        elif ref_iso < vig["inicio"]:
            status = "futuro"
        elif ref_iso > vig["fim"]:
            status = "vencido"
        else:
            status = "vigente"
        relatorio.append(
            {
                "id": doc["id"],
                "titulo": doc["titulo"],
                "vigencia": vig,
                "status": status,
                "utilizavel": status == "vigente",
            }
        )
    return relatorio


class CalendarioAcademico:
    """Modelo estruturado e deterministicamente consultável do calendário acadêmico da UnB."""

    def __init__(self, dados: dict[str, Any]):
        validar_schema(dados)
        self.dados = dados
        self.semestres: list[dict[str, Any]] = dados["semestres"]
        self.documentos_calendario: list[dict[str, Any]] = dados["documentos_calendario"]

    @classmethod
    def construir_do_catalogo(
        cls,
        catalogo_path: Path | None = None,
        dados_dir: Path | None = None,
    ) -> CalendarioAcademico:
        """Lê `catalogo.yaml`, `F57` e `F58`, valida o schema e instancia `CalendarioAcademico`."""
        cat_path = Path(catalogo_path or config.CATALOGO)
        d_dir = Path(dados_dir or config.DADOS)
        cat = yaml.safe_load(cat_path.read_text(encoding="utf-8"))
        docs = cat.get("documentos", [])
        docs_cal = [d for d in docs if d.get("tipo") == "calendario"]
        por_id = {d["id"]: d for d in docs_cal}

        semestres: list[dict[str, Any]] = []
        if "F57" in por_id:
            meta_f57 = por_id["F57"]
            arq_f57 = d_dir / meta_f57["arquivo"]
            semestres.append(extrair_f57(arq_f57.read_text(encoding="utf-8"), meta_f57))

        if "F58" in por_id:
            meta_f58 = por_id["F58"]
            arq_f58 = d_dir / "texto" / "F58.txt"
            semestres.append(extrair_f58(arq_f58.read_text(encoding="utf-8"), meta_f58))

        documentos_norm = [
            {
                "id": d["id"],
                "titulo": d["titulo"],
                "orgao": d["orgao"],
                "url": d.get("url", ""),
                "arquivo": str(d.get("arquivo", "")),
                "data": str(d.get("data", "")),
                "vigencia": (
                    {
                        "inicio": str(d["vigencia"]["inicio"]),
                        "fim": str(d["vigencia"]["fim"]),
                    }
                    if d.get("vigencia")
                    else None
                ),
            }
            for d in docs_cal
        ]

        payload = {
            "versao": "1.0",
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "semestres": semestres,
            "documentos_calendario": documentos_norm,
        }
        return cls(payload)

    def salvar_json(self, caminho: Path | None = None) -> Path:
        """Valida e persiste o JSON estruturado em disco."""
        destino = Path(caminho or config.CALENDARIO_JSON)
        destino.parent.mkdir(parents=True, exist_ok=True)
        validar_schema(self.dados)
        destino.write_text(
            json.dumps(self.dados, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destino

    def semestres_vigentes(self, data_ref: date | str) -> list[dict[str, Any]]:
        """Retorna apenas os semestres cuja vigência cobre estritamente `data_ref`."""
        d_iso = _parse_data_flexivel(data_ref).isoformat()
        return [
            s
            for s in self.semestres
            if s["vigencia"]["inicio"] <= d_iso <= s["vigencia"]["fim"]
        ]

    def _buscar_eventos_exatos(
        self,
        data_iso: str,
        vigentes: list[dict[str, Any]],
    ) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[tuple[dict[str, Any], dict[str, Any]]]]:
        """Busca feriados/pontos facultativos nos semestres vigentes e notas explícitas de fim de ano em F57 durante a janela de F58."""
        candidatos = list(vigentes)
        vig_ids = {s["doc_id"] for s in vigentes}
        # Fim de dezembro (22/12 a 31/12/2026) está na vigência de F58 (Verão 2027), enquanto F57 registrou 24/12, 25/12 e 31/12.
        for s in self.semestres:
            if s["doc_id"] not in vig_ids and s["vigencia"]["fim"][:4] == data_iso[:4]:
                candidatos.append(s)

        feriados = [
            (s, f)
            for s in candidatos
            for f in s["feriados"]
            if f["data"] == data_iso
        ]
        facultativos = [
            (s, pf)
            for s in candidatos
            for pf in s["pontos_facultativos"]
            if pf["data"] == data_iso
        ]
        return feriados, facultativos

    def consultar_data(self, data_ref: date | str) -> dict[str, Any]:
        """Consulta determinística da situação acadêmica de uma data respeitando vigência."""
        d = _parse_data_flexivel(data_ref)
        d_iso = d.isoformat()
        d_br = d.strftime("%d/%m/%Y")
        dia_sem = DIAS_SEMANA[d.weekday()]

        vigentes = self.semestres_vigentes(d)
        auditoria_vigencia = verificar_vigencia_catalogo(d, self.documentos_calendario)

        if not vigentes:
            limites = ", ".join(
                f"{s['semestre']} ({_iso_para_br(s['vigencia']['inicio'])} a {_iso_para_br(s['vigencia']['fim'])})"
                for s in self.semestres
            )
            return {
                "data": d_iso,
                "data_br": d_br,
                "dia_semana": dia_sem,
                "vigente": False,
                "status": "sem_calendario_vigente",
                "tem_aula": None,
                "bloqueia_agenda": False,
                "semestre": None,
                "feriado": None,
                "ponto_facultativo": None,
                "eventos": [],
                "fontes": [],
                "auditoria_vigencia": auditoria_vigencia,
                "resumo": (
                    f"Não há calendário acadêmico vigente registrado no catálogo do RUmo para {d_br} ({dia_sem}). "
                    f"Calendários cadastrados com vigência verificada cobrem apenas: {limites}."
                ),
            }

        feriados_hit, facultativos_hit = self._buscar_eventos_exatos(d_iso, vigentes)
        eventos_dia = [
            {"semestre": s["semestre"], "doc_id": s["doc_id"], **ev}
            for s in vigentes
            for ev in s["eventos"]
            if ev.get("data") == d_iso
            or (ev.get("inicio") and ev.get("fim") and ev["inicio"] <= d_iso <= ev["fim"])
        ]

        # Se a data é feriado registrado dentro de um calendário vigente na UnB, tem precedência.
        if feriados_hit:
            sem_ev, feriado = feriados_hit[0]
            fora_aulas = not any(
                s["periodo_aulas"]["inicio"] <= d_iso <= s["periodo_aulas"]["fim"]
                for s in vigentes
            )
            fontes = _dedup_semestres([sem_ev] + vigentes)
            extra_aulas = (
                f" Além disso, a data está fora do período regular de aulas dos semestres vigentes."
                if fora_aulas
                else ""
            )
            return {
                "data": d_iso,
                "data_br": d_br,
                "dia_semana": dia_sem,
                "vigente": True,
                "status": "feriado",
                "tem_aula": False,
                "bloqueia_agenda": True,
                "semestre": vigentes[0]["semestre"],
                "feriado": feriado,
                "ponto_facultativo": None,
                "eventos": eventos_dia,
                "fontes": fontes,
                "auditoria_vigencia": auditoria_vigencia,
                "resumo": (
                    f"Não há aula nem expediente acadêmico em {d_br} ({dia_sem}): "
                    f"{feriado['nome']} (feriado {feriado['abrangencia']}).{extra_aulas}"
                ),
            }

        if d.weekday() == 6:
            return {
                "data": d_iso,
                "data_br": d_br,
                "dia_semana": dia_sem,
                "vigente": True,
                "status": "domingo",
                "tem_aula": False,
                "bloqueia_agenda": True,
                "semestre": vigentes[0]["semestre"],
                "feriado": None,
                "ponto_facultativo": None,
                "eventos": eventos_dia,
                "fontes": _dedup_semestres(vigentes),
                "auditoria_vigencia": auditoria_vigencia,
                "resumo": f"Não há aulas regulares em {d_br} ({dia_sem}).",
            }

        em_aula = [
            s
            for s in vigentes
            if s["periodo_aulas"]["inicio"] <= d_iso <= s["periodo_aulas"]["fim"]
        ]
        if not em_aula:
            s_vig = vigentes[0]
            pf_info = facultativos_hit[0][1] if facultativos_hit else None
            sem_anteriores = [s for s in self.semestres if s["periodo_aulas"]["fim"] < d_iso]
            partes_periodo: list[str] = []
            if sem_anteriores:
                ult = max(sem_anteriores, key=lambda x: x["periodo_aulas"]["fim"])
                partes_periodo.append(
                    f"as aulas regulares de {ult['semestre']} encerraram em {_iso_para_br(ult['periodo_aulas']['fim'])}"
                )
            if d_iso < s_vig["periodo_aulas"]["inicio"]:
                partes_periodo.append(
                    f"as aulas de {s_vig['semestre']} só iniciam em {_iso_para_br(s_vig['periodo_aulas']['inicio'])}"
                )
            elif d_iso > s_vig["periodo_aulas"]["fim"]:
                partes_periodo.append(
                    f"as aulas de {s_vig['semestre']} encerraram em {_iso_para_br(s_vig['periodo_aulas']['fim'])}"
                )
            detalhe_pf = ""
            if pf_info:
                horario_txt = f" ({pf_info['horario']})" if pf_info.get("horario") else ""
                detalhe_pf = f" Além disso, trata-se de ponto facultativo de {pf_info['nome']}{horario_txt}."
            fontes_raw = vigentes + ([facultativos_hit[0][0]] if facultativos_hit else [])
            if sem_anteriores:
                fontes_raw.append(max(sem_anteriores, key=lambda x: x["periodo_aulas"]["fim"]))
            return {
                "data": d_iso,
                "data_br": d_br,
                "dia_semana": dia_sem,
                "vigente": True,
                "status": "fora_periodo_aulas",
                "tem_aula": False,
                "bloqueia_agenda": True,
                "semestre": s_vig["semestre"],
                "feriado": None,
                "ponto_facultativo": pf_info,
                "eventos": eventos_dia,
                "fontes": _dedup_semestres(fontes_raw),
                "auditoria_vigencia": auditoria_vigencia,
                "resumo": (
                    f"Não há aulas regulares em {d_br} ({dia_sem}): a data está fora do período de aulas "
                    f"({'; '.join(partes_periodo)}).{detalhe_pf}"
                ),
            }

        s_ativo = em_aula[0]
        if facultativos_hit:
            sem_pf, pf = facultativos_hit[0]
            horario_txt = f" ({pf['horario']})" if pf.get("horario") else ""
            return {
                "data": d_iso,
                "data_br": d_br,
                "dia_semana": dia_sem,
                "vigente": True,
                "status": "ponto_facultativo",
                "tem_aula": None,
                "bloqueia_agenda": False,
                "semestre": s_ativo["semestre"],
                "feriado": None,
                "ponto_facultativo": pf,
                "eventos": eventos_dia,
                "fontes": _dedup_semestres([s_ativo, sem_pf]),
                "auditoria_vigencia": auditoria_vigencia,
                "resumo": (
                    f"{d_br} ({dia_sem}) NÃO é feriado, mas ponto facultativo ({pf['nome']}{horario_txt}) "
                    f"dentro do período de aulas de {s_ativo['semestre']} "
                    f"({_iso_para_br(s_ativo['periodo_aulas']['inicio'])} a {_iso_para_br(s_ativo['periodo_aulas']['fim'])}). "
                    f"A confirmação de aulas ou expediente depende de deliberação da unidade/docente."
                ),
            }

        aviso_eventos = ""
        if eventos_dia:
            nomes_ev = "; ".join(e["titulo"] for e in eventos_dia)
            aviso_eventos = f" Observação do calendário: {nomes_ev}."

        return {
            "data": d_iso,
            "data_br": d_br,
            "dia_semana": dia_sem,
            "vigente": True,
            "status": "dia_letivo_regular",
            "tem_aula": True,
            "bloqueia_agenda": False,
            "semestre": s_ativo["semestre"],
            "feriado": None,
            "ponto_facultativo": None,
            "eventos": eventos_dia,
            "fontes": _dedup_semestres([s_ativo]),
            "auditoria_vigencia": auditoria_vigencia,
            "resumo": (
                f"{d_br} ({dia_sem}) é dia letivo regular no período de aulas de {s_ativo['semestre']} "
                f"({_iso_para_br(s_ativo['periodo_aulas']['inicio'])} a {_iso_para_br(s_ativo['periodo_aulas']['fim'])}), "
                f"sem feriado ou ponto facultativo registrado no calendário.{aviso_eventos}"
            ),
        }

    def filtrar_aulas_do_dia(
        self,
        data_ref: date | str,
        aulas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Filtra compromissos da agenda (#64) bloqueando aulas em feriados, domingos e fora do período de aulas."""
        consulta = self.consultar_data(data_ref)
        lista = list(aulas)
        if consulta["bloqueia_agenda"]:
            return {
                "data": consulta["data"],
                "data_br": consulta["data_br"],
                "dia_semana": consulta["dia_semana"],
                "status": consulta["status"],
                "tem_aula": False,
                "bloqueia_agenda": True,
                "aulas_ativas": [],
                "aulas_canceladas": lista,
                "motivo": consulta["resumo"],
                "consulta": consulta,
            }
        return {
            "data": consulta["data"],
            "data_br": consulta["data_br"],
            "dia_semana": consulta["dia_semana"],
            "status": consulta["status"],
            "tem_aula": consulta["tem_aula"],
            "bloqueia_agenda": False,
            "aulas_ativas": lista,
            "aulas_canceladas": [],
            "motivo": consulta["resumo"],
            "consulta": consulta,
        }

    def eh_pergunta_calendario(self, pergunta: str) -> bool:
        """Retorna True quando a pergunta trata de calendário acadêmico, feriados, recesso ou aulas em data."""
        if not pergunta or _RE_EXCLUSAO_GRADE.search(pergunta):
            return False
        return bool(_RE_TERMOS_CALENDARIO.search(pergunta))

    def _extrair_data_pergunta(
        self,
        pergunta: str,
        data_referencia: date | None = None,
    ) -> date | None:
        ref = data_referencia or date.today()
        m_rel_amanha = re.search(r"\bamanh[ãa]\b", pergunta, re.I)
        m_rel_hoje = re.search(r"\bhoje\b", pergunta, re.I)

        m_iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", pergunta)
        if m_iso:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))

        m_br_ano = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", pergunta)
        if m_br_ano:
            return date(int(m_br_ano.group(3)), int(m_br_ano.group(2)), int(m_br_ano.group(1)))

        m_br_curto = re.search(r"\b(\d{1,2})/(\d{1,2})\b", pergunta)
        if m_br_curto:
            dia, mes = int(m_br_curto.group(1)), int(m_br_curto.group(2))
            ano = _inferir_ano(dia, mes, ref, self.semestres)
            return date(ano, mes, dia)

        m_ext = re.search(
            r"\b(?:dia\s+)?(\d{1,2})\s+de\s+([a-zçãõáéíóú]+)(?:\s+de\s+(20\d{2}))?\b",
            pergunta,
            re.I,
        )
        if m_ext:
            mes_str = m_ext.group(2).lower()
            if mes_str in _MESES:
                dia = int(m_ext.group(1))
                mes = _MESES[mes_str]
                ano = int(m_ext.group(3)) if m_ext.group(3) else _inferir_ano(dia, mes, ref, self.semestres)
                return date(ano, mes, dia)

        if data_referencia is not None:
            if m_rel_amanha:
                return date.fromordinal(data_referencia.toordinal() + 1)
            if m_rel_hoje:
                return data_referencia
        return None

    def consultar_pergunta(
        self,
        pergunta: str,
        data_referencia: date | None = None,
    ) -> dict[str, Any] | None:
        """Responde deterministicamente perguntas sobre datas, feriados, pontos facultativos, recesso ou períodos."""
        if not self.eh_pergunta_calendario(pergunta):
            return None

        trechos_base: list[dict[str, Any]] = []
        data_alvo = self._extrair_data_pergunta(pergunta, data_referencia=data_referencia)

        if data_alvo is not None:
            res = self.consultar_data(data_alvo)
            fontes_meta = res["fontes"] or [_semestre_resumo_fonte(s) for s in self.semestres]
            trechos_base = _montar_trechos_calendario(fontes_meta, res["resumo"])
            resposta = f"{res['resumo']} [1]"
            return {
                "resposta": resposta,
                "trechos": trechos_base,
                "fontes_citadas": [
                    {
                        "n": 1,
                        "doc_id": trechos_base[0]["doc_id"],
                        "titulo": trechos_base[0]["titulo"],
                        "pagina": trechos_base[0]["pagina"],
                        "secao": trechos_base[0]["secao"],
                        "url": trechos_base[0]["url"],
                    }
                ],
                "consulta_data": res,
            }

        p_low = pergunta.lower()
        sem = _selecionar_semestre_pergunta(p_low, self.semestres)

        if "recesso" in p_low or "semana de provas" in p_low or "provas" in p_low:
            obs = " ".join(sem["observacoes"]) or (
                "Não há datas específicas de recesso nem de semana de provas listadas no documento-base."
            )
            texto_resp = (
                f"No calendário acadêmico de {sem['semestre']} da UnB, {obs} "
                f"O período letivo vai de {_iso_para_br(sem['periodo_letivo']['inicio'])} a "
                f"{_iso_para_br(sem['periodo_letivo']['fim'])}, com aulas regulares de "
                f"{_iso_para_br(sem['periodo_aulas']['inicio'])} a {_iso_para_br(sem['periodo_aulas']['fim'])}."
            )
            trechos_base = _montar_trechos_calendario([_semestre_resumo_fonte(sem)], texto_resp)
            return _empacotar_resposta(f"{texto_resp} [1]", trechos_base)

        if "feriado" in p_low or "ponto facultativo" in p_low or "pontos facultativos" in p_low:
            fer_str = ", ".join(
                f"{_iso_para_br(f['data'])} ({f['nome']})" for f in sem["feriados"]
            ) or "nenhum listado"
            pf_str = ", ".join(
                f"{_iso_para_br(pf['data'])} ({pf['nome']}"
                + (f" — {pf['horario']}" if pf.get("horario") else "")
                + ")"
                for pf in sem["pontos_facultativos"]
            ) or "nenhum listado"
            texto_resp = (
                f"No calendário acadêmico de {sem['semestre']} ({_iso_para_br(sem['vigencia']['inicio'])} a "
                f"{_iso_para_br(sem['vigencia']['fim'])}), os feriados registrados são: {fer_str}. "
                f"Os pontos facultativos registrados são: {pf_str}."
            )
            trechos_base = _montar_trechos_calendario([_semestre_resumo_fonte(sem)], texto_resp)
            return _empacotar_resposta(f"{texto_resp} [1]", trechos_base)

        if any(t in p_low for t in ("início", "inicio", "término", "termino", "começa", "comeca", "termina", "período", "periodo")):
            texto_resp = (
                f"Em {sem['semestre']}, o período letivo da UnB ocorre de "
                f"{_iso_para_br(sem['periodo_letivo']['inicio'])} a {_iso_para_br(sem['periodo_letivo']['fim'])}, "
                f"e as aulas acontecem de {_iso_para_br(sem['periodo_aulas']['inicio'])} a "
                f"{_iso_para_br(sem['periodo_aulas']['fim'])}."
            )
            trechos_base = _montar_trechos_calendario([_semestre_resumo_fonte(sem)], texto_resp)
            return _empacotar_resposta(f"{texto_resp} [1]", trechos_base)

        if "semana universit" in p_low:
            evs = [e for e in sem["eventos"] if "semana universit" in e["titulo"].lower()]
            if evs:
                ev = evs[0]
                texto_resp = (
                    f"No calendário {sem['semestre']}, a {ev['titulo']} ocorre de "
                    f"{_iso_para_br(ev['inicio'])} a {_iso_para_br(ev['fim'])}. {ev['observacao']}"
                )
                trechos_base = _montar_trechos_calendario([_semestre_resumo_fonte(sem)], texto_resp)
                return _empacotar_resposta(f"{texto_resp} [1]", trechos_base)

        return None


def _inferir_ano(dia: int, mes: int, ref: date, semestres: list[dict[str, Any]]) -> int:
    candidatos = sorted({int(s["vigencia"]["inicio"][:4]) for s in semestres} | {int(s["vigencia"]["fim"][:4]) for s in semestres})
    for ano in candidatos:
        try:
            d_cand = date(ano, mes, dia).isoformat()
        except ValueError:
            continue
        if any(s["vigencia"]["inicio"] <= d_cand <= s["vigencia"]["fim"] for s in semestres):
            return ano
    return ref.year


def _selecionar_semestre_pergunta(p_low: str, semestres: list[dict[str, Any]]) -> dict[str, Any]:
    for s in semestres:
        if s["semestre"] in p_low:
            return s
    if "verão" in p_low or "verao" in p_low or "2027" in p_low:
        for s in semestres:
            if s["semestre"] == "2026.4":
                return s
    return semestres[0]


def _semestre_resumo_fonte(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": s["doc_id"],
        "titulo": s["titulo"],
        "orgao": s["orgao"],
        "url": s["url"],
        "pagina": s.get("pagina", 1),
        "semestre": s["semestre"],
        "vigencia": s["vigencia"],
    }


def _dedup_semestres(semestres: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vistos: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in semestres:
        did = s["doc_id"]
        if did in vistos:
            continue
        vistos.add(did)
        out.append(_semestre_resumo_fonte(s))
    return out


def _montar_trechos_calendario(fontes: list[dict[str, Any]], resumo_texto: str) -> list[dict[str, Any]]:
    trechos: list[dict[str, Any]] = []
    for i, f in enumerate(fontes):
        vig = f.get("vigencia") or {}
        vig_txt = (
            f"Vigência: {_iso_para_br(vig['inicio'])} a {_iso_para_br(vig['fim'])}. "
            if vig.get("inicio") and vig.get("fim")
            else ""
        )
        trechos.append(
            {
                "chunk_id": f"calendario-{f['doc_id']}-{i + 1}",
                "doc_id": f["doc_id"],
                "titulo": f["titulo"],
                "orgao": f["orgao"],
                "pagina": f.get("pagina", 1),
                "secao": f"Calendário {f.get('semestre', '')}".strip(),
                "url": f.get("url", ""),
                "texto": f"{vig_txt}{resumo_texto}",
                "similaridade": 1.0,
            }
        )
    return trechos


def _empacotar_resposta(resposta: str, trechos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resposta": resposta,
        "trechos": trechos,
        "fontes_citadas": [
            {
                "n": 1,
                "doc_id": trechos[0]["doc_id"],
                "titulo": trechos[0]["titulo"],
                "pagina": trechos[0]["pagina"],
                "secao": trechos[0]["secao"],
                "url": trechos[0]["url"],
            }
        ],
    }


def limpar_cache() -> None:
    """Limpa o cache em memória do calendário estruturado (útil em testes)."""
    _CACHE.clear()


def carregar_calendario(
    caminho: Path | None = None,
    reconstruir_se_ausente: bool = True,
) -> CalendarioAcademico:
    """Carrega o `CalendarioAcademico` do JSON estruturado (ou constrói do catálogo se ausente)."""
    alvo = Path(caminho or config.CALENDARIO_JSON)
    if not alvo.exists():
        if not reconstruir_se_ausente:
            raise FileNotFoundError(f"Calendário estruturado não encontrado em {alvo}")
        cal = CalendarioAcademico.construir_do_catalogo()
        cal.salvar_json(alvo)
        mtime = alvo.stat().st_mtime
        _CACHE[(str(alvo.resolve()), mtime)] = cal
        return cal

    chave = (str(alvo.resolve()), alvo.stat().st_mtime)
    if chave in _CACHE:
        return _CACHE[chave]

    dados = json.loads(alvo.read_text(encoding="utf-8"))
    cal = CalendarioAcademico(dados)
    _CACHE[chave] = cal
    return cal
