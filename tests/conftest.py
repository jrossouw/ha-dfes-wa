"""Load the pure-Python parser without importing Home Assistant."""

import importlib.util
import pathlib
import sys
import types

PKG_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "dfes_wa"

pkg = types.ModuleType("dfes_wa")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["dfes_wa"] = pkg

for name in ("const", "feed"):
    spec = importlib.util.spec_from_file_location(f"dfes_wa.{name}", PKG_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"dfes_wa.{name}"] = mod
    spec.loader.exec_module(mod)
