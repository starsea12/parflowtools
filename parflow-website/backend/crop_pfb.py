#!/usr/bin/env python
"""兼容入口：实际 PFB 裁剪逻辑统一由 concnshare.crop_pfb 提供。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from concnshare.crop_pfb import crop_pfb, main  # noqa: E402,F401


if __name__ == "__main__":
    main()
