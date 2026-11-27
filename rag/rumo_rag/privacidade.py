"""Política de privacidade, sanitização e extração efêmera para documentos pessoais (#59, LGPD).

Mantém apenas quatro campos operacionais do comprovante/atestado de matrícula
(`codigo`, `turma`, `horario`, `sala`), descarta dados sensíveis em memória e
impede que trechos do perfil sejam enviados a LLMs externos ou gravados em disco.
"""

from __future__ import annotations

import io
import re
from typing import Any
import unicodedata

CAMPOS_PERMITIDOS_DOCUMENTO: tuple[str, ...] = ("codigo", "turma", "horario", "sala")

CAMPOS_PROIBIDOS_PII: frozenset[str] = frozenset({
    "nome",
    "nome_completo",
    "estudante",
    "aluno",
    "cpf",
    "rg",
    "matricula",
    "registro_academico",
    "email",
    "telefone",
    "endereco",
    "notas",
    "mencao",
    "mencoes",
    "ira",
    "mp",
    "reprovacoes",
    "historico",
    "texto_bruto",
    "pdf",
    "arquivo",
})

MAX_BYTES_PDF: int = 5 * 1024 * 1024  # 5 MB

AVISO_PRIVACIDADE_UPLOAD: str = (
    "Antes de selecionar o arquivo: envie preferencialmente o Comprovante ou Atestado de "
    "Matrícula do SIGAA (e não o Histórico Escolar). Sempre que possível, a leitura ocorre "
    "no seu próprio navegador, sem enviar o PDF ao servidor. Caso o processamento ocorra em "
    "servidor, o arquivo é lido apenas em memória e descartado imediatamente — nada é "
    "gravado em disco ou banco. Extraímos somente quatro campos (código da disciplina, turma, "
    "horário e sala) e descartamos nome, CPF, registro acadêmico, notas e reprovações. "
    "Nenhum trecho do documento é enviado a LLM externo (como OpenRouter), e o perfil "
    "derivado fica salvo apenas no navegador."
)

MENSAGEM_RECUSA_HISTORICO: str = (
    "Histórico escolar não é aceito nesta etapa porque não informa horário nem sala das turmas "
    "e concentra dados pessoais sensíveis (notas, menções e reprovações). Envie o Comprovante "
    "ou Atestado de Matrícula do SIGAA, do qual mantemos apenas código da disciplina, turma, "
    "horário e sala."
)

MENSAGEM_SEM_DISCIPLINAS: str = (
    "Não foi possível identificar disciplinas com código e horário do SIGAA no documento. "
    "Verifique se o PDF é o Comprovante ou Atestado de Matrícula com texto selecionável "
    "(PDFs escaneados como imagem ainda não são suportados)."
)

_DIAS_SIGAA: dict[str, str] = {
    "2": "segunda-feira",
    "3": "terça-feira",
    "4": "quarta-feira",
    "5": "quinta-feira",
    "6": "sexta-feira",
    "7": "sábado",
}
_PRIORIDADE_DIA: dict[str, int] = {d: i for i, d in enumerate(_DIAS_SIGAA.values())}
_ORDEM_TURNOS: dict[str, int] = {"M": 0, "T": 1, "N": 2}

_HORARIOS_SIGAA: dict[str, dict[int, tuple[str, str]]] = {
    "M": {
        1: ("08:00", "08:55"),
        2: ("08:55", "09:50"),
        3: ("10:00", "10:55"),
        4: ("10:55", "11:50"),
        5: ("12:00", "12:55"),
    },
    "T": {
        1: ("12:55", "13:50"),
        2: ("14:00", "14:55"),
        3: ("14:55", "15:50"),
        4: ("16:00", "16:55"),
        5: ("16:55", "17:50"),
        6: ("18:00", "18:55"),
    },
    "N": {
        1: ("19:00", "19:50"),
        2: ("19:50", "20:40"),
        3: ("20:50", "21:40"),
        4: ("21:40", "22:30"),
    },
}
_FAIXA_PARA_SIGAA: dict[tuple[str, str], tuple[str, int]] = {
    faixa: (turno, slot)
    for turno, mapa in _HORARIOS_SIGAA.items()
    for slot, faixa in mapa.items()
}

