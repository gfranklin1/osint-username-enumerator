"""Optional Textual-based TUI for AliasGraph.

Install with `pip install -e '.[tui]'`. The CLI (`aliasgraph scan ...`) is
unaffected — this package is opt-in and the rest of aliasgraph does not
import from it.
"""
from __future__ import annotations

__all__ = ["run_tui"]


def run_tui() -> None:
    """Launch the TUI. Imported lazily so the textual dep is only required here."""
    from aliasgraph.tui.app import AliasGraphApp

    AliasGraphApp().run()
