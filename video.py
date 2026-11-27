"""Tabrik videosi — saytdagi «Tabrik videosini yuklab oliş» bilan aynan bir xil.

Sayt (gh-pages worktree) lokal serverda oçiladi, sahna kadrma-kadr (30 fps) çiziladi va
ffmpeg bilan musiqa qöşilib MP4 (H.264 + AAC) qilinadi. Hamma narsa vaqtinçalik papkada.
"""
import base64
import functools
import http.server
import os
import subprocess
import tempfile
import threading
import time
import traceback

FPS = 30


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _serve(root):
    h = functools.partial(_Quiet, directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _browser(pw):
    for kw in ({"channel": "chrome"}, {}):
        try:
            return pw.chromium.launch(**kw)
        except Exception:
            continue
    raise RuntimeError("brauzer topilmadi")


def render(site_dir, n, entries=None, timeout=420):
    """-> MP4 baytlari. entries: barça taşakkurnomalar röyxati (yangisi bilan) — izoh va unvon raqami şundan hisoblanadi."""
    from playwright.sync_api import sync_playwright
    t0 = time.time()
    srv = _serve(site_dir)
    tmp = tempfile.mkdtemp(prefix="kunvid_")
    out = os.path.join(tmp, "v.mp4")
    try:
        with sync_playwright() as pw:
            b = _browser(pw)
            p = b.new_page(viewport={"width": 420, "height": 800})
            p.goto(f"http://127.0.0.1:{srv.server_address[1]}/?galereya=1", wait_until="networkidle")
            p.wait_for_function("typeof window.__kunScene === 'function' && Array.isArray(DATA)", timeout=30000)
            if entries:
                p.evaluate("""(e) => { DATA.length = 0; DATA.push(...e); izohlar(); }""", entries)
            dur = p.evaluate("(n) => window.__kunScene(n)", int(n))
            music = p.evaluate("() => window.__kunMusic || 'assets/taqdirlov.mp3'").split("?")[0]
            total = int(round(dur * FPS))
            ff = subprocess.Popen(
                [_ffmpeg(), "-y", "-loglevel", "error",
                 "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                 "-stream_loop", "-1", "-i", os.path.join(site_dir, *music.split("/")),
                 "-map", "0:v", "-map", "1:a", "-t", str(dur),
                 "-af", f"afade=t=out:st={dur - 2.2}:d=2.2",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out],
                stdin=subprocess.PIPE)
            BATCH = 15
            for i in range(0, total, BATCH):
                if time.time() - t0 > timeout:
                    raise TimeoutError("video juda uzoq çizildi")
                frames = p.evaluate(
                    "([a, b, fps]) => { const r = []; for (let i = a; i < b; i++) r.push(window.__kunFrame(i / fps)); return r; }",
                    [i, min(total, i + BATCH), FPS])
                for f in frames:
                    ff.stdin.write(base64.b64decode(f.split(",", 1)[1]))
            ff.stdin.close()
            if ff.wait(timeout=120) != 0:
                raise RuntimeError("ffmpeg xatosi")
            b.close()
        with open(out, "rb") as fh:
            data = fh.read()
        print(f"video #{n}: {len(data) // 1024} KB, {time.time() - t0:.0f} s", flush=True)
        return data
    finally:
        srv.shutdown()
        try:
            for f in os.listdir(tmp):
                os.remove(os.path.join(tmp, f))
            os.rmdir(tmp)
        except Exception:
            traceback.print_exc()
