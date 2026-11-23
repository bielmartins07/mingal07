"""Coloca legenda (tradução PT grande + inglês pequeno) na faixa de baixo do vídeo."""
import subprocess, sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
S = os.path.dirname(os.path.abspath(__file__)); F = S + "/fonts"
W, H, FPS = 720, 1280, 30
YEL, WHITE = (255, 212, 0), (255, 255, 255)
F_PT = ImageFont.truetype(F + "/montserrat/files/montserrat-latin-900-normal.woff2", 44)
F_EN = ImageFont.truetype(F + "/montserrat/files/montserrat-latin-700-normal.woff2", 24)

# (início, fim, português com *destaque*, inglês)
LINES = [
    (0.00, 4.40, "Só o *AMOR* nunca hesita", "Only love never hesitates"),
    (4.48, 8.10, "Só a *CONFIANÇA* tem um preço a pagar", "Only trust has a price to pay"),
    (8.14, 11.00, "Como uma *FLOR* num *FURACÃO*", "Like a flower in a hurricane"),
    (11.06, 15.40, "Vamos ver o *SOL* nascer num novo dia", "We'll see the sun rise into another day"),
    (15.48, 19.50, "Só o *AMOR* nunca hesita", "Only love never hesitates"),
    (19.56, 23.28, "Só a *CONFIANÇA* tem um preço a pagar", "Only trust has a price to pay"),
    (23.32, 26.18, "Como uma *FLOR* num *FURACÃO*", "Like a flower in a hurricane"),
    (26.22, 30.10, "Eu *MORRO* antes de ir embora", "I will die before I walk away"),
]

def render_pt(text, maxw=660):
    words = [(w.strip("*").upper(), w.startswith("*")) for w in text.split()]
    lines, cur = [], []
    for w in words:
        test = " ".join(x for x, _ in cur + [w])
        if cur and F_PT.getlength(test) > maxw: lines.append(cur); cur = [w]
        else: cur.append(w)
    lines.append(cur)
    lh = 54; pad = 20
    im = Image.new("RGBA", (W, lh * len(lines) + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    for i, ln in enumerate(lines):
        total = F_PT.getlength(" ".join(x for x, _ in ln)); x = (W - total) / 2; y = pad + i * lh
        for wtxt, hl in ln:
            ds.text((x + 3, y + 5), wtxt, font=F_PT, fill=(0, 0, 0, 220), stroke_width=4, stroke_fill=(0, 0, 0, 220))
            d.text((x, y), wtxt, font=F_PT, fill=(YEL if hl else WHITE) + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 255))
            x += F_PT.getlength(wtxt + " ")
    out = sh.filter(ImageFilter.GaussianBlur(4)); out.alpha_composite(im)
    return out

def render_en(text):
    im = Image.new("RGBA", (W, 50), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = (W - F_EN.getlength(text)) / 2
    d.text((x, 10), text, font=F_EN, fill=(255, 235, 200, 230), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    return im

CACHE = [(a, b, render_pt(pt), render_en(en)) for a, b, pt, en in LINES]
BAR_TOP, BAR_BOT = 1088, 1280

def ease_back(t, s=2.2):
    t = min(1.0, max(0.0, t)) - 1; return t * t * ((s + 1) * t + s) + 1

def overlay(frame, t):
    for a, b, pt, en in CACHE:
        if a <= t < b:
            lt = t - a
            k = ease_back(lt / 0.28)
            alpha = min(1.0, lt / 0.12, max(0.0, (b - t) / 0.15))
            blk_h = pt.height + en.height - 10
            cy = (BAR_TOP + BAR_BOT) / 2
            top = int(cy - blk_h / 2)
            sc = 0.6 + 0.4 * k
            p = pt.resize((max(1, int(pt.width * sc)), max(1, int(pt.height * sc))), Image.BICUBIC)
            if alpha < 1:
                p = p.copy(); p.putalpha(p.getchannel("A").point(lambda v: int(v * alpha)))
                e = en.copy(); e.putalpha(en.getchannel("A").point(lambda v: int(v * alpha)))
            else:
                e = en
            frame.alpha_composite(p, (int(W / 2 - p.width / 2), int(top + pt.height / 2 - p.height / 2)))
            frame.alpha_composite(e, (0, top + pt.height - 10))
    return frame

if __name__ == "__main__":
    if len(sys.argv) > 3:
        for ts in [float(x) for x in sys.argv[3].split(",")]:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(ts), "-i", SRC, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True).stdout
            fr = Image.frombytes("RGBA", (W, H), raw); overlay(fr, ts + 0.5).convert("RGB").save(f"{S}/leg_{ts}.jpg", quality=90)
        sys.exit()
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "rgba", "-r", str(FPS), "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-i", SRC, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    n = 0; fs = W * H * 4
    while True:
        buf = dec.stdout.read(fs)
        if len(buf) < fs: break
        fr = Image.frombytes("RGBA", (W, H), buf)
        enc.stdin.write(overlay(fr, n / FPS).tobytes()); n += 1
    enc.stdin.close(); enc.wait(); print("ok", n, "frames")
