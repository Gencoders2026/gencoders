"""
Pytest configuration for the Task 6 support-assistance tests.

The Task 6 modules use flat imports (`import analysis_core`,
`from support_assist import ...`), exactly like the other agents in
this project. This file makes sure the folder itself is importable no
matter which directory pytest is started from.
"""

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent

if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
