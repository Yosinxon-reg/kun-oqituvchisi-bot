"""Veb-sahifa (GitHub Pages, gh-pages şoxobçasi): har bir taşakkurnoma avtomatik joylanadi.

_site/ — gh-pages şoxobçasining nusxasi (git worktree). Bot faqat c/ va data/ ni yangilaydi;
index.html va assets/ qölda joylanadi.
"""
import io
import json
import os
import subprocess
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.environ.get("SITE_DIR") or os.path.join(HERE, "_site")
_ready = [None]
_last_push = [0.0]
_dirty = [False]


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd or HERE, capture_output=True, text=True)


def ready(git_sync):
    """gh-pages worktree tayyorlaş (bir marta)."""
    if _ready[0] is not None:
        return _ready[0]
    ok = True
    if git_sync and not os.path.isdir(os.path.join(DIR, ".git")) and not os.path.isfile(os.path.join(DIR, ".git")):
        git("fetch", "-q", "origin", "+refs/heads/gh-pages:refs/remotes/origin/gh-pages")
        r = git("worktree", "add", "-f", "-B", "gh-pages", DIR, "origin/gh-pages")
        ok = r.returncode == 0
        if not ok:
            print("site worktree xato:", r.stderr, flush=True)
    os.makedirs(os.path.join(DIR, "c"), exist_ok=True)
    os.makedirs(os.path.join(DIR, "data"), exist_ok=True)
    _ready[0] = ok
    return ok


def put_image(n, jpg_bytes):
    """Taşakkurnoma rasmi: veb (1600 px) va kiçik (480 px)."""
    im = Image.open(io.BytesIO(jpg_bytes)).convert("RGB")
    big = im.resize((1600, round(1600 * im.height / im.width)), Image.LANCZOS)
    big.save(os.path.join(DIR, "c", f"{n:04d}.jpg"), "JPEG", quality=86, optimize=True, progressive=True)
    sm = im.resize((480, round(480 * im.height / im.width)), Image.LANCZOS)
    sm.save(os.path.join(DIR, "c", f"{n:04d}_t.jpg"), "JPEG", quality=80, optimize=True, progressive=True)
    _dirty[0] = True


def has_image(n):
    return os.path.exists(os.path.join(DIR, "c", f"{n:04d}.jpg"))


def write_index(entries):
    path = os.path.join(DIR, "data", "certs.json")
    data = {"yangilandi": time.strftime("%Y-%m-%dT%H:%M:%S"), "certs": entries}
    old = None
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8")).get("certs")
        except Exception:
            old = None
    if old != entries:
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        _dirty[0] = True


def push(git_sync, force=False):
    """Özgarişlarni gh-pages ga yuboriş (kamida 60 soniyada bir marta)."""
    if not git_sync or not _dirty[0] or not _ready[0]:
        return False
    if not force and time.time() - _last_push[0] < 60:
        return False
    _last_push[0] = time.time()
    git("add", "-A", "c", "data", cwd=DIR)
    if git("commit", "-q", "-m", "taşakkurnomalar yangilandi", cwd=DIR).returncode != 0:
        _dirty[0] = False
        return False
    for _ in range(3):
        if git("push", "-q", "origin", "gh-pages", cwd=DIR).returncode == 0:
            _dirty[0] = False
            return True
        git("pull", "-q", "--rebase", "-X", "ours", "origin", "gh-pages", cwd=DIR)
    return False
