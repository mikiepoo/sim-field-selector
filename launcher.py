from __future__ import annotations

import logging
import os
import socket
import threading
import time

import webview
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


def wait_for_server() -> bool:
    for _ in range(80):
        if server_is_running():
            return True
        time.sleep(0.1)
    return False


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
        if os.environ.get("SIM_FIELD_SELECTOR_NO_BROWSER") == "1":
            return
        window = webview.create_window(
            "IROC Challenge Series - Sim Field Selector",
            URL,
            width=1280,
            height=850,
            min_size=(900, 650),
            background_color="#101010",
        )
        webview.start(private_mode=True)
        return

    configure_logging()
    server = create_server(app, host=HOST, port=PORT, threads=4)
    if os.environ.get("SIM_FIELD_SELECTOR_NO_BROWSER") == "1":
        server.run()
        return

    server_thread = threading.Thread(target=server.run, name="local-web-server", daemon=True)
    server_thread.start()
    if not wait_for_server():
        raise RuntimeError("The local Sim Field Selector server did not start")

    window = webview.create_window(
        "IROC Challenge Series - Sim Field Selector",
        URL,
        width=1280,
        height=850,
        min_size=(900, 650),
        background_color="#101010",
    )

    def close_window_from_page() -> None:
        threading.Timer(0.4, window.destroy).start()

    app.config["EXIT_CALLBACK"] = close_window_from_page
    try:
        webview.start(private_mode=True)
    finally:
        server.close()
        server.task_dispatcher.shutdown(timeout=2)
        server_thread.join(timeout=2)


if __name__ == "__main__":
    main()
