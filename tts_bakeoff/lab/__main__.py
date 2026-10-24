"""python3 -m tts_bakeoff.lab --out runs/2026-10-24 | --demo | --export DIR"""
from __future__ import annotations

import argparse
import sys
import tempfile
import webbrowser
from pathlib import Path

from . import export_standalone, serve
from .demo import make_demo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m tts_bakeoff.lab", description=__doc__)
    ap.add_argument("--out", help="bake-off run folder (OUT/<model>/<lang>/<id>.wav, manifest.jsonl, scores.jsonl)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="do not open the browser")
    ap.add_argument("--demo", action="store_true", help="generate a synthetic 3-voice run in a temp folder and serve it")
    ap.add_argument("--export", metavar="DIR", help="write a standalone copy of the page (opens from disk) and exit")
    args = ap.parse_args(argv)

    if args.export:
        dest = export_standalone(Path(args.export))
        print(f"wrote {dest}/index.html: open it in a browser and use 'Open run folder'")
        return 0
    if args.demo:
        out = make_demo(Path(tempfile.mkdtemp(prefix="tts-lab-demo-")))
        print(f"demo run written to {out}")
    elif args.out:
        out = Path(args.out)
        if not out.is_dir():
            print(f"not a folder: {out}", file=sys.stderr)
            return 2
    else:
        out = None  # empty lab: load folders or drop files in the page
    srv = serve(out, args.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"listening lab: {url}   (Ctrl-C to stop)", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