_BLOCO_SIGAA_RE = re.compile(r"\b([2-7]+)([MTN])([1-6]+)\b")
_CODIGO_DISCIPLINA_RE = re.compile(r"^[A-Z]{2,6}\d{3,4}[A-Z]?$")
_CODIGO_NO_TEXTO_RE = re.compile(r"\b([A-Z]{2,4}\d{3,4}[A-Z]?)\b")
_INICIO_TURMA_RE = re.compile(r"^[A-Z]{2,4}\d{3,4}[A-Z]?\s*-")
_LINHA_GRADE_RE = re.compile(r"^(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s+(.+)$")
_CABECALHO_GRADE_RE = re.compile(r"\bseg\b.*\bter\b.*\bqua\b.*\bqui\b.*\bsex\b")
_LINHA_TURMA_SELECIONADA_RE = re.compile(
    r"^([A-Z]{2,4}\d{3,4}[A-Z]?)\s*-\s*.*\bTurma\s+([A-Z0-9]{1,4})\s+(.+?)\s+"
    r"(DEFERIDA|INDEFERIDA|MATRICULAD[OA]|AGUARDANDO\s+PROCESSAMENTO|"
    r"EXCLU[IÍ]DA|DESIST[EÊ]NCIA|CANCELADA|TRANCADA|PR[EÉ]-?MATRICULAD[OA])\s*$",
    re.IGNORECASE,
)
_SITUACOES_ATIVAS: frozenset[str] = frozenset({"DEFERIDA", "MATRICULADO", "MATRICULADA"})

_PII_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_PII_REGISTRO_UNB_RE = re.compile(r"\b\d{2}/\d{7}\b|\b\d{9}\b")
_PII_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.IGNORECASE)
_PII_ROTULOS_RE = re.compile(
    r"\b(?:cpf|rg|ira|menc[aã]o|men[cç][oõ]es|reprova[cç][aã]o|reprova[cç][oõ]es"
    r"|nome\s+completo|hist[oó]rico\s+escolar|nota\s+final|matr[ií]cula\s*:)\b",
    re.IGNORECASE,
)

_MENCIONA_HISTORICO_STATUS_RE = re.compile(r"\b(?:SS|MS|MM|MI|II|SR)\b")
_LIMITE_CAMPOS = {
    "codigo": 16,
    "turma": 20,
    "horario": 80,
    "sala": 60,
    "dia": 20,
    "disciplina": 120,
    "nome": 120,
}


def _normalizar_small_caps(texto: str) -> str:
    """Recompõe palavras em caixa alta separadas após a inicial (ex.: ``T URMAS`` -> ``TURMAS``)."""
    return re.sub(r"\b([A-ZÀ-ÖØ-Ý]) ([A-ZÀ-ÖØ-Ý]{2,})\b", r"\1\2", texto or "")


def _normalizar_ascii(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto or "")
    sem_acentos = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", sem_acentos).strip().lower()


def _limpar_espacos(valor: Any, limite: int = 80) -> str:
    texto = re.sub(r"\s+", " ", str(valor or "")).strip()
    return texto[:limite]


def politica_privacidade_documento() -> dict[str, Any]:
    """Retorna o contrato oficial de privacidade para exibição antes do seletor."""
    return {
        "versao": "1.0",
        "epico": "#59",
        "aviso_antes_upload": AVISO_PRIVACIDADE_UPLOAD,
        "campos_permitidos": list(CAMPOS_PERMITIDOS_DOCUMENTO),
        "campos_descartados": sorted(CAMPOS_PROIBIDOS_PII),
        "documentos_aceitos": [
            "comprovante_solicitacao_matricula",
            "comprovante_matricula",
            "atestado_matricula",
        ],
        "documentos_recusados": ["historico_escolar"],
        "mensagem_recusa_historico": MENSAGEM_RECUSA_HISTORICO,
        "processamento_preferencial": "navegador",
        "fallback_servidor": "memoria_efemera_sem_disco",
        "armazenamento_servidor": False,
        "armazenamento_perfil": "navegador_localStorage",
        "envio_llm_externo": False,
        "tamanho_maximo_bytes": MAX_BYTES_PDF,
    }


