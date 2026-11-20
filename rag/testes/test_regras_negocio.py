"""Testes das regras de negócio do RUmo (docs/entrega-1/regras-de-negocio.md).
Redireciona para test_rn.py.
"""
import sys
from pathlib import Path
import unittest

_TESTES = Path(__file__).resolve().parent
if str(_TESTES) not in sys.path:
    sys.path.insert(0, str(_TESTES))

from test_rn import *  # noqa: F401, F403, E402

if __name__ == "__main__":
    unittest.main()
