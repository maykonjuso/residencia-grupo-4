"""Agente especializado em disciplinas e normas acadêmicas."""

from __future__ import annotations

from .. import config, indice


class AgenteFluxo:
    """Pesquisa informações do fluxo acadêmico."""

    nome = "Agente Fluxo"
    eixo = "fluxo"

    def __init__(self, k: int = config.TOP_K, modo: str = "hibrido"):
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("O parâmetro k deve ser um inteiro positivo.")
        if modo not in ("denso", "bm25", "hibrido"):
            raise ValueError("Modo de busca inválido.")

        self.k = k
        self.modo = modo

    def pesquisar(self, pergunta: str) -> dict:
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("A pergunta não pode estar vazia.")

        pergunta = pergunta.strip()
        trechos = indice.buscar(
            pergunta,
            k=self.k,
            modo=self.modo,
            eixo=self.eixo,
            decompor_pergunta=False,
        )

        fontes = []
        fontes_vistas = set()

        for trecho in trechos:
            chave = (
                trecho.get("doc_id"),
                trecho.get("pagina"),
                trecho.get("url"),
            )
            if chave not in fontes_vistas:
                fontes_vistas.add(chave)
                fontes.append({
                    campo: trecho.get(campo)
                    for campo in (
                        "doc_id", "titulo", "orgao", "pagina",
                        "secao", "url", "chunk_id",
                    )
                })

        return {
            "agente": self.nome,
            "eixo": self.eixo,
            "pergunta": pergunta,
            "encontrou": bool(trechos),
            "trechos": trechos,
            "fontes": fontes,
        }