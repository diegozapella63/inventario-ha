"""Cobertura só com a biblioteca padrão (sys.monitoring, Python 3.12+): grava as linhas executadas dos arquivos em INV_COV_SRC."""
import os, sys

_out = os.environ.get("INV_COV_DIR")
_src = os.environ.get("INV_COV_SRC")
if _out and _src and hasattr(sys, "monitoring"):
    import atexit, json, signal, threading
    mon = sys.monitoring
    _tool = mon.COVERAGE_ID
    mon.use_tool_id(_tool, "inv-cov")
    _hits = {}
    _keep = {}

    def _line(code, line):
        f = code.co_filename
        ok = _keep.get(f)
        if ok is None:
            ok = _keep[f] = os.path.abspath(f).startswith(_src)
        if ok:
            _hits.setdefault(f, set()).add(line)
        return mon.DISABLE

    mon.register_callback(_tool, mon.events.LINE, _line)
    mon.set_events(_tool, mon.events.LINE)
    _done = threading.Lock()

    def _dump():
        if not _done.acquire(blocking=False):
            return
        os.makedirs(_out, exist_ok=True)
        with open(os.path.join(_out, f"{os.getpid()}-{os.urandom(3).hex()}.json"), "w") as fh:
            json.dump({os.path.abspath(k): sorted(v) for k, v in list(_hits.items())}, fh)

    atexit.register(_dump)

    def _term(sig, frm):
        _dump()
        os._exit(0)

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _term)
