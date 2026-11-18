"""Alergênicos por prato, lidos dos ícones do cardápio oficial do RU (Issue #55).

O cardápio semanal do RU Gama marca cada preparação com ícones de alergênicos
(Cogumelo, Leite e derivados, Mel, Pimenta, Soja, Trigo/Glúten, Amendoim, Oleaginosa,
Ovo, Suíno) e traz a legenda no rodapé de cada página. A extração de texto descarta
imagens, então essa informação nunca chegava à base. Este módulo:

1. recorta os ícones da legenda da própria página (referência visual, com o nome
   lido das palavras logo abaixo de cada ícone);
2. recorta cada ícone da tabela (algumas imagens juntam 2 ou 3 ícones lado a lado),
   e o compara pixel a pixel com os 10 da legenda;
3. liga o ícone à opção de prato da célula onde ele está (a palavra com maior
   sobreposição à esquerda na mesma linha; se não houver, a mais próxima à direita;
   se não houver, a linha de texto logo acima);
4. escreve a etiqueta "[Alergênicos: ...]" logo depois de cada opção, no texto da célula.
   Esse é o formato que `coleta/cardapio.py` (#54) transforma no campo `alergenicos`
   de cada opção do JSON de montagem de prato.

Nada é estimado: quando a comparação não é clara, a etiqueta diz "a conferir na
distribuição", e o alergênico duvidoso não é afirmado. Calorias e nutrientes não são
publicados pelo RU e não entram aqui (decisão em docs/entrega-2/base-de-conhecimento.md).
"""
import re

RESOLUCAO = 300                 # dpi da renderização usada para comparar os ícones
LADO = 24                       # ícones reduzidos a 24×24 px antes da comparação
MARGEM_MINIMA = 1.25            # 2º melhor / melhor: abaixo disso, a escolha é ambígua
DISTANCIA_MAXIMA = 0.06         # erro quadrático médio máximo para aceitar um ícone
ALTURA_RODAPE = 70              # pontos: faixa do rodapé onde fica a legenda
ALTURA_CABECALHO = 70           # pontos: faixa dos logotipos (UnB, ISM)
SEPARADOR = re.compile(r"^(ou|OU|/)$")
A_CONFERIR = "a conferir na distribuição"


# ---------------------------------------------------------------- comparação de imagens
def _pixels(img):
    largura, altura = img.size
    px = img.load()
    return [[px[x, y] for x in range(largura)] for y in range(altura)]


def _tem_tinta(px) -> bool:
    return min(px) < 217           # ~0,85 em escala 0–1: tudo que não é fundo branco


def _segmentos(img):
    """Divide o recorte de uma imagem em ícones: pelas colunas brancas entre eles e,
    quando os círculos se encostam, pela proporção largura/altura."""
    linhas = _pixels(img)
    largura, altura = img.size
    colunas = [any(_tem_tinta(linhas[y][x]) for y in range(altura)) for x in range(largura)]
    trechos, ini = [], None
    for x, c in enumerate(colunas + [False]):
        if c and ini is None:
            ini = x
        elif not c and ini is not None:
            trechos.append((ini, x))
            ini = None
    saida = []
    for x0, x1 in trechos:
        if x1 - x0 <= altura * 0.4:            # sujeira estreita, não é ícone
            continue
        ys = [y for y in range(altura) if any(_tem_tinta(linhas[y][x]) for x in range(x0, x1))]
        y0, y1 = ys[0], ys[-1] + 1
        k = max(1, round((x1 - x0) / (y1 - y0)))
        passo = (x1 - x0) / k
        for j in range(k):
            saida.append(img.crop((x0 + round(j * passo), y0, x0 + round((j + 1) * passo), y1)))
    return saida


def _vetor(img):
    pequeno = img.convert("RGB").resize((LADO, LADO))
    return [c / 255 for c in pequeno.tobytes()]


