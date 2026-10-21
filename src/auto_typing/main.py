"""Desktop entry point."""

import sys

from PySide6.QtWidgets import QApplication

from .ui import MainWindow


def main() -> int:
    if "--smoke-test" in sys.argv:
        # Used by Windows packaging CI to verify the frozen GUI starts without
        # entering the normal event loop or sending any keyboard input.
        app = QApplication([sys.argv[0]])
        window = MainWindow()
        window.show()
        app.processEvents()
        if not window.isVisible():
            raise RuntimeError("Bundled window failed to open")
        if window.interval.value() != 10 or window.hold.value() != 5:
            raise RuntimeError("Bundled application has incorrect timing defaults")
        window.close()
        return 0

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