def contem_pii_proibido(texto: str) -> bool:
    """Detecta indícios de CPF, número de registro estudantil, e-mail ou rótulos sensíveis."""
    if not texto:
        return False
    bruto = str(texto)
    norm = _normalizar_ascii(bruto)
    return bool(
        _PII_CPF_RE.search(bruto)
        or _PII_REGISTRO_UNB_RE.search(bruto)
        or _PII_EMAIL_RE.search(bruto)
        or _PII_ROTULOS_RE.search(norm)
    )


def _mapear_chaves_normalizadas(bruto: dict[str, Any]) -> dict[str, Any]:
    return {_normalizar_ascii(str(k)): v for k, v in bruto.items()}


def sanitizar_registro_disciplina(registro: dict[str, Any]) -> dict[str, str] | None:
    """Mantém exclusivamente os quatro campos permitidos e bloqueia qualquer PII."""
    if not isinstance(registro, dict):
        return None

    normalizado = _mapear_chaves_normalizadas(registro)
    codigo = _limpar_espacos(normalizado.get("codigo"), _LIMITE_CAMPOS["codigo"]).upper()
    if not codigo or contem_pii_proibido(codigo) or not _CODIGO_DISCIPLINA_RE.match(codigo):
        return None

    saida: dict[str, str] = {"codigo": codigo}
    for campo in ("turma", "horario", "sala"):
        valor = _limpar_espacos(normalizado.get(campo), _LIMITE_CAMPOS[campo])
        if contem_pii_proibido(valor):
            valor = ""
        saida[campo] = valor
    return saida


def sanitizar_perfil_contexto(perfil: Any) -> dict[str, Any] | None:
    """Aplica allowlist estrita ao ``contexto.perfil`` descartando dados pessoais."""
    if not isinstance(perfil, dict):
        return None

    limpo: dict[str, Any] = {}

    raw_disciplinas = perfil.get("disciplinas")
    if isinstance(raw_disciplinas, list):
        disciplinas: list[dict[str, str]] = []
        vistos: set[tuple[str, str, str, str]] = set()
        for item in raw_disciplinas:
            if not isinstance(item, dict):
                continue
            reg = sanitizar_registro_disciplina(item)
            if reg is None:
                continue
            chave = (reg["codigo"], reg["turma"], reg["horario"], reg["sala"])
            if chave not in vistos:
                vistos.add(chave)
                disciplinas.append(reg)
        if disciplinas:
            limpo["disciplinas"] = disciplinas

    raw_aulas = perfil.get("aulas")
    if isinstance(raw_aulas, list):
        aulas: list[dict[str, str]] = []
        chaves_aula = ("dia", "horario", "codigo", "turma", "disciplina", "nome", "sala")
        for item in raw_aulas:
            if not isinstance(item, dict):
                continue
            norm_item = _mapear_chaves_normalizadas(item)
            aula_limpa: dict[str, str] = {}
            for campo in chaves_aula:
                val = _limpar_espacos(norm_item.get(campo), _LIMITE_CAMPOS.get(campo, 80))
                if val and contem_pii_proibido(val):
                    val = ""
                if val:
                    aula_limpa[campo] = val
            if any(aula_limpa.get(c) for c in ("dia", "horario", "codigo", "disciplina", "nome")):
                aulas.append(aula_limpa)
        if aulas:
            limpo["aulas"] = aulas

    return limpo or None


