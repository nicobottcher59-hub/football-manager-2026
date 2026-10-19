from __future__ import annotations


def main() -> None:
    try:
        from .app import run
    except ImportError as exc:
        if exc.name == "tkinter":
            raise SystemExit(
                "Tkinter is not available in this Python installation. Install Python with Tcl/Tk support and retry."
            ) from exc
        raise
    run()


if __name__ == "__main__":
    main()
