"""Agente especializado em informações do Restaurante Universitário (RU)."""

from __future__ import annotations

from .. import config, indice


class AgenteRU:
    """Research Agent responsável por pesquisar informações do RU."""

    nome = "Agente RU"
    eixo = "ru"

    def __init__(
        self,
        k: int = config.TOP_K,
        modo: str = "hibrido",
    ):
        # Valida a quantidade de trechos que serão recuperados.
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise ValueError("O parâmetro k deve ser um inteiro positivo.")

        # Valida o método de recuperação.
        if modo not in ("denso", "bm25", "hibrido"):
            raise ValueError("Modo de busca inválido.")

        self.k = k
        self.modo = modo

    def pesquisar(self, pergunta: str) -> dict:
        """
        Pesquisa informações do Restaurante Universitário.

        Recebe uma pergunta do Orquestrador e retorna os
        trechos recuperados e suas respectivas fontes.
        """

        # Valida a pergunta recebida.
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("A pergunta não pode estar vazia.")

        pergunta = pergunta.strip()

        # Busca restrita aos documentos do eixo RU.
        # A decomposição fica sob responsabilidade do Orquestrador.
        trechos = indice.buscar(
            pergunta,
            k=self.k,
            modo=self.modo,
            eixo=self.eixo,
            decompor_pergunta=False,
        )

        # Organiza as fontes sem duplicar a mesma página.
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
                        "doc_id",
                        "titulo",
                        "orgao",
                        "pagina",
                        "secao",
                        "url",
                        "chunk_id",
                    )
                })

        # Retorna os resultados para o Orquestrador.
        return {
            "agente": self.nome,
            "eixo": self.eixo,
            "pergunta": pergunta,
            "encontrou": bool(trechos),
            "trechos": trechos,
            "fontes": fontes,
        }