def decodificar_horario_sigaa(codigo_horario: str) -> list[dict[str, str]]:
    """Traduz códigos de horário do SIGAA/UnB (ex.: ``35T23``, ``24M5 24T1``) para dia e faixa."""
    texto = str(codigo_horario or "").upper()
    if not texto.strip():
        return []

    por_dia: dict[str, list[tuple[str, str]]] = {}
    for match in _BLOCO_SIGAA_RE.finditer(texto):
        dias_cod, turno, slots_cod = match.groups()
        mapa_turno = _HORARIOS_SIGAA.get(turno)
        if not mapa_turno:
            continue
        slots = sorted({int(ch) for ch in slots_cod if int(ch) in mapa_turno})
        if not slots:
            continue

        faixas_consecutivas: list[list[int]] = []
        for s in slots:
            if not faixas_consecutivas or s != faixas_consecutivas[-1][-1] + 1:
                faixas_consecutivas.append([s])
            else:
                faixas_consecutivas[-1].append(s)

        for digito_dia in dict.fromkeys(dias_cod):
            dia_nome = _DIAS_SIGAA.get(digito_dia)
            if not dia_nome:
                continue
            lista_dia = por_dia.setdefault(dia_nome, [])
            for grupo in faixas_consecutivas:
                lista_dia.append((mapa_turno[grupo[0]][0], mapa_turno[grupo[-1]][1]))

    resultados: list[dict[str, str]] = []
    for dia_nome in sorted(por_dia, key=lambda d: _PRIORIDADE_DIA.get(d, 99)):
        mescladas: list[tuple[str, str]] = []
        for ini, fim in sorted(por_dia[dia_nome]):
            if not mescladas or ini > mescladas[-1][1]:
                mescladas.append((ini, fim))
            elif fim > mescladas[-1][1]:
                mescladas[-1] = (mescladas[-1][0], fim)
        for ini, fim in mescladas:
            resultados.append({"dia": dia_nome, "horario": f"{ini}-{fim}"})
    return resultados


def validar_pdf_em_memoria(conteudo: bytes) -> None:
    """Valida bytes de PDF em RAM antes da leitura (sem tocar o disco)."""
    if not isinstance(conteudo, (bytes, bytearray)):
        raise ValueError("O documento deve ser enviado em bytes.")
    tamanho = len(conteudo)
    if tamanho == 0:
        raise ValueError("O arquivo PDF está vazio.")
    if tamanho > MAX_BYTES_PDF:
        raise ValueError(
            f"O arquivo PDF excede o limite máximo permitido ({MAX_BYTES_PDF // (1024 * 1024)} MB)."
        )
    cabecalho = bytes(conteudo[:32]).lstrip()
    if not cabecalho.startswith(b"%PDF-"):
        raise ValueError("Arquivo inválido: cabeçalho PDF (%PDF-) ausente.")


def extrair_texto_pdf_em_memoria(conteudo: bytes) -> str:
    """Extrai texto diretamente de ``bytes`` em memória, sem gravação em disco."""
    validar_pdf_em_memoria(conteudo)
    raw = bytes(conteudo)
    partes: list[str] = []

    buf = io.BytesIO(raw)
    try:
        from pypdf import PdfReader

        leitor = PdfReader(buf)
        for pagina in leitor.pages:
            partes.append(pagina.extract_text() or "")
    finally:
        buf.close()

    texto = "\n".join(partes).strip()
    if texto:
        return texto

    buf_fallback = io.BytesIO(raw)
    try:
        import pdfplumber

        with pdfplumber.open(buf_fallback) as pdf:
            texto = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
    finally:
        buf_fallback.close()
    return texto


