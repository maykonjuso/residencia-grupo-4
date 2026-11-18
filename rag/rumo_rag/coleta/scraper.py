"""Scraper do cardápio semanal do RU Gama (issue #50 · RF01 · épico E5).

Fonte oficial: a página https://ru.unb.br/cardapio-gama/ (Diretoria do RU / DAC) lista um
link por semana, com o texto "ISM – 12/10/2026 A 18/10/2026", apontando para um PDF em
wp-content/uploads. O cardápio em si é uma tabela dentro do PDF (não é imagem), então a
leitura reaproveita ``extracao._ler_cardapio``, a mesma da ingestão.

Regras de educação com o site institucional:
- uma requisição por recurso (a página e, depois, o PDF da semana), em sequência;
- sem paralelismo e sem nova tentativa automática;
- User-Agent identificando o projeto.

Tudo é baixado e lido em memória antes de gravar qualquer coisa. Se a rede falhar no meio,
nada é gravado. Na gravação, cada arquivo é escrito num temporário e só então renomeado,
então nunca fica arquivo pela metade.

O HTML bruto da página é guardado em ``dados/brutos/cardapio-gama/``: quando o layout mudar,
é com ele que se descobre o que quebrou.
"""
from __future__ import annotations

import html
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import config

try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

PAGINA = "https://ru.unb.br/cardapio-gama/"
ORGAO = "UnB · Diretoria do RU"
USER_AGENT = ("RUmo/1.0 (Residência em IA UnB/FCTE, Grupo 04; coleta semanal do cardápio; "
              "+https://github.com/maykonjuso/residencia-grupo-4)")
TIMEOUT = 30
BRUTOS = config.DADOS / "brutos" / "cardapio-gama"

_LINK = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"']+?\.pdf)[\"'][^>]*>(.*?)</a>", re.I | re.S)
_DATA = r"(\d{1,2})\s*[ºo°]?\s*/\s*(\d{1,2})\s*/\s*(\d{4})"
_INTERVALO_TEXTO = re.compile(_DATA + r"\s*(?:a|à|até|-|–)\s*" + _DATA, re.I)
_INTERVALO_ARQUIVO = re.compile(r"(\d{1,2})-(\d{1,2})-a-(\d{1,2})-(\d{1,2})", re.I)
_ANO_UPLOAD = re.compile(r"/uploads/(\d{4})/(\d{2})/")


class ErroColeta(Exception):
    """Falha esperada da coleta (rede, página sem semanas, PDF ilegível). Mensagem para humanos."""


@dataclass(frozen=True)
class Semana:
    inicio: date
    fim: date
    url: str
    texto: str

    def contem(self, d: date) -> bool:
        return self.inicio <= d <= self.fim


# ----------------------------------------------------------------------------- rede

