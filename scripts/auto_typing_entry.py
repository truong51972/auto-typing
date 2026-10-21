"""PyInstaller entry point; import the package rather than running a relative-import module."""

from auto_typing.main import main


if __name__ == "__main__":
    raise SystemExit(main())
