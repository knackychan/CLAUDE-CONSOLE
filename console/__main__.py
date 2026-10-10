"""py -m console          open the window (service runs inside it)
py -m console --serve  service only; open http://127.0.0.1:47770/ in a browser"""
import argparse
import json
import sys
import threading
import urllib.request

from . import events, paths, runs, server


def already_running(port: int) -> bool:
    """True when our own service answers on the port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            return json.loads(resp.read()).get("app") == server.APP_ID
    except (OSError, ValueError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="console")
    parser.add_argument("--serve", action="store_true", help="service only, no window")
    args = parser.parse_args(argv)

    if sys.stderr is None:  # started with pythonw (run.bat): keep errors readable
        paths.home().mkdir(parents=True, exist_ok=True)
        sys.stderr = open(paths.home() / "window-errors.log", "a", encoding="utf-8")
    cfg = paths.ensure_config()
    events.prune(paths.home(), cfg["retention_days"])
    runs.prune(paths.home(), cfg["retention_days"])
    port = cfg["port"]
    url = f"http://127.0.0.1:{port}/"

    httpd = None
    try:
        httpd, hub = server.make_server(cfg)
    except OSError:
        if not already_running(port):
            print(f"port {port} is used by another program; set another \"port\" in "
                  f"{paths.home() / 'config.json'}", file=sys.stderr)
            return 1
    if httpd:
        hub.start()
        threading.Thread(target=httpd.serve_forever, name="cc-http", daemon=True).start()

    if args.serve:
        if not httpd:
            print(f"already running: {url}")
            return 0
        print(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            return 0

    import webview  # imported late: --serve works without pywebview
    webview.create_window("Claude Console", url, width=420, height=640,
                          min_size=(360, 400), on_top=True)
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
