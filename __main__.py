"""
adopt module entrypoint.
"""
from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from adopt.main import main
except ImportError:
    from main import main

if __name__ == "__main__":
    main()
