from __future__ import annotations

import threading
import webbrowser

from waitress import serve

from instruction_app import create_app


def open_browser() -> None:
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    application = create_app()
    threading.Timer(1.2, open_browser).start()
    serve(application, host="127.0.0.1", port=5000, threads=4)