def detectar_tipo_documento(texto: str) -> str:
    """Classifica texto extraído em comprovante/atestado, histórico escolar ou desconhecido."""
    texto_sc = _normalizar_small_caps(texto or "")
    norm = _normalizar_ascii(texto_sc)
    if not norm:
        return "desconhecido"

    tem_horario_sigaa = bool(_BLOCO_SIGAA_RE.search(texto.upper()))
    tem_grade_sigaa = bool(_CABECALHO_GRADE_RE.search(norm) and _LINHA_GRADE_RE.search(texto))
    indica_comprovante = (
        "comprovante de solicitacao de matricula" in norm
        or "atestado de matricula" in norm
        or "comprovante de matricula" in norm
        or "turmas matriculadas" in norm
        or "turmas selecionadas" in norm
    )
    indica_historico = (
        "historico escolar" in norm
        or "indice de rendimento academico" in norm
        or (
            "componente curricular" in norm
            and bool(_MENCIONA_HISTORICO_STATUS_RE.search(texto))
            and not tem_horario_sigaa
            and not tem_grade_sigaa
        )
    )

    if indica_historico and not tem_horario_sigaa and not tem_grade_sigaa:
        return "historico_escolar"
    if indica_comprovante or tem_grade_sigaa or (tem_horario_sigaa and _CODIGO_NO_TEXTO_RE.search(texto.upper())):
        return "comprovante_matricula"
    if indica_historico:
        return "historico_escolar"
    return "desconhecido"


