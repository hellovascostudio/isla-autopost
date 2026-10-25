"""Render an Isla Kerrow Reel (1080x1920 MP4) from a post.json with "type": "reel".

A reel is a real excerpt from a book, read by a British AI voice, over moody background video,
with burned-in subtitles and an end card with the cover.

post.json fields (besides publish_at / pillar / caption):
    type     : "reel"
    book     : book title, e.g. "Under the Lining"
    cover    : path to the cover, e.g. assets/covers/under-the-lining.jpg
    hook     : opening line shown on screen for the first seconds (our words, not a quote)
    excerpt  : list of lines, VERBATIM from the book. A line is a string, or
               {"text": "...", "pause": 1.2, "sfx": "ring"}  (pause in seconds after the line;
               sfx "ring" = a soft electronic telephone trill during that pause)
    voice    : edge-tts voice (default en-GB-SoniaNeural)
    rate     : speaking rate (default "-6%")
    scenes   : animated, hand-drawn scenes that follow the excerpt (see scripts/scenes.py) — preferred
    stock    : instead of scenes: Pexels search terms for background clips (needs PEXELS_API_KEY);
               without scenes, key or results the background is a slow, dark, blurred cover
    end      : {"kicker": "Out now", "title": "...", "body": "..."}  end card text

Output in the post folder: reel.mp4 and thumb.jpg (cover frame for the PR and Instagram).

Usage:
    python scripts/reel.py posts/queue/2026-10-29-under-the-lining   # one reel
    python scripts/reel.py --all        # every reel in queue/ without reel.mp4
    python scripts/reel.py --all --force

Env:
    PEXELS_API_KEY   optional, free key from pexels.com/api
    REEL_FAKE_TTS=1  local test without network: silence instead of a voice
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import BRAND, C, ROOT, block, draw_lines, font, red_line, spaced  # noqa: E402

W, H = 1080, 1920
FPS = 30
MARGIN = 90
LEAD_IN = 0.9        # seconds before the voice starts
GAP = 0.35           # default pause between lines
END_CARD = 4.5       # seconds
SUB_Y = 1180         # top of the subtitle area (stays clear of the Reels UI at the bottom)
HOOK_UNTIL = 4.2     # hook text visible until (seconds)
FAKE = os.environ.get("REEL_FAKE_TTS") == "1"
PEXELS = os.environ.get("PEXELS_API_KEY", "")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{' '.join(map(str, cmd))[:600]}\n{r.stderr[-2500:]}")
    return r.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.strip())


def clean(text):
    """Fonts have no emoji glyphs."""
    return "".join(ch for ch in text if ord(ch) < 0x2190).strip()


# ---------- voice ----------

async def _tts(text, voice, rate, path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def speak(text, voice, rate, path):
    if FAKE:
        secs = max(1.0, len(text.split()) / 2.5)
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{secs:.2f}", str(path)])
    else:
        for attempt in range(3):
            try:
                asyncio.run(_tts(text, voice, rate, path))
                break
            except Exception as e:  # network hiccup: retry
                if attempt == 2:
                    sys.exit(f"edge-tts failed: {e}")
    return duration(path)


# ---------- subtitles ----------

WEAK_END = {"the", "a", "an", "of", "to", "in", "on", "at", "and", "with", "her", "his", "my", "that", "for",
            "from", "into", "as", "if", "by", "was", "were", "had", "it", "be", "but", "or", "so"}


def chunks(text, max_chars=38):
    """Split a line into short, natural subtitle phrases: break after sentence punctuation,
    otherwise at a comma or before a weak word, and never end a phrase on 'the', 'of' …"""
    out = []
    for sent in re.split(r"(?<=[.?!:])\s+", text.strip()):
        words = sent.split()
        while words:
            if len(" ".join(words)) <= max_chars:
                out.append(" ".join(words))
                break
            best, best_score = 1, -1e9
            for k in range(1, len(words)):
                part = " ".join(words[:k])
                if len(part) > max_chars:
                    break
                rest = len(" ".join(words[k:]))
                score = len(part) / max_chars                       # longer is better
                if re.search(r"[,;’']$", words[k - 1]):
                    score += 0.6                                    # break after a comma
                if words[k - 1].lower().strip(",") in WEAK_END:
                    score -= 1.0                                    # don't end on 'the'
                if rest < 12:
                    score -= 0.8                                    # avoid a tiny orphan
                if score > best_score:
                    best, best_score = k, score
            out.append(" ".join(words[:best]))
            words = words[best:]
    return out


def text_png(path, text, kind="sans_bold", size=62, max_w=W - 2 * MARGIN, y=SUB_Y, color=None, max_h=360):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fnt, lines, lh, h = block(d, text, kind, size, max_w, max_h, spacing=1.22)
    # soft dark halo behind the text for legibility on any footage
    halo = Image.new("L", (W, H), 0)
    hd = ImageDraw.Draw(halo)
    yy = y
    for ln in lines:
        lw = d.textlength(ln, font=fnt)
        x = (W - lw) / 2
        hd.rectangle([x - 26, yy - 8, x + lw + 26, yy + lh + 4], fill=150)
        yy += lh
    halo = halo.filter(ImageFilter.GaussianBlur(22))
    img.paste(Image.new("RGBA", (W, H), (6, 8, 14, 255)), (0, 0), halo)
    d = ImageDraw.Draw(img)
    draw_lines(d, lines, fnt, lh, MARGIN, y, color or C["text"], align="center", width=W - 2 * MARGIN)
    img.save(path)


def hook_png(path, post):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    halo = Image.new("L", (W, H), 0)
    ImageDraw.Draw(halo).rectangle([0, 300, W, 940], fill=150)
    img.paste(Image.new("RGBA", (W, H), (6, 8, 14, 255)), (0, 0), halo.filter(ImageFilter.GaussianBlur(80)))
    d = ImageDraw.Draw(img)
    y = 400
    spaced(d, (MARGIN, y), f"FROM {post['book'].upper()}", font("sans_bold", 28), C["accent"], tracking=6)
    y += 80
    fnt, lines, lh, h = block(d, clean(post["hook"]), "display", 92, W - 2 * MARGIN, 420, spacing=1.08)
    y = draw_lines(d, lines, fnt, lh, MARGIN, y, C["text"]) + 34
    red_line(d, MARGIN, y)
    img.save(path)


def handle_png(path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    spaced(d, (MARGIN, 150), BRAND["handle"].upper(), font("sans", 24), C["muted"], tracking=3)
    img.save(path)


def end_png(path, post):
    end = post.get("end", {})
    img = Image.new("RGB", (W, H), C["background"])
    d = ImageDraw.Draw(img)
    cover = Image.open(ROOT / post["cover"]).convert("RGB")
    cover.thumbnail((640, 1000), Image.LANCZOS)
    cw, ch = cover.size
    x, y = (W - cw) // 2, 260
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rectangle([x + 16, y + 26, x + cw + 16, y + ch + 26], fill=180)
    img.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(30)))
    img.paste(cover, (x, y))
    ty = y + ch + 80
    if end.get("kicker"):
        spaced(d, (MARGIN, ty), end["kicker"].upper(), font("sans_bold", 28), C["accent"], tracking=6,
               center_w=W - 2 * MARGIN)
        ty += 66
    fnt, lines, lh, h = block(d, clean(end.get("title", post["book"])), "display", 76, W - 2 * MARGIN, 200)
    ty = draw_lines(d, lines, fnt, lh, MARGIN, ty, C["text"], align="center", width=W - 2 * MARGIN) + 24
    red_line(d, W // 2 - 45, ty)
    ty += 46
    if end.get("body"):
        fnt, lines, lh, h = block(d, clean(end["body"]), "sans", 38, W - 2 * MARGIN, 200, spacing=1.4)
        draw_lines(d, lines, fnt, lh, MARGIN, ty, C["muted"], align="center", width=W - 2 * MARGIN)
    spaced(d, (MARGIN, H - 200), BRAND["handle"].upper(), font("sans", 24), C["muted"], tracking=3,
           center_w=W - 2 * MARGIN)
    img.save(path)


# ---------- background ----------

def pexels_clips(terms, tmp, need):
    if not PEXELS:
        return []
    got, seen = [], set()
    for term in terms:
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": term, "orientation": "portrait", "size": "medium", "per_page": 8})
        req = urllib.request.Request(url, headers={"Authorization": PEXELS, "User-Agent": "isla-autopost"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                videos = json.loads(r.read()).get("videos", [])
        except Exception as e:
            print(f"  pexels '{term}': {e}")
            continue
        for v in videos:
            if v["id"] in seen or v.get("duration", 0) < 4:
                continue
            files = [f for f in v["video_files"] if f.get("height") and f.get("width")
                     and f["height"] > f["width"] and f["width"] >= 720 and f.get("file_type") == "video/mp4"]
            if not files:
                continue
            f = min(files, key=lambda f: abs(f["width"] - 1080))
            dest = tmp / f"pexels-{v['id']}.mp4"
            req = urllib.request.Request(f["link"], headers={"User-Agent": "isla-autopost"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    dest.write_bytes(r.read())
            except Exception as e:
                print(f"  pexels download {v['id']}: {e}")
                continue
            seen.add(v["id"])
            got.append(dest)
            print(f"  clip '{term}': pexels.com/video/{v['id']}")
            break
        if len(got) >= need:
            break
    return got


GRADE = ("eq=saturation=0.45:brightness=-0.10:contrast=1.08,"
         "colorbalance=rs=-0.04:bs=0.07:rm=-0.02:bm=0.04,"
         "noise=alls=7:allf=t,vignette=PI/4")


def scene_background(post, total, tmp, ev):
    from scenes import build
    frame = build(post["scenes"], ev, total)
    out = tmp / "bg.mp4"
    n = int(round(total * FPS))
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-vf", "noise=alls=6:allf=t,vignette=PI/4.5,format=yuv420p",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ffmpeg failed while encoding scenes")
    return out, "scenes"


def background(post, total, tmp, ev=None):
    if post.get("scenes"):
        return scene_background(post, total, tmp, ev)
    terms = post.get("stock", [])
    seg_target = 5.5
    need = max(1, min(len(terms), round(total / seg_target))) if terms else 0
    clips = pexels_clips(terms, tmp, need) if need else []
    out = tmp / "bg.mp4"
    if clips:
        seg = total / len(clips)
        parts = []
        for i, c in enumerate(clips):
            p = tmp / f"seg{i}.mp4"
            fade = min(0.5, seg / 4)
            run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(c), "-t", f"{seg:.3f}", "-an",
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                        f"setpts=1.25*PTS,{GRADE},fade=t=in:st=0:d={fade:.2f},"
                        f"fade=t=out:st={seg - fade:.3f}:d={fade:.2f},format=yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(p)])
            parts.append(p)
        lst = tmp / "segs.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
        return out, "pexels"
    # mood fallback: the cover, heavily blurred into the navy, drifting slowly upwards
    cover = Image.open(ROOT / post["cover"]).convert("RGB")
    bw, bh = int(W * 1.12), int(H * 1.12)
    bg = ImageOps.fit(cover, (bw // 4, bh // 4), method=Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    bg = bg.resize((bw, bh), Image.BICUBIC).filter(ImageFilter.GaussianBlur(20))
    bg = Image.blend(bg, Image.new("RGB", bg.size, C["background"]), 0.62)
    bg.save(tmp / "mood.png")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{total:.2f}", "-i", str(tmp / "mood.png"),
         "-vf", f"crop={W}:{H}:x='(iw-{W})/2':y='(ih-{H})*(1-t/{total:.2f})',{GRADE},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
    return out, "mood"


# ---------- audio ----------

RING = ("aevalsrc='0.22*sin(2*PI*1400*t)*(0.55+0.45*sin(2*PI*20*t))"
        "*(lt(mod(t,2.2),0.4)+gte(mod(t,2.2),0.6)*lt(mod(t,2.2),1.0))':s=48000:d={d:.2f}")


# ---------- main ----------

def render_reel(folder):
    folder = Path(folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    voice = post.get("voice", "en-GB-SoniaNeural")
    rate = post.get("rate", "-6%")
    lines = [ln if isinstance(ln, dict) else {"text": ln} for ln in post["excerpt"]]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # 1. voice per line, build the timeline
        t, voice_parts, sfx_parts, subs, line_starts = LEAD_IN, [], [], [], []
        for i, ln in enumerate(lines):
            line_starts.append(t)
            mp3 = tmp / f"line{i:02d}.mp3"
            d = speak(ln["text"], voice, rate, mp3)
            voice_parts.append((mp3, t))
            pieces = chunks(clean(ln["text"]))
            total_chars = sum(len(p) for p in pieces)
            st, speech = t + 0.08, max(0.4, d - 0.25)
            for p in pieces:
                dur = speech * len(p) / total_chars
                subs.append((p, st, st + dur))
                st += dur
            t += d
            pause = float(ln.get("pause", GAP))
            if ln.get("sfx") == "ring":
                sfx_parts.append((t + 0.2, max(pause, 2.6)))
                pause = max(pause, 2.6) + 0.3
            t += pause
        end_start = t + 0.4
        total = end_start + END_CARD
        print(f"{folder.name}: {total:.1f}s, {len(lines)} lines, {len(subs)} subtitles")

        # 2. graphics
        hook_png(tmp / "hook.png", post)
        handle_png(tmp / "handle.png")
        end_png(tmp / "end.png", post)
        sub_files = []
        for i, (txt, a, b) in enumerate(subs):
            p = tmp / f"sub{i:03d}.png"
            text_png(p, txt)
            # subtitles stay until the next one starts, so they don't flicker between phrases
            nxt = subs[i + 1][1] if i + 1 < len(subs) else b
            sub_files.append((p, a, min(nxt, b + 0.6)))

        # 3. background
        bg, mode = background(post, total, tmp, {"lines": line_starts, "sfx": sfx_parts})
        print(f"  background: {mode}")

        # 4. compose video + audio
        inputs = ["-i", str(bg), "-i", str(tmp / "handle.png"),
                  "-loop", "1", "-framerate", str(FPS), "-t", f"{HOOK_UNTIL:.2f}", "-i", str(tmp / "hook.png"),
                  "-loop", "1", "-framerate", str(FPS), "-t", f"{END_CARD:.2f}", "-i", str(tmp / "end.png")]
        fv = [f"[2:v]format=rgba,fade=t=out:st={HOOK_UNTIL - 0.6:.2f}:d=0.6:alpha=1[hook]",
              f"[3:v]format=rgba,fade=t=in:st=0:d=0.7:alpha=1,setpts=PTS+{end_start:.3f}/TB[end]",
              "[0:v][1:v]overlay=0:0[v0]", "[v0][hook]overlay=0:0:eof_action=pass[v1]"]
        last, n = "v1", 4
        for i, (p, a, b) in enumerate(sub_files):
            inputs += ["-i", str(p)]
            fv.append(f"[{last}][{n}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[s{i}]")
            last, n = f"s{i}", n + 1
        fv.append(f"[{last}][end]overlay=0:0:eof_action=pass,format=yuv420p[vout]")

        fa, mix = [], []
        for i, (mp3, st) in enumerate(voice_parts):
            inputs += ["-i", str(mp3)]
            ms = int(st * 1000)
            fa.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{i}]")
            mix.append(f"[a{i}]")
            n += 1
        for j, (st, d) in enumerate(sfx_parts):
            ms = int(st * 1000)
            fa.append(RING.format(d=d) + f",afade=t=out:st={d - 0.3:.2f}:d=0.3,"
                      f"aformat=channel_layouts=stereo,adelay={ms}|{ms}[r{j}]")
            mix.append(f"[r{j}]")
        # low ambient drone under everything
        fa.append(f"anoisesrc=color=brown:amplitude=0.5:r=48000:d={total:.2f},lowpass=f=260,volume=0.10,"
                  f"aformat=channel_layouts=stereo[noise]")
        fa.append(f"sine=f=55:r=48000:d={total:.2f},volume=0.05,aformat=channel_layouts=stereo[hum]")
        fa.append(f"[noise][hum]amix=inputs=2:normalize=0,afade=t=in:d=1.5,"
                  f"afade=t=out:st={total - 1.5:.2f}:d=1.5[amb]")
        mix.append("[amb]")
        fa.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,"
                  f"atrim=0:{total:.2f},loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")

        script = tmp / "graph.txt"
        script.write_text(";\n".join(fv + fa))
        out = folder / "reel.mp4"
        run(["ffmpeg", "-y", *inputs, "-filter_complex_script", str(script),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "5M", "-bufsize", "10M",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
             "-movflags", "+faststart", str(out)])
        run(["ffmpeg", "-y", "-ss", "1.6", "-i", str(out), "-frames:v", "1", "-q:v", "3",
             str(folder / "thumb.jpg")])
    mb = out.stat().st_size / 1e6
    print(f"  -> {out.relative_to(ROOT)} ({mb:.1f} MB)")
    return out


def is_reel(folder):
    p = Path(folder) / "post.json"
    return p.exists() and json.loads(p.read_text(encoding="utf-8")).get("type") == "reel"


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    force = "--force" in args
    if "--all" in args:
        for d in sorted((ROOT / "posts" / "queue").glob("*/")):
            if is_reel(d) and (force or not (d / "reel.mp4").exists()):
                render_reel(d)
    else:
        for a in args:
            if not a.startswith("--"):
                render_reel(a)