def baixar(url: str, timeout: int = TIMEOUT) -> bytes:
    """Uma requisição, sem nova tentativa. Erro de rede vira ErroColeta com mensagem clara."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise ErroColeta(f"{url} respondeu HTTP {e.code}. A página pode ter mudado de endereço.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        motivo = getattr(e, "reason", e)
        raise ErroColeta(f"não consegui acessar {url} ({motivo}). Sem conexão com a internet?") from e


# ----------------------------------------------------------------------------- página

def _data(d: str, m: str, a: str) -> date:
    return date(int(a), int(m), int(d))


def _intervalo_pelo_arquivo(url: str) -> tuple[date, date] | None:
    """'.../uploads/2026/10/Gama-Semana-04-12-10-a-18-10.pdf' -> (12/10/2026, 18/10/2026)."""
    m = _INTERVALO_ARQUIVO.search(urllib.parse.unquote(url.rsplit("/", 1)[-1]))
    a = _ANO_UPLOAD.search(url)
    if not m or not a:
        return None
    ano = int(a.group(1))
    try:
        inicio = date(ano, int(m.group(2)), int(m.group(1)))
        fim = date(ano, int(m.group(4)), int(m.group(3)))
    except ValueError:
        return None
    if fim < inicio:                       # semana que atravessa o ano (29/12 a 4/1)
        fim = date(ano + 1, fim.month, fim.day)
    return inicio, fim


def listar_semanas(pagina_html: str, base: str = PAGINA) -> tuple[list[Semana], list[str]]:
    """Semanas linkadas na página, da mais antiga para a mais nova, e avisos de links ignorados."""
    semanas, avisos = {}, []
    for href, rotulo in _LINK.findall(pagina_html):
        url = urllib.parse.urljoin(base, html.unescape(href.strip()))
        texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", rotulo))).strip()
        m = _INTERVALO_TEXTO.search(texto)
        try:
            intervalo = (_data(*m.groups()[:3]), _data(*m.groups()[3:])) if m else _intervalo_pelo_arquivo(url)
        except ValueError:
            intervalo = _intervalo_pelo_arquivo(url)
        if not intervalo:
            avisos.append(f"link sem datas reconhecíveis, ignorado: {texto or url}")
            continue
        semanas[url] = Semana(intervalo[0], intervalo[1], url, texto)
    return sorted(semanas.values(), key=lambda s: (s.inicio, s.url)), avisos


def escolher_semana(semanas: list[Semana], referencia: date) -> tuple[Semana, str | None]:
    """A semana que contém a data; se nenhuma contém, a mais recente (com aviso)."""
    if not semanas:
        raise ErroColeta(f"a página {PAGINA} não tem nenhum link de cardápio reconhecível. "
                         "O layout pode ter mudado: confira o HTML bruto guardado.")
    for s in reversed(semanas):
        if s.contem(referencia):
            return s, None
    ultima = semanas[-1]
    return ultima, (f"nenhuma semana publicada contém {referencia:%d/%m/%Y}; "
                    f"usando a mais recente ({ultima.inicio:%d/%m} a {ultima.fim:%d/%m/%Y})")


# ----------------------------------------------------------------------------- PDF -> dias

_SECAO = re.compile(r"^## (?P<ref>.+?) · (?P<dia>\S+) ?(?P<data>\d{2}/\d{2}/\d{4})?\s*$")
_ORDEM_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


def completar_datas(texto: str, inicio: date) -> tuple[str, list[str]]:
    """Seção sem data ("## Almoço · segunda-feira ") recebe a data pelo dia da semana."""
    avisos, saida = [], []
    for linha in texto.splitlines():
        m = _SECAO.match(linha)
        if m and not m.group("data") and m.group("dia") in _ORDEM_DIAS:
            d = inicio + timedelta(days=(_ORDEM_DIAS.index(m.group("dia")) - inicio.weekday()) % 7)
            avisos.append(f"{m.group('ref')} de {m.group('dia')} sem data no PDF; usei {d:%d/%m/%Y} pela semana do link")
            linha = f"## {m.group('ref')} · {m.group('dia')} {d:%d/%m/%Y}"
            saida.append(linha)
            continue
        if linha.startswith("Cardápio do RU Gama (FCTE) —") and saida and _SECAO.match(saida[-1]):
            sec = _SECAO.match(saida[-1])
            if sec.group("data"):
                linha = f"Cardápio do RU Gama (FCTE) — {sec.group('ref')} de {sec.group('dia')}, {sec.group('data')}:"
        saida.append(linha)
    return "\n".join(saida), avisos


def ler_pdf(conteudo: bytes, semana: Semana) -> tuple[str, list[str]]:
    """Texto normalizado por refeição e dia, no formato que o chunking espera."""
    from .. import extracao
    if not conteudo.startswith(b"%PDF"):
        raise ErroColeta(f"{semana.url} não devolveu um PDF. Se o cardápio virou imagem, "
                         "trate esta semana como fonte curada (como dados/curados/F16_*.md).")
    with tempfile.TemporaryDirectory() as tmp:          # fora de dados/: nada fica pela metade lá
        caminho = Path(tmp) / "cardapio.pdf"
        caminho.write_bytes(conteudo)
        try:
            bruto = extracao._ler_cardapio(caminho)
        except Exception as e:                           # PDF corrompido ou layout irreconhecível
            raise ErroColeta(f"não consegui ler a tabela do PDF {semana.url} ({type(e).__name__}: {e})") from e
    texto, avisos = completar_datas(extracao.limpar(bruto), semana.inicio)
    if "## " not in texto:
        raise ErroColeta(f"o PDF {semana.url} não tem a tabela de cardápio esperada "
                         "(cardápio em imagem ou layout novo). Nada foi gravado.")
    return texto, avisos


def dias(texto: str) -> list[dict]:
    """[{'data': '09/11/2026', 'dia': 'segunda-feira', 'refeicoes': {'Almoço': ['Salada 1: ...']}}]"""
    por_dia: dict[tuple[str, str], dict] = {}
    atual = None
    for linha in texto.splitlines():
        m = _SECAO.match(linha)
        if m:
            chave = (m.group("data") or "", m.group("dia"))
            dia = por_dia.setdefault(chave, {"data": chave[0], "dia": chave[1], "refeicoes": {}})
            atual = dia["refeicoes"].setdefault(m.group("ref"), [])
            continue
        if atual is not None and linha.startswith("- "):
            atual.append(linha[2:].strip())

    def ordem(d):
        try:
            return datetime.strptime(d["data"], "%d/%m/%Y").date(), ""
        except ValueError:
            return date.max, d["dia"]
    return sorted(por_dia.values(), key=ordem)


# ----------------------------------------------------------------------------- gravação

def gravar_atomico(destino: Path, conteudo: bytes | str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=f".{destino.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
        os.replace(tmp, destino)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def entrada_do_catalogo(catalogo_texto: str, semana: Semana, coletado_em: date) -> tuple[str, str | None]:
    """(id, bloco YAML) para acrescentar ao catálogo; bloco None se a URL já está catalogada."""
    m = re.search(r'^\s*-\s*id:\s*(F\d+)\s*\n(?:(?!^\s*-\s*id:).*\n)*?\s*url:\s*"?' + re.escape(semana.url) + r'"?\s*$',
                  catalogo_texto, re.M)
    if m:
        return m.group(1), None
    numeros = [int(n) for n in re.findall(r"^\s*-\s*id:\s*F(\d+)", catalogo_texto, re.M)]
    novo = f"F{max(numeros, default=0) + 1:02d}"
    titulo = f"Cardápio semanal do RU Gama — {semana.inicio:%d/%m} a {semana.fim:%d/%m/%Y}"
    bloco = (f"  - id: {novo}\n"
             f'    titulo: "{titulo}"\n'
             f'    orgao: "{ORGAO}"\n'
             f"    eixo: ru\n"
             f"    tipo: cardapio\n"
             f'    data: "{semana.inicio.isoformat()}"\n'
             f'    url: "{semana.url}"\n'
             f"    arquivo: originais/{novo}.pdf\n"
             f'    coletado_em: "{coletado_em.isoformat()}"  # scraper (#50), página {PAGINA}\n')
    return novo, bloco


def gravar(pagina_html: bytes | None, pdf: bytes, semana: Semana, hoje: date) -> dict:
    """Guarda o HTML bruto, o PDF em originais/ e registra a semana no catálogo. Devolve o que gravou."""
    catalogo = config.CATALOGO.read_text(encoding="utf-8")
    doc_id, bloco = entrada_do_catalogo(catalogo, semana, hoje)
    gravados = {"doc_id": doc_id, "arquivos": []}
    if pagina_html is not None:
        bruto = BRUTOS / f"{datetime.now():%Y-%m-%dT%H%M%S}.html"
        gravar_atomico(bruto, pagina_html)
        gravados["arquivos"].append(bruto)
    pdf_destino = config.ORIGINAIS / f"{doc_id}.pdf"
    gravar_atomico(pdf_destino, pdf)
    gravados["arquivos"].append(pdf_destino)
    if bloco:
        if not catalogo.endswith("\n"):
            catalogo += "\n"
        gravar_atomico(config.CATALOGO, catalogo + bloco)
        gravados["arquivos"].append(config.CATALOGO)
    gravados["novo"] = bloco is not None
    return gravados


# ----------------------------------------------------------------------------- orquestração

def coletar(referencia: date, pagina_local: Path | None = None, pdf_local: Path | None = None,
            url_pdf: str | None = None) -> dict:
    """Baixa (ou lê do disco) a página e o PDF da semana e devolve tudo em memória, sem gravar."""
    avisos: list[str] = []
    pagina = None
    if url_pdf or (pdf_local and not pagina_local):
        # sem a página: a semana vem do nome do arquivo ou, na falta dele, da data de referência
        intervalo = _intervalo_pelo_arquivo(url_pdf) if url_pdf else None
        inicio = intervalo[0] if intervalo else referencia - timedelta(days=referencia.weekday())
        semana = Semana(inicio, intervalo[1] if intervalo else inicio + timedelta(days=6),
                        url_pdf or pdf_local.resolve().as_uri(), "informado na linha de comando")
    else:
        pagina = pagina_local.read_bytes() if pagina_local else baixar(PAGINA)
        semanas, avisos_links = listar_semanas(pagina.decode("utf-8", errors="replace"))
        avisos += avisos_links
        semana, aviso = escolher_semana(semanas, referencia)
        if aviso:
            avisos.append(aviso)
    pdf = pdf_local.read_bytes() if pdf_local else baixar(semana.url)
    texto, avisos_pdf = ler_pdf(pdf, semana)
    return {"semana": semana, "pagina": pagina, "pdf": pdf, "texto": texto,
            "dias": dias(texto), "avisos": avisos + avisos_pdf}


def imprimir(resultado: dict) -> str:
    from .cardapio import ALERGENICOS_OFICIAIS

    s = resultado["semana"]
    legenda = ", ".join(rotulo for _, rotulo in ALERGENICOS_OFICIAIS)
    extraidos = "[Alergênicos:" in resultado.get("texto", "")
    obs = (
        "Extraídos automaticamente dos ícones do PDF por célula (auto-calibrados pela legenda do rodapé)."
        if extraidos
        else "Notações de alergênicos por prato no PDF oficial são ícones (imagens) não extraídos como texto."
    )
    linhas = [
        f"Cardápio do RU Gama · semana de {s.inicio:%d/%m/%Y} a {s.fim:%d/%m/%Y}",
        f"fonte: {s.url}",
        f"listada em: {PAGINA}",
        f"alergenicos (legenda oficial): {legenda}",
        f"alergenicos (observacao): {obs}",
        "",
    ]
    for d in resultado["dias"]:
        linhas.append(f"{d['dia']} {d['data']}".strip())
        for ref, itens in d["refeicoes"].items():
            linhas.append(f"  {ref}")
            linhas.extend(f"    - {i}" for i in itens)
        linhas.append("")
    return "\n".join(linhas)
