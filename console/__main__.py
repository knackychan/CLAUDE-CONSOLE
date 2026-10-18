"""py -m console          the tray icon (service inside); it opens the window as its own process
py -m console --window the window only, for a running service (what the tray starts)
py -m console --serve  service only; open http://127.0.0.1:47770/ in a browser"""
import argparse
import json
import sys
import threading
import urllib.error
import urllib.request

from . import events, kinds, paths, prep, runs, server, tasks


def already_running(port: int) -> bool:
    """True when our own service answers on the port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            return json.loads(resp.read()).get("app") == server.APP_ID
    except (OSError, ValueError):
        return False


def log_harnesses(hub) -> None:
    """One line in console.log once the start probe is done: which harnesses were found, with their versions."""
    hub.probing.join()
    found = hub.harnesses()
    hub._log("harnesses: " + ", ".join(
        f"{name} {'on' if h['on'] else 'off'}" + (f" {h['version'] or 'found'}" if h["found"] else " not found" if h["on"] else "")
        for name, h in found.items()))


def replay_supervisor_cli(pair) -> int:
    """The --supervisor-replay branch: one guarded local request to the already running service. No Hub, no probe,
    no model call in this process; the service remains the single admission owner."""
    task, wake = pair
    if not tasks.safe_id(task):
        print("task must be a task id", file=sys.stderr)
        return 2
    if not wake.isdigit() or int(wake) < 1:
        print("wake must be a positive whole number", file=sys.stderr)
        return 2
    wake = int(wake)
    cfg = paths.load_config()
    port = cfg["port"]
    if not already_running(port):
        print("Start the Console service before replay", file=sys.stderr)
        return 1
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/task/supervisor/replay",
                                 data=json.dumps({"task": task, "wake": wake}).encode("utf-8"),
                                 headers={"X-CC": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=cfg["supervisor_timeout_s"] + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            data = {"error": f"HTTP {exc.code}"}
        print(json.dumps(data, ensure_ascii=False), file=sys.stdout)
        return 1
    except OSError as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="console")
    parser.add_argument("--serve", action="store_true", help="service only, no window")
    parser.add_argument("--window", action="store_true", help="the window only, for a running service")
    parser.add_argument("--supervisor-replay", nargs=2, metavar=("TASK", "WAKE"),
                        help="dry-run replay of one supervisor wake through the running service")
    args = parser.parse_args(argv)

    if sys.stderr is None:  # started with pythonw (run.bat): keep errors readable
        paths.home().mkdir(parents=True, exist_ok=True)
        sys.stderr = open(paths.home() / "window-errors.log", "a", encoding="utf-8")
    if args.supervisor_replay:
        if args.serve or args.window:
            print("--supervisor-replay cannot be combined with --serve or --window", file=sys.stderr)
            return 2
        return replay_supervisor_cli(args.supervisor_replay)
    cfg = paths.ensure_config()
    port = cfg["port"]
    url = f"http://127.0.0.1:{port}/"
    if args.window:
        if not already_running(port):
            print(f"no service on port {port}: start it with py -m console", file=sys.stderr)
            return 1
        return open_window(url)
    events.prune(paths.home(), cfg["retention_days"])
    runs.prune(paths.home(), cfg["retention_days"])
    tasks.prune(paths.home(), cfg["task_retention_days"])  # plan 28: 0 (the default) keeps every task folder
    kinds.ensure(paths.home())  # plan 28: the kind files the console runs with, seeded once, then Fred's to edit
    prep.prune_orphans(paths.home())  # plan 29: the folders of prompts never run, after prep.ORPHAN_DAYS

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
        threading.Thread(target=log_harnesses, args=(hub,), name="cc-harness-log", daemon=True).start()
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

    if not httpd:  # a tray already runs: show a window for it
        return open_window(url)
    from . import tray
    tray.Tray(hub).run()  # until Quit in the tray menu
    hub.stop()
    httpd.shutdown()
    return 0


def open_window(url: str) -> int:
    """The pywebview window, a client of the service; closing it ends this process and frees WebView2."""
    import webview  # imported late: --serve and the tray work without pywebview
    from . import icon, window
    window.set_app_id()
    api = window.WindowApi(paths.home())
    x, y = api._place()
    # Not transparent: a WinForms form cannot be, its corners showed grey. Windows 11 rounds it instead
    # (window.round_corners) and the background matches the page.
    win = webview.create_window(window.TITLE, url, js_api=api, width=api.open_size()[0],
                                height=api.open_size()[1], x=x, y=y, min_size=(window.OPEN_MIN_W, window.PILL_H), frameless=True,
                                easy_drag=False, background_color=window.BACKGROUND, on_top=api.state()["on_top"])
    api._attach(win)
    win.events.closing += api._remember_place
    webview.start(api._restore, icon=str(icon.ICO))  # pywebview's WinForms form loads it as its Icon
    return 0


if __name__ == "__main__":
    sys.exit(main())
