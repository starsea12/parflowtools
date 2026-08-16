#!/usr/bin/env python
"""兼容入口：实际掩膜逻辑统一由 concnshare.generate_mask 提供。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from concnshare.generate_mask import generate_mask, main  # noqa: E402,F401


if __name__ == "__main__":
    main()