def _extrair_campos_segmento(segmento: str) -> tuple[str, str, str]:
    """Extrai (turma, horario_sigaa, sala) de um segmento de texto associado a um código."""
    horarios = _BLOCO_SIGAA_RE.findall(segmento.upper())
    if not horarios:
        return "", "", ""

    horario_fmt = " ".join("".join(h) for h in horarios)
    primeiro_match = _BLOCO_SIGAA_RE.search(segmento.upper())
    ultimo_match = None
    for m in _BLOCO_SIGAA_RE.finditer(segmento.upper()):
        ultimo_match = m

    antes = segmento[: primeiro_match.start()] if primeiro_match else ""
    depois = segmento[ultimo_match.end() :] if ultimo_match else ""

    turma = ""
    if m_turma := re.search(r"\bTurma[:\s]+([A-Z0-9]{1,4})\b", segmento, re.IGNORECASE):
        turma = m_turma.group(1).upper()
    elif m_turma_pos := re.search(r"\b(\d{2}|T\d{1,2}|[A-Z])\s*$", antes.strip()):
        turma = m_turma_pos.group(1).upper()

    sala_bruta = ""
    if m_sala := re.search(
        r"\b(?:Sala|Local|Audit[oó]rio)[:\s]+([A-Za-zÀ-ÿ0-9._/\- ]{1,40})",
        depois,
        re.IGNORECASE,
    ):
        sala_bruta = m_sala.group(1)
    else:
        trecho_sala = depois.strip(" -–|·:\t")
        trecho_sala = re.split(
            r"\b(?:Matriculad[oa]|Confirmad[oa]|Ativo|Deferid[oa]|Situa[cç][aã]o)\b",
            trecho_sala,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        sala_bruta = trecho_sala

    sala = _limpar_espacos(sala_bruta, _LIMITE_CAMPOS["sala"])
    if contem_pii_proibido(sala):
        sala = ""
    return turma, horario_fmt, sala


def _compactar_horarios_sigaa(ocorrencias: set[tuple[str, str, int]]) -> str:
    """Compacta ``(dia_digito, turno, slot)`` da grade visual em código SIGAA (ex.: ``35T45``)."""
    por_dia_turno: dict[tuple[str, str], list[int]] = {}
    for dia_dig, turno, slot in ocorrencias:
        por_dia_turno.setdefault((dia_dig, turno), []).append(slot)

    por_bloco: dict[tuple[str, tuple[int, ...]], set[str]] = {}
    for (dia_dig, turno), slots in por_dia_turno.items():
        runs: list[list[int]] = []
        for s in sorted(set(slots)):
            if not runs or s != runs[-1][-1] + 1:
                runs.append([s])
            else:
                runs[-1].append(s)
        for run in runs:
            por_bloco.setdefault((turno, tuple(run)), set()).add(dia_dig)

    ordenados = sorted(
        por_bloco.items(),
        key=lambda kv: (_ORDEM_TURNOS.get(kv[0][0], 9), kv[0][1][0], "".join(sorted(kv[1]))),
    )
    return " ".join(
        f"{''.join(sorted(dias))}{turno}{''.join(str(s) for s in run)}"
        for (turno, run), dias in ordenados
    )


def _extrair_grade_horarios_sigaa(texto: str) -> dict[str, str]:
    """Extrai o código SIGAA de cada disciplina a partir da grade semanal ``Horários Seg ... Sáb``."""
    ocorrencias: dict[str, set[tuple[str, str, int]]] = {}
    em_grade = False
    for linha in texto.splitlines():
        limpa = re.sub(r"\s+", " ", linha).strip()
        if not limpa:
            continue
        norm = _normalizar_ascii(_normalizar_small_caps(limpa))
        if not em_grade:
            if _CABECALHO_GRADE_RE.search(norm):
                em_grade = True
            continue
        m_linha = _LINHA_GRADE_RE.match(limpa)
        if not m_linha:
            if norm.startswith(("para verificar", "numero do documento", "codigo de verificacao")):
                break
            continue
        ini, fim, resto = m_linha.groups()
        chave_slot = _FAIXA_PARA_SIGAA.get((ini, fim))
        if chave_slot is None:
            continue
        turno, slot = chave_slot
        for idx_col, celula in enumerate(resto.split()[:6]):
            token = celula.strip().upper()
            if token == "---" or not _CODIGO_DISCIPLINA_RE.match(token):
                continue
            ocorrencias.setdefault(token, set()).add((str(idx_col + 2), turno, slot))
    return {cod: _compactar_horarios_sigaa(ocs) for cod, ocs in ocorrencias.items()}


def _extrair_turmas_selecionadas(texto: str) -> tuple[bool, list[dict[str, str]]]:
    """Extrai apenas as turmas deferidas/matriculadas da seção ``TURMAS SELECIONADAS``."""
    linhas_secao: list[str] = []
    na_secao = False
    cabecalho_visto = False

    for linha in texto.splitlines():
        limpa = re.sub(r"\s+", " ", linha).strip()
        if not limpa:
            continue
        norm_sc = _normalizar_ascii(_normalizar_small_caps(limpa))
        if not na_secao:
            if "turmas selecionadas" in norm_sc:
                na_secao = True
            elif "componente curricular" in norm_sc and "situacao" in norm_sc:
                na_secao = True
                cabecalho_visto = True
            continue
        if _CABECALHO_GRADE_RE.search(norm_sc) or _LINHA_GRADE_RE.match(limpa):
            break
        if norm_sc.startswith(("para verificar", "numero do documento", "codigo de verificacao")):
            break
        if not cabecalho_visto and "componente curricular" in norm_sc and "turma" in norm_sc:
            cabecalho_visto = True
            continue
        linhas_secao.append(limpa)

    if not na_secao:
        return False, []

    entradas: list[str] = []
    for linha in linhas_secao:
        if _INICIO_TURMA_RE.match(linha.upper()):
            entradas.append(linha)
        elif entradas:
            entradas[-1] = f"{entradas[-1]} {linha}".strip()

    ativas: list[dict[str, str]] = []
    for entrada in entradas:
        m = _LINHA_TURMA_SELECIONADA_RE.match(entrada)
        if not m:
            continue
        codigo, turma, sala, situacao = m.groups()
        if _normalizar_ascii(situacao).upper() not in _SITUACOES_ATIVAS:
            continue
        ativas.append({
            "codigo": codigo.upper(),
            "turma": turma.upper(),
            "sala": sala.strip(),
        })
    return True, ativas


def extrair_disciplinas_de_texto(texto: str) -> list[dict[str, str]]:
    """Extrai e sanitiza apenas (codigo, turma, horario, sala) a partir do texto em RAM."""
    if not texto:
        return []

    grade = _extrair_grade_horarios_sigaa(texto)
    tem_secao_turmas, turmas_ativas = _extrair_turmas_selecionadas(texto)
    if tem_secao_turmas or grade:
        registros_grade: list[dict[str, str]] = []
        vistos_grade: set[tuple[str, str, str, str]] = set()
        codigos_turmas: set[str] = set()

        for item in turmas_ativas:
            cod = item["codigo"]
            codigos_turmas.add(cod)
            reg = sanitizar_registro_disciplina({
                "codigo": cod,
                "turma": item["turma"],
                "horario": grade.get(cod, ""),
                "sala": item["sala"],
            })
            if reg is None:
                continue
            chave = (reg["codigo"], reg["turma"], reg["horario"], reg["sala"])
            if chave not in vistos_grade:
                vistos_grade.add(chave)
                registros_grade.append(reg)

        for cod, horario_cod in grade.items():
            if cod in codigos_turmas:
                continue
            reg = sanitizar_registro_disciplina({
                "codigo": cod,
                "turma": "",
                "horario": horario_cod,
                "sala": "",
            })
            if reg is None:
                continue
            chave = (reg["codigo"], reg["turma"], reg["horario"], reg["sala"])
            if chave not in vistos_grade:
                vistos_grade.add(chave)
                registros_grade.append(reg)

        return registros_grade

    linhas = [re.sub(r"\s+", " ", l).strip() for l in texto.splitlines() if l.strip()]
    registros: list[dict[str, str]] = []
    vistos: set[tuple[str, str, str, str]] = set()

    for idx, linha in enumerate(linhas):
        linha_upper = linha.upper()
        cod_match = _CODIGO_NO_TEXTO_RE.search(linha_upper)
        if not cod_match:
            continue

        codigo = cod_match.group(1)
        segmento = linha[cod_match.end() :]
        if not _BLOCO_SIGAA_RE.search(segmento.upper()) and idx + 1 < len(linhas):
            prox = linhas[idx + 1]
            if not _CODIGO_NO_TEXTO_RE.search(prox.upper()):
                segmento = f"{segmento} {prox}".strip()

        turma, horario_sigaa, sala = _extrair_campos_segmento(segmento)
        if not horario_sigaa:
            continue

        reg = sanitizar_registro_disciplina({
            "codigo": codigo,
            "turma": turma,
            "horario": horario_sigaa,
            "sala": sala,
        })
        if reg is None:
            continue

        chave = (reg["codigo"], reg["turma"], reg["horario"], reg["sala"])
        if chave not in vistos:
            vistos.add(chave)
            registros.append(reg)

    return registros


def processar_comprovante_em_memoria(conteudo: bytes) -> dict[str, Any]:
    """Executa o fluxo completo em memória: extrai, sanitiza para 4 campos e descarta."""
    texto = ""
    try:
        texto = extrair_texto_pdf_em_memoria(conteudo)
        tipo = detectar_tipo_documento(texto)
        disciplinas = extrair_disciplinas_de_texto(texto)

        if tipo == "historico_escolar" and not disciplinas:
            return {
                "sucesso": False,
                "recusado": True,
                "tipo_documento": tipo,
                "motivo": "historico_escolar_nao_suportado",
                "mensagem": MENSAGEM_RECUSA_HISTORICO,
                "disciplinas": [],
                "campos_mantidos": list(CAMPOS_PERMITIDOS_DOCUMENTO),
                "persistido_em_servidor": False,
                "enviado_llm_externo": False,
            }

        if not disciplinas:
            return {
                "sucesso": False,
                "recusado": True,
                "tipo_documento": tipo,
                "motivo": "sem_disciplinas_validas",
                "mensagem": MENSAGEM_SEM_DISCIPLINAS,
                "disciplinas": [],
                "campos_mantidos": list(CAMPOS_PERMITIDOS_DOCUMENTO),
                "persistido_em_servidor": False,
                "enviado_llm_externo": False,
            }

        return {
            "sucesso": True,
            "recusado": False,
            "tipo_documento": tipo,
            "disciplinas": disciplinas,
            "campos_mantidos": list(CAMPOS_PERMITIDOS_DOCUMENTO),
            "persistido_em_servidor": False,
            "enviado_llm_externo": False,
        }
    finally:
        del texto
