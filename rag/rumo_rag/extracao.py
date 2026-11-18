"""Etapas 1 e 2 da ingestão: coleta (download) e extração/limpeza de texto."""
import html
import re
import urllib.request
from pathlib import Path

import yaml
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from . import config


def carregar_catalogo() -> list[dict]:
    with open(config.CATALOGO, encoding="utf-8") as f:
        return yaml.safe_load(f)["documentos"]


def caminho_local(doc: dict) -> Path:
    return config.DADOS / doc["arquivo"]


def baixar(docs: list[dict]) -> None:
    """Baixa os originais que ainda não existem em dados/originais/."""
    config.ORIGINAIS.mkdir(parents=True, exist_ok=True)
    for d in docs:
        destino = caminho_local(d)
        if destino.exists() or not d["arquivo"].startswith("originais/"):
            continue
        print(f"baixando {d['id']} {d['url']}")
        req = urllib.request.Request(d["url"], headers={"User-Agent": "Mozilla/5.0 (RUmo/UnB)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            destino.write_bytes(r.read())


def _ler_pdf(p: Path) -> str:
    leitor = PdfReader(str(p))
    partes = []
    for i, pagina in enumerate(leitor.pages, start=1):
        partes.append(f"\n[[PAGINA {i}]]\n{pagina.extract_text() or ''}")
    return "".join(partes)


DIAS = {"2ª": "segunda-feira", "3ª": "terça-feira", "4ª": "quarta-feira", "5ª": "quinta-feira",
        "6ª": "sexta-feira", "SÁB": "sábado", "DOM": "domingo"}


# Datas do cabeçalho do cardápio: "09/11/2026", "9/11/2026" e "1º/9/2026" aparecem no mesmo PDF.
# O chunking e a API (com_data) esperam sempre dd/mm/aaaa, então tudo é normalizado aqui (#50).
DATA_CARDAPIO = re.compile(r"(\d{1,2})\s*[ºo°]?\s*/\s*(\d{1,2})\s*/\s*(\d{4})")


def data_cardapio(texto: str) -> str:
    """Primeira data do texto em dd/mm/aaaa, ou "" se não houver."""
    m = DATA_CARDAPIO.search(texto or "")
    return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}" if m else ""


_ALERGENICOS_LEGENDA = (
    "cogumelo", "leite", "mel", "pimenta", "soja",
    "gluten", "amendoim", "oleaginosa", "ovo", "suino",
)


def _vetorizar_icone(page_img, page, im_dict: dict, n_slices: int = 1):
    import numpy as np

    sx = page_img.width / page.width
    sy = page_img.height / page.height
    x0, top = im_dict["x0"] * sx, im_dict["top"] * sy
    x1, bot = im_dict["x1"] * sx, im_dict["bottom"] * sy
    pil = page_img.crop((int(round(x0)), int(round(top)), int(round(x1)), int(round(bot)))).convert("L")
    vecs = []
    sw = pil.width / n_slices
    for i in range(n_slices):
        crop = pil.crop((int(round(i * sw)), 0, int(round((i + 1) * sw)), pil.height)).resize((24, 24))
        arr = np.asarray(crop, dtype=np.float32).ravel()
        arr = arr - arr.mean()
        norm = float(np.linalg.norm(arr))
        vecs.append(arr / norm if norm > 1e-6 else arr)
    return vecs


def _templates_alergenicos(pg, texto: str) -> tuple[object | None, dict]:
    """Auto-calibra os 10 ícones da legenda do rodapé da própria página."""
    if len(pg.images) < 10 or "cogumelo" not in texto.lower() or "suíno" not in texto.lower():
        return None, {}
    footer = sorted((im for im in pg.images if im["top"] > pg.height * 0.85), key=lambda im: im["x0"])
    if len(footer) != len(_ALERGENICOS_LEGENDA):
        return None, {}
    try:
        pimg = pg.to_image(resolution=144).original
        templates = {
            _ALERGENICOS_LEGENDA[i]: _vetorizar_icone(pimg, pg, im, 1)[0]
            for i, im in enumerate(footer)
        }
        return pimg, templates
    except Exception:
        return None, {}


def _alergenicos_da_celula(pg, pimg, templates: dict, bbox: tuple[float, float, float, float] | None) -> list[str]:
    if not templates or pimg is None or not bbox:
        return []
    import numpy as np

    cx0, ctop, cx1, cbot = bbox
    ims = [
        im for im in pg.images
        if cx0 - 2 <= (im["x0"] + im["x1"]) / 2 <= cx1 + 2
        and ctop - 2 <= (im["top"] + im["bottom"]) / 2 <= cbot + 2
    ]
    encontrados: list[str] = []
    for im in ims:
        largura = im["x1"] - im["x0"]
        altura = max(1e-3, im["bottom"] - im["top"])
        n = max(1, round(largura / altura))
        for vec in _vetorizar_icone(pimg, pg, im, n):
            melhor_id, melhor_score = max(
                ((aid, float(np.dot(vec, tv))) for aid, tv in templates.items()),
                key=lambda x: x[1],
            )
            if melhor_score >= 0.65 and melhor_id not in encontrados:
                encontrados.append(melhor_id)
    return encontrados


def _ler_cardapio(p: Path) -> str:
    """Cardápio do RU é uma tabela (linhas = componentes, colunas = dias).
    Extrair como texto corrido mistura as colunas; aqui cada célula é lida
    e a semana vira um registro por refeição e por dia."""
    import pdfplumber
    saida = []
    paginas_texto = [pg.extract_text() or "" for pg in PdfReader(str(p)).pages]  # o rótulo da refeição é vertical
    eh_dia = re.compile(r"^([2-6]ª\s*FEIRA|SÁBADO|DOMINGO)", re.I)
    with pdfplumber.open(str(p)) as pdf:
        for n, pg in enumerate(pdf.pages, start=1):
            texto = paginas_texto[n - 1]
            refeicao = next((r for r in ("Café da manhã", "Almoço", "Jantar") if r.lower() in texto.lower()), "Refeição")
            rodape = re.findall(r"(Mesa de apoio:[^\n]*)", texto)
            pimg, templates = _templates_alergenicos(pg, texto)
            for tab in pg.find_tables():
                tabela = tab.extract()
                linhas = [[(c or "").replace("\n", " ").strip() for c in l] for l in tabela]
                i_dias = next((i for i, l in enumerate(linhas) if any(eh_dia.match(c) for c in l)), None)
                if i_dias is None:
                    continue
                cols = [j for j, c in enumerate(linhas[i_dias]) if eh_dia.match(c)]
                if not cols:
                    continue
                prox = linhas[i_dias + 1] if i_dias + 1 < len(linhas) else []
                linha_de_datas = any(data_cardapio(c) for c in prox)
                dias = []
                for j in cols:
                    rotulo = linhas[i_dias][j]
                    nome = next((v for k, v in DIAS.items() if rotulo.upper().startswith(k)), rotulo.lower())
                    data = data_cardapio(rotulo) or (linha_de_datas and j < len(prox) and data_cardapio(prox[j])) or ""
                    dias.append((j, nome, data))
                inicio_itens = i_dias + (2 if linha_de_datas else 1)
                componentes = []
                for offset, l in enumerate(linhas[inicio_itens:]):
                    r_idx = inicio_itens + offset
                    nome = next((c for c in l[:cols[0]] if c), "")
                    valores = [l[j] if j < len(l) else "" for j in cols]
                    if not nome or not any(valores):
                        continue
                    row_cells = tab.rows[r_idx].cells if r_idx < len(tab.rows) else []
                    for pos, j in enumerate(cols):
                        if not valores[pos]:
                            continue
                        bbox = row_cells[j] if j < len(row_cells) else None
                        alerg = _alergenicos_da_celula(pg, pimg, templates, bbox)
                        if alerg:
                            valores[pos] = f"{valores[pos]} [Alergênicos: {', '.join(alerg)}]"
                    if valores[0] and not any(valores[1:]):   # célula mesclada: vale para a semana toda
                        valores = [valores[0]] * len(valores)
                    componentes.append((nome.capitalize(), valores))
                for k, (_, nome_dia, data) in enumerate(dias):
                    saida.append(f"\n[[PAGINA {n}]]\n## {refeicao} · {nome_dia} {data}")
                    saida.append(f"Cardápio do RU Gama (FCTE) — {refeicao} de {nome_dia}, {data}:")
                    for comp, valores in componentes:
                        if valores[k]:
                            saida.append(f"- {comp}: {valores[k]}")
                    saida.extend(rodape)
    return "\n".join(saida)


def _ler_html(p: Path) -> str:
    bruto = p.read_bytes()
    try:
        s = bruto.decode("utf-8")
    except UnicodeDecodeError:
        s = bruto.decode("cp1252", errors="ignore")
    # fica só com o conteúdo principal da página (WordPress e Planalto)
    m = re.search(r"<main.*?</main>|<article.*?</article>", s, re.S | re.I)
    s = m.group(0) if m else s
    s = re.sub(r"<(script|style|nav|header|footer|form)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    # abas (Elementor/EAEL): cada painel vira uma seção com o título da aba, para não perder
    # a ligação "nível → disciplinas" das grades curriculares
    titulos = [t.strip() for t in re.findall(r'class="eael-tab-title[^"]*"\s*>([^<]+)<', s)]
    if titulos:
        s = re.sub(r'<ul class="eael-tabs-nav.*?</ul>', " ", s, flags=re.S)
        contador = iter(titulos)
        s = re.sub(r'<div[^>]*class="[^"]*eael-tab-content-item[^"]*"[^>]*>',
                   lambda m: f"\n<h2>{next(contador, 'Aba')}</h2>\n", s)
    s = re.sub(r"<h([1-4])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</tr>|</div>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s)


def limpar(texto: str) -> str:
    # PDFs do SEI perdem a ligadura "ti" (vira \x00): "a\x00vidades" -> "atividades"
    t = texto.replace("\x00", "ti").replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl").replace("\t", " ")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)          # palavra hifenizada na quebra de linha
    t = re.sub(r"[  ]+", " ", t)
    linhas = [l.strip() for l in t.splitlines()]
    # descarta rodapés/linhas de navegação muito curtas e repetitivas
    linhas = [l for l in linhas if not re.fullmatch(r"(Read More »|Nenhum comentário|\d{1,3})", l)]
    t = "\n".join(linhas)
    # rótulo de versão de grade ("PARA INGRESSANTES A PARTIR DE" + "2027") vira título de nível 1
    t = re.sub(r"(?:^#+\s*\n)?^PARA INGRESSANTES ([^\n]+)\n+([^\n]+)",
               lambda m: f"# Para ingressantes {m.group(1).lower()} {m.group(2)}", t, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def extrair(doc: dict) -> str:
    p = caminho_local(doc)
    if p.suffix == ".pdf" and doc.get("tipo") == "cardapio":
        bruto = _ler_cardapio(p)
    elif p.suffix == ".pdf":
        bruto = _ler_pdf(p)
    elif p.suffix in (".html", ".htm"):
        bruto = _ler_html(p)
    else:  # .md / .txt curados pelo grupo
        bruto = p.read_text(encoding="utf-8")
    return limpar(bruto)


def extrair_todos(docs: list[dict]) -> dict[str, str]:
    config.TEXTO.mkdir(parents=True, exist_ok=True)
    textos = {}
    for d in docs:
        t = extrair(d)
        (config.TEXTO / f"{d['id']}.txt").write_text(t, encoding="utf-8")
        textos[d["id"]] = t
        print(f"{d['id']}: {len(t):>7} caracteres · {d['titulo'][:70]}")
    return textos