def _distancia(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


# ---------------------------------------------------------------- leitura da página
def _recorte(render, bbox):
    esc = RESOLUCAO / 72
    x0, topo, x1, base = bbox
    return render.crop((round(x0 * esc), round(topo * esc), round(x1 * esc), round(base * esc))).convert("RGB")


def _legenda(pg, render):
    """[(nome, vetor)] dos ícones do rodapé, com o nome lido das palavras sob cada um."""
    icones = sorted((i for i in pg.images if i["top"] > pg.height - ALTURA_RODAPE), key=lambda i: i["x0"])
    if not icones:
        return []
    palavras = [w for w in pg.extract_words() if w["top"] > min(i["bottom"] for i in icones) - 2]
    nomes = {id(i): [] for i in icones}
    for w in palavras:
        centro = (w["x0"] + w["x1"]) / 2
        dono = min(icones, key=lambda i: abs((i["x0"] + i["x1"]) / 2 - centro))
        nomes[id(dono)].append(w)
    legenda = []
    for i in icones:
        nome = " ".join(w["text"] for w in sorted(nomes[id(i)], key=lambda w: w["x0"]))
        segs = _segmentos(_recorte(render, (i["x0"], i["top"], i["x1"], i["bottom"])))
        if nome and segs:
            legenda.append((nome, _vetor(segs[0])))
    return legenda


def icones_da_pagina(pg) -> list[dict]:
    """Cada ícone de alergênico da tabela: centro, alergênico e se a leitura é segura."""
    render = pg.to_image(resolution=RESOLUCAO).original
    legenda = _legenda(pg, render)
    if len(legenda) < 2:
        return []                           # página sem legenda: não há como identificar
    vistos, saida = set(), []
    for im in pg.images:
        if im["top"] > pg.height - ALTURA_RODAPE or im["top"] < ALTURA_CABECALHO:
            continue
        x0, x1, topo, base = im["x0"], im["x1"], im["top"], im["bottom"]
        segs = _segmentos(_recorte(render, (x0, topo, x1, base)))
        for k, seg in enumerate(segs):
            v = _vetor(seg)
            d = sorted((_distancia(v, ref), nome) for nome, ref in legenda)
            cx = x0 + (k + 0.5) * (x1 - x0) / len(segs)
            chave = (d[0][1], round(cx), round((topo + base) / 2))
            if chave in vistos:             # o PDF às vezes desenha a mesma imagem duas vezes
                continue
            vistos.add(chave)
            margem = d[1][0] / max(d[0][0], 1e-9)
            saida.append({"cx": cx, "top": topo, "bottom": base, "x0": x0,
                          "alergeno": d[0][1], "distancia": round(d[0][0], 4), "margem": round(margem, 2),
                          "seguro": margem >= MARGEM_MINIMA and d[0][0] <= DISTANCIA_MAXIMA})
    return saida


def _celula(palavras):
    """Divide as palavras da célula em opções ('X ou Y', 'X / Y', 'X ... OPÇÃO: Y').

    Devolve (opcoes, fluxo). `fluxo` é a sequência original de palavras, com a marca
    ("fim", k) onde a opção k termina: é onde a etiqueta de alergênicos é inserida,
    sem mexer em nenhuma palavra nem separador da célula."""
    opcoes, atual, fluxo = [], [], []

    def fecha():
        if atual:
            fluxo.append(("fim", len(opcoes)))
            opcoes.append(list(atual))
            atual.clear()

    for w in palavras:
        t = w["text"]
        if SEPARADOR.match(t):
            fecha()
            fluxo.append(("txt", t))
            continue
        if t.startswith("/") and len(t) > 1:          # "Chipotle /Limão": barra grudada
            fecha()
            fluxo.append(("txt", t))
            atual.append(dict(w, text=t[1:]))
            continue
        if t.upper().startswith("OPÇÃO"):
            fecha()
        fluxo.append(("txt", t))
        atual.append(w)
    fecha()
    return opcoes, fluxo


def _dono(icone, opcoes):
    """Índice da opção a que o ícone pertence."""
    candidatas = []
    for k, op in enumerate(opcoes):
        for w in op:
            # o ícone é mais alto que o texto e pode encostar em duas linhas: vale a de maior sobreposição
            sobreposicao = min(w["bottom"], icone["bottom"]) - max(w["top"], icone["top"])
            if sobreposicao > 0 and w["x1"] <= icone["cx"]:
                candidatas.append((-round(sobreposicao), icone["cx"] - w["x1"], k))
    if candidatas:
        return min(candidatas)[2]
    # ícone antes do texto, na mesma linha: vale a palavra mais próxima à direita
    direita = [(w["x0"] - icone["cx"], k) for k, op in enumerate(opcoes) for w in op
               if min(w["bottom"], icone["bottom"]) - max(w["top"], icone["top"]) > 0 and w["x0"] >= icone["cx"]]
    if direita:
        return min(direita)[1]
    acima = [(w["bottom"], w["x1"], k) for k, op in enumerate(opcoes) for w in op if w["bottom"] <= icone["top"] + 2]
    if acima:
        return max(acima)[2]
    return 0


def etiqueta(item: dict) -> str:
    """'[Alergênicos: Trigo/Glúten, Leite e derivados]', no formato que coleta/cardapio.py lê (#54).
    Ícone duvidoso vira 'a conferir na distribuição': o parser registra aviso e não afirma nada."""
    nomes = list(item["alergenos"])
    if item["conferir"]:
        nomes.append(A_CONFERIR)
    return f"[Alergênicos: {', '.join(nomes)}]" if nomes else ""


def anotar(fluxo, itens: list[dict]) -> str:
    """Remonta o texto da célula com a etiqueta logo depois de cada opção que tem ícone."""
    partes = []
    for tipo, valor in fluxo:
        if tipo == "txt":
            partes.append(valor)
        elif etiqueta(itens[valor]):
            partes.append(etiqueta(itens[valor]))
    return " ".join(partes)


def alergenos_por_celula(pg, tabela) -> dict:
    """{bbox da célula: {'texto': texto anotado, 'itens': [{'opcao', 'alergenos', 'conferir'}]}},
    só para as células que têm ícone."""
    icones = icones_da_pagina(pg)
    saida = {}
    for linha in tabela.rows:
        for bbox in linha.cells:
            if not bbox:
                continue
            dentro = [i for i in icones if bbox[0] <= i["cx"] <= bbox[2] and bbox[1] <= (i["top"] + i["bottom"]) / 2 <= bbox[3]]
            if not dentro:
                continue
            opcoes, fluxo = _celula(pg.crop(bbox).extract_words())
            if not opcoes:
                continue
            itens = [{"opcao": " ".join(w["text"] for w in op), "alergenos": [], "conferir": False} for op in opcoes]
            for i in sorted(dentro, key=lambda i: i["cx"]):
                item = itens[_dono(i, opcoes)]
                if not i["seguro"]:
                    item["conferir"] = True
                elif i["alergeno"] not in item["alergenos"]:
                    item["alergenos"].append(i["alergeno"])
            saida[tuple(bbox)] = {"texto": anotar(fluxo, itens), "itens": itens}
    return saida
