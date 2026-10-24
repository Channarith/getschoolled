"""python3 -m tts_bakeoff.voice_clone.enroll_ui --root ~/voices [--port 8780]"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import serve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m tts_bakeoff.voice_clone.enroll_ui", description=__doc__)
    ap.add_argument("--root", default=os.environ.get("GS_VOICES_DIR") or str(Path.home() / "voices"),
                    help="where consent records and samples live (default ~/voices; never commit it)")
    ap.add_argument("--port", type=int, default=8780)
    args = ap.parse_args(argv)
    root = Path(args.root).expanduser()
    os.environ["GS_VOICES_DIR"] = str(root)
    srv = serve(root, args.port)
    port = srv.server_address[1]
    print(f"voice enrollment: http://localhost:{port}/   voices in {root}   (Ctrl-C to stop)", flush=True)
    print(f"on a remote box, from your laptop: ssh -L {port}:127.0.0.1:{port} <host>  then open http://localhost:{port}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
