"""Etapa 3 da ingestão: divisão em chunks com consciência de estrutura.

Estratégia (justificativa em docs/entrega-2/chunking.md):
1. Quebra o texto em blocos lógicos: páginas, títulos (#), artigos de norma (Art. N),
   itens numerados de edital (2.1, 3.4.1) e parágrafos.
2. Junta blocos vizinhos até ~CHUNK_ALVO caracteres, sem passar de CHUNK_MAX.
3. Blocos maiores que CHUNK_MAX são cortados por frase, com SOBREPOSICAO.
4. Cardápios: cada página (uma refeição da semana) vira um chunk inteiro,
   para não separar o dia da semana do prato.
5. Cada chunk recebe um cabeçalho de contexto (documento, seção, página),
   que entra no embedding e ajuda a recuperar trechos curtos.
"""
import re

from . import config

PAGINA = re.compile(r"\[\[PAGINA (\d+)\]\]")
INICIO_BLOCO = re.compile(
    r"^(#{1,4} |Art\.? ?\d+|CAP[IÍ]TULO|SE[CÇ][AÃ]O|\d+(\.\d+){1,3}\.? |[IVX]{1,5} ?[-–.] )",
    re.I,
)


def _blocos(texto: str):
    """Gera (pagina, secao, bloco)."""
    pagina, secao = 1, ""
    pilha: dict[int, str] = {}      # nível do título -> texto (hierarquia de seções)
    atual: list[str] = []

    def fechar():
        if atual:
            b = "\n".join(atual).strip()
            if b:
                yield pagina, secao, b
            atual.clear()

    for linha in texto.splitlines():
        m = PAGINA.fullmatch(linha.strip())
        if m:
            yield from fechar()
            pagina = int(m.group(1))
            continue
        if not linha.strip():
            yield from fechar()
            continue
        if INICIO_BLOCO.match(linha):
            yield from fechar()
            if linha.startswith("#"):
                nivel = len(linha) - len(linha.lstrip("#"))
                titulo = linha.lstrip("# ").strip()[:70]
                if titulo:
                    pilha = {n: t for n, t in pilha.items() if n < nivel}
                    pilha[nivel] = titulo
                    secao = " > ".join(pilha[n] for n in sorted(pilha))[:160]
        atual.append(linha)
    yield from fechar()


def _cortar_grande(bloco: str, maximo: int) -> list[str]:
    frases = re.split(r"(?<=[.;:!?])\s+", bloco)
    partes, buf = [], ""
    for f in frases:
        while len(f) > maximo:                # frase gigante (tabela): corte seco
            partes.append((buf + " " + f[:maximo]).strip()); buf = ""
            f = f[maximo - config.SOBREPOSICAO:]
        if len(buf) + len(f) + 1 > maximo and buf:
            partes.append(buf.strip())
            buf = buf[-config.SOBREPOSICAO:] + " " + f
        else:
            buf = (buf + " " + f).strip()
    if buf.strip():
        partes.append(buf.strip())
    return partes


def dividir(doc: dict, texto: str) -> list[dict]:
    cardapio = doc.get("tipo") == "cardapio"
    maximo = config.CHUNK_MAX_CARDAPIO if cardapio else config.CHUNK_MAX
    alvo = maximo if cardapio else config.CHUNK_ALVO

    grupos: list[tuple[int, str, str]] = []   # (pagina, secao, texto)
    for pagina, secao, bloco in _blocos(texto):
        pedacos = [bloco] if len(bloco) <= maximo else _cortar_grande(bloco, maximo)
        for p in pedacos:
            ult = grupos[-1] if grupos else None
            mesma_pagina = ult and (ult[0] == pagina or not cardapio)
            # junta com o bloco anterior se for a mesma seção ou uma subseção dela
            # (ex.: "Grupo II" + "Grupo II > Café da manhã: R$ 2,00"); cardápio: um dia por chunk
            mesma_secao = ult and (ult[1] == secao or (not cardapio and bool(ult[1]) and secao.startswith(ult[1] + " > ")))
            if ult and mesma_pagina and mesma_secao and len(ult[2]) + len(p) + 1 <= alvo:
                grupos[-1] = (ult[0], ult[1], ult[2] + "\n" + p)
            else:
                grupos.append((pagina, secao, p))

    chunks = []
    for i, (pagina, secao, corpo) in enumerate(grupos):
        if len(corpo) < 40:      # descarta migalhas (números de página, rótulos soltos)
            continue
        cabecalho = f"{doc['titulo']} ({doc['orgao']})"
        if secao:
            cabecalho += f" · {secao}"
        chunks.append({
            "chunk_id": f"{doc['id']}-{i:04d}",
            "doc_id": doc["id"],
            "titulo": doc["titulo"],
            "orgao": doc["orgao"],
            "eixo": doc["eixo"],
            "curso": doc.get("curso", ""),
            "tipo": doc["tipo"],
            "url": doc["url"],
            "data": str(doc.get("data", "")),
            "pagina": pagina,
            "secao": secao,
            "texto": corpo,
            "texto_indexado": f"{cabecalho}\n{corpo}",
        })
    return chunks
