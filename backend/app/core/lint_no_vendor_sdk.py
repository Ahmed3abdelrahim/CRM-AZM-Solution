"""Import-lint enforcing constitution Principle VIII / PLAN.md C8: no module besides
app/ai/litellm_wrapper.py may import an LLM vendor SDK/HTTP client for LLM use.

Run as: python -m app.core.lint_no_vendor_sdk
"""

import ast
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
ALLOWED_MODULE = APP_DIR / "ai" / "litellm_wrapper.py"

# Vendor SDKs/HTTP clients whose direct import is banned outside the wrapper. "litellm" itself
# is the gateway, not a vendor SDK, and is exempt.
BANNED_IMPORTS = {
    "openai",
    "anthropic",
    "google.generativeai",
    "cohere",
    "together",
    "replicate",
}


def _iter_python_files() -> list[Path]:
    return [p for p in APP_DIR.rglob("*.py") if p.resolve() != ALLOWED_MODULE]


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def check() -> list[str]:
    violations: list[str] = []
    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_names(tree):
            root = imported.split(".")[0]
            if imported in BANNED_IMPORTS or root in BANNED_IMPORTS:
                violations.append(f"{path.relative_to(APP_DIR.parent)}: imports banned vendor SDK '{imported}'")
    return violations


def main() -> int:
    violations = check()
    if violations:
        print("lint_no_vendor_sdk: FAILED")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("lint_no_vendor_sdk: OK — no vendor SDK imports outside app/ai/litellm_wrapper.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
