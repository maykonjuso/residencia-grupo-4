"""Utilitários compartilhados de normalização textual e dias da semana."""
from __future__ import annotations

import re
import unicodedata

DIAS_SEMANA: tuple[str, ...] = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def sem_acentos(texto: str) -> str:
    """Converte para minúsculas removendo acentos e diacríticos combinantes."""
    decomp = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in decomp if not unicodedata.combining(c))


def normalizar_texto(texto: str) -> str:
    """Remove acentos, normaliza caixa e colapsa espaços em branco."""
    return " ".join(sem_acentos(texto).split())


def slugify(texto: str, padrao: str = "item") -> str:
    """Gera slug ASCII em minúsculas separado por hífens."""
    limpo = re.sub(r"[^a-z0-9]+", "-", normalizar_texto(texto)).strip("-")
    return limpo or padrao
