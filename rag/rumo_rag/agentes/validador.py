"""Agente Validador factual e verificador de citações obrigatórias (RN-02 e RN-03)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .. import geracao
from .base import Agente
from .mensagem import Mensagem, Resposta


@dataclass
class ResultadoValidacao:
    """Parecer factual emitido pelo AgenteValidador sobre a saída de um agente."""

    aprovado: bool
    valores_sem_fonte: list[str]
    sem_citacao: bool
    eh_recusa: bool
    motivos: list[str]
    acao_recomendada: str


def normalizar_trecho_validacao(t: dict) -> dict:
    """Garante as chaves mínimas esperadas por `geracao.py` ao validar ou extrair citações."""
    return {
        "chunk_id": t.get("chunk_id") or "",
        "doc_id": t.get("doc_id") or "",
        "titulo": t.get("titulo") or "",
        "orgao": t.get("orgao") or "",
        "pagina": t.get("pagina") if t.get("pagina") is not None else "",
        "secao": t.get("secao") or "",
        "url": t.get("url") or "",
        "texto": t.get("texto") or t.get("conteudo") or "",
    }


def avaliar_validacao(
    conteudo: str,
    trechos: list[dict] | None,
    fontes: list[dict] | None,
    erro: str | None = None,
) -> ResultadoValidacao:
    """Executa a checagem factual (valores sem respaldo e citação obrigatória RN-02)."""
    if erro:
        return ResultadoValidacao(
            aprovado=False,
            valores_sem_fonte=[],
            sem_citacao=False,
            eh_recusa=False,
            motivos=[f"Falha na execução do agente: {erro}"],
            acao_recomendada="devolver_ao_sintetizador",
        )

    recusa = geracao.eh_recusa(conteudo)
    motivos: list[str] = []

    if trechos is not None:
        trechos_norm = [normalizar_trecho_validacao(t) for t in trechos]
        valores = geracao.valores_sem_fonte(conteudo, trechos_norm)
        sem_cit = geracao.resposta_sem_citacao(conteudo, trechos_norm)
    else:
        fontes_com_texto = [
            normalizar_trecho_validacao(f)
            for f in (fontes or [])
            if isinstance(f, dict) and (f.get("texto") or f.get("conteudo"))
        ]
        if fontes_com_texto:
            valores = geracao.valores_sem_fonte(conteudo, fontes_com_texto)
            sem_cit = geracao.resposta_sem_citacao(conteudo, fontes_com_texto)
        elif not fontes:
            valores = geracao.valores_sem_fonte(conteudo, [])
            sem_cit = not recusa
        else:
            valores = []
            nums = {int(n) for n in re.findall(r"\[(\d+)\]", conteudo) if 0 < int(n) <= len(fontes)}
            sem_cit = (not recusa) and (not nums)

    if valores:
        motivos.append(f"Valores sem respaldo nos trechos: {', '.join(valores)}")
    if sem_cit:
        motivos.append("Resposta afirmativa sem citação [n] (RN-02)")

    aprovado = not motivos
    return ResultadoValidacao(
        aprovado=aprovado,
        valores_sem_fonte=valores,
        sem_citacao=sem_cit,
        eh_recusa=recusa,
        motivos=motivos,
        acao_recomendada="aprovar" if aprovado else "devolver_ao_sintetizador",
    )


class AgenteValidador(Agente):
    """Agente ativo que audita fatos e citações, podendo aprovar ou reprovar para devolução."""

    nome = "Agente Validador"
    papel = "Validador factual e verificador de citações (RN-02 e RN-03)"

    def executar(self, mensagem: Mensagem) -> Resposta:
        contexto = mensagem.contexto if isinstance(mensagem.contexto, dict) else {}
        trechos = contexto.get("trechos")
        fontes = contexto.get("fontes") or []
        erro = contexto.get("erro")

        parecer = avaliar_validacao(
            conteudo=mensagem.conteudo,
            trechos=trechos,
            fontes=fontes,
            erro=erro,
        )
        contexto["validacao"] = asdict(parecer)
        return Resposta(
            conteudo="APROVADO" if parecer.aprovado else "REPROVADO",
            fontes=list(fontes),
            confianca=1.0 if parecer.aprovado else 0.0,
            alertas=list(parecer.motivos),
        )

    def validar(
        self,
        item: Any,
        trechos: list[dict] | None = None,
    ) -> ResultadoValidacao:
        """Executa o contrato do validador e devolve parecer estruturado `ResultadoValidacao`."""
        if isinstance(item, Resposta):
            msg = Mensagem(
                remetente="Orquestrador",
                destinatario=self.nome,
                conteudo=item.conteudo,
                contexto={"trechos": trechos, "fontes": item.fontes},
            )
        else:
            msg = Mensagem(
                remetente="Orquestrador",
                destinatario=self.nome,
                conteudo=item.resposta,
                contexto={
                    "agente": item.agente,
                    "subpergunta": item.subpergunta,
                    "trechos": trechos if trechos is not None else item.trechos_recuperados,
                    "fontes": item.fontes_citadas,
                    "erro": item.erro,
                },
            )
        self.executar(msg)
        return ResultadoValidacao(**msg.contexto["validacao"])
