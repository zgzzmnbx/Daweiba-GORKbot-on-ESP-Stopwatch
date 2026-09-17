"""Run PlatformIO Core in the project's isolated Python environment.

The bundled Python 3.14 runtime on this host blocks in ``platform.system()``
and ``platform.platform()``.  PlatformIO 6.1.18 calls those functions while
initialising its diagnostics/telemetry modules, so the wrapper supplies the
stable Windows values that PlatformIO itself already expects from
``PLATFORMIO_SYSTEM_TYPE``.  It does not change PlatformIO or project source.
"""

from __future__ import annotations

import os
import platform
import sys


os.environ.setdefault("PLATFORMIO_SYSTEM_TYPE", "windows_amd64")
os.environ.setdefault("PLATFORMIO_SETTING_ENABLE_TELEMETRY", "false")
os.environ.setdefault("PLATFORMIO_DISABLE_PROGRESSBAR", "true")
os.environ.setdefault("PLATFORMIO_NO_ANSI", "true")

# Keep PlatformIO's host probes deterministic on this Python 3.14 runtime.
platform.system = lambda: "Windows"
platform.machine = lambda: "AMD64"
platform.platform = lambda: "Windows-10"
platform.architecture = lambda: ("64bit", "")

from platformio.__main__ import main  # noqa: E402


raise SystemExit(main())
