from __future__ import annotations

import logging
import os
import socket
import threading
import time
import webbrowser

from waitress import create_server

from app import app
from runtime_paths import prepare_data_paths


HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def server_is_running() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.35):
            return True
    except OSError:
        return False


def open_browser_when_ready() -> None:
    for _ in range(80):
        if server_is_running():
            webbrowser.open(URL)
            return
        time.sleep(0.1)


def configure_logging() -> None:
    paths = prepare_data_paths()
    paths["logs"].mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=paths["logs"] / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    if server_is_running():
        if os.environ.get("SIM_FIELD_SELECTOR_NO_BROWSER") != "1":
            webbrowser.open(URL)
        return
    configure_logging()
    if os.environ.get("SIM_FIELD_SELECTOR_NO_BROWSER") != "1":
        threading.Thread(target=open_browser_when_ready, daemon=True).start()
    server = create_server(app, host=HOST, port=PORT, threads=4)
    server.run()


if __name__ == "__main__":
    main()
