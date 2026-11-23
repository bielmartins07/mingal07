"""Vídeo 30s (1080x1920) da tabela de valores inteira, com elementos animados na própria arte:
poste de barbeiro girando, brilho nas navalhas/título, preços pulsando na batida, flocos girando."""
import math, random, subprocess, sys, wave, os
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

SRC, OUT = sys.argv[1], sys.argv[2]
S = os.path.dirname(os.path.abspath(__file__)); F = S + "/fonts"
W, H, FPS, DUR = 1080, 1920, 30, 30.0
N = int(FPS * DUR)
BEAT = 0.5
FONT = {
    "anton": F + "/anton/files/anton-latin-400-normal.woff2",
    "mont9": F + "/montserrat/files/montserrat-latin-900-normal.woff2",
    "mont8": F + "/montserrat/files/montserrat-latin-800-normal.woff2",
}
YEL, WHITE, RED = (255, 212, 0), (255, 255, 255), (214, 16, 24)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_out_back(t, s=1.9): t = clamp(t) - 1; return t * t * ((s + 1) * t + s) + 1

@lru_cache(None)
def font(n, s): return ImageFont.truetype(FONT[n], s)

@lru_cache(None)
def text_img(text, fname, size, color=WHITE, stroke=0, glow=None, shadow=True):
    f = font(fname, size); asc, desc = f.getmetrics(); pad = stroke + 40
    w, h = int(f.getlength(text) + 2 * pad), asc + desc + 2 * pad
    def layer(fill, sc):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad, pad), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=sc)
        return im
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow:
        g = layer(glow + (255,), glow + (255,)); g = Image.new("RGBA", (w, h)); ImageDraw.Draw(g).text((pad, pad), text, font=f, fill=glow + (255,), stroke_width=stroke + 8, stroke_fill=glow + (255,))
        out.alpha_composite(g.filter(ImageFilter.GaussianBlur(16)))
    if shadow:
        sh = layer((0, 0, 0, 190), (0, 0, 0, 190)).filter(ImageFilter.GaussianBlur(6))
        tmp = Image.new("RGBA", (w, h)); tmp.paste(sh, (5, 9)); out.alpha_composite(tmp)
    out.alpha_composite(layer(color + (255,), (0, 0, 0, 255)))
    return out

def place(canvas, img, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01: return
    if abs(scale - 1) > 1e-3:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if abs(rot) > 0.05: img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        img = img.copy(); img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    canvas.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)

# ------------------------------------------------------------------ base
src = Image.open(SRC).convert("RGB")
SW, SH = src.size
BASE = np.asarray(src).astype(np.float32)

def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))
BG_BIG = cover(src, int(W * 1.2), int(H * 1.2)).filter(ImageFilter.GaussianBlur(26))
BG_BIG = ImageEnhance.Brightness(BG_BIG).enhance(0.32).convert("RGBA")

# ------------------------------------------------------------------ poste girando (procedural)
PX0, PY0, PX1, PY1 = 10, 96, 175, 328
SS = 3  # supersample
c0 = np.array([77.5, 321.0]); c1 = np.array([107.5, 101.0])
ax = (c1 - c0); L = np.linalg.norm(ax); ah = ax / L; nh = np.array([-ah[1], ah[0]])
if nh[0] < 0: nh = -nh
R = 49.0
ys, xs = np.mgrid[0:(PY1 - PY0) * SS, 0:(PX1 - PX0) * SS].astype(np.float32)
px = PX0 + (xs + 0.5) / SS; py = PY0 + (ys + 0.5) / SS
dx, dy = px - c0[0], py - c0[1]
V = dx * ah[0] + dy * ah[1]
U = (dx * nh[0] + dy * nh[1]) / R
inside = (np.abs(U) < 1.0) & (py > 103) & (py < 318)
Uc = np.clip(U, -0.999, 0.999)
THETA = np.arcsin(Uc)
shade = 0.42 + 0.58 * np.cos(THETA) ** 0.8
spec = 0.55 * np.exp(-((Uc + 0.38) / 0.13) ** 2) + 0.18 * np.exp(-((Uc - 0.62) / 0.08) ** 2)
edge = np.clip((1 - np.abs(U)) * R / 2.0, 0, 1) * np.clip((py - 103) / 1.5, 0, 1) * np.clip((318 - py) / 1.5, 0, 1)
P_MASK = (inside * edge).astype(np.float32)
STRIPE_COLS = np.array([[175, 14, 34], [244, 244, 244], [24, 38, 120], [244, 244, 244]], np.float32)

def render_pole(arr, t):
    phase = V / 100.0 + THETA * 0.13 + t * 0.9
    idx = (np.floor((phase % 1.0) * 4)).astype(np.int32) % 4
    # suaviza as bordas das listras
    col = STRIPE_COLS[idx]
    col = col * shade[..., None] + spec[..., None] * 255
    col = np.clip(col, 0, 255)
    h, w = col.shape[:2]
    small = col.reshape(h // SS, SS, w // SS, SS, 3).mean(axis=(1, 3))
    m = P_MASK.reshape(h // SS, SS, w // SS, SS).mean(axis=(1, 3))[..., None]
    reg = arr[PY0:PY1, PX0:PX1]
    arr[PY0:PY1, PX0:PX1] = reg * (1 - m) + small * m

# ------------------------------------------------------------------ máscaras de brilho (dourado das navalhas, título)
def hsv_np(a):
    a = a / 255.0; mx = a.max(-1); mn = a.min(-1); d = mx - mn + 1e-6
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return h, d / (mx + 1e-6), mx
Hh, Ss, Vv = hsv_np(BASE)
gold = ((Hh > 22) & (Hh < 60) & (Ss > 0.28) & (Vv > 0.3)).astype(np.float32)
GOLD = np.zeros((SH, SW), np.float32)
for (x0, y0, x1, y1) in [(860, 120, SW, 450), (780, 1100, SW, SH), (0, 0, 190, 420)]:
    GOLD[y0:y1, x0:x1] = gold[y0:y1, x0:x1]
# metal do poste (tampas) também brilha
pole_metal = (Vv > 0.75) & (Ss < 0.2)
GOLD[0:96, 0:190] = np.maximum(GOLD[0:96, 0:190], pole_metal[0:96, 0:190])
GOLD[318:420, 0:190] = np.maximum(GOLD[318:420, 0:190], pole_metal[318:420, 0:190])
GOLD = np.asarray(Image.fromarray((GOLD * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))).astype(np.float32) / 255
TITLE = np.zeros((SH, SW), np.float32)
TITLE[300:400, 370:760] = ((Vv > 0.8) & (Ss < 0.25))[300:400, 370:760]
TITLE[160:260, 270:810] = ((Vv > 0.8) & (Ss < 0.25))[160:260, 270:810]
YY, XX = np.mgrid[0:SH, 0:SW].astype(np.float32)

def glint(arr, mask, t, period, offset, width=60, strength=1.0, angle=0.6):
    """Faixa de luz diagonal passando pelos pixels da máscara."""
    k = ((t + offset) % period) / period
    if k > 0.6: return
    pos = -400 + k / 0.6 * (SW + SH * angle + 800)
    proj = XX + YY * angle
    band = np.exp(-((proj - pos) / width) ** 2) * mask * strength
    sel = band > 0.01
    arr[sel] = np.clip(arr[sel] + band[sel, None] * 255 * np.array([1.0, 0.95, 0.75]), 0, 255)

# ------------------------------------------------------------------ preços pulsando (linha por linha, na batida)
ROWS = [485, 560, 640, 722, 797, 873, 951, 1030, 1112, 1197]
PRICE_X0, PRICE_X1 = 695, 875
NAME_X0 = 262
row_glow_y = np.arange(SH, dtype=np.float32)

def pop_price(img, row_i, k):
    """Amplia o preço da linha (k: 0..1 intensidade)."""
    if k <= 0.01: return
    y = ROWS[row_i]; box = (PRICE_X0, y - 34, PRICE_X1, y + 34)
    crop = img.crop(box)
    sc = 1 + 0.22 * k
    big = crop.resize((int(crop.width * sc), int(crop.height * sc)), Image.BICUBIC)
    # deixa o preço amarelo durante o pulo
    b = np.asarray(big).astype(np.float32)
    lum = b.mean(-1, keepdims=True)
    wmask = np.clip((lum - 170) / 60, 0, 1) * k
    b = b * (1 - wmask) + np.array(YEL, np.float32) * wmask
    big = Image.fromarray(b.astype(np.uint8))
    m = Image.new("L", big.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((8, 8, big.width - 8, big.height - 8), 20, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(7))
    cx = (box[0] + box[2]) / 2; cy = (box[1] + box[3]) / 2
    img.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), m)

def row_light(arr, row_i, k):
    if k <= 0.01: return
    y = ROWS[row_i]
    y0, y1 = y - 45, y + 45
    prof = np.exp(-((np.arange(y0, y1) - y) / 26.0) ** 2)[:, None, None]
    xr = np.linspace(0, 1, 918 - 210)[None, :, None]
    xprof = np.clip(np.minimum(xr, 1 - xr) * 12, 0, 1)
    arr[y0:y1, 210:918] = np.clip(arr[y0:y1, 210:918] + prof * xprof * 70 * k, 0, 255)

# ------------------------------------------------------------------ pílula do topo (pulsa)
PILL_BOX = (300, 22, 838, 150)
def pill_pulse(img, k):
    crop = img.crop(PILL_BOX); sc = 1 + 0.05 * k
    big = crop.resize((int(crop.width * sc), int(crop.height * sc)), Image.BICUBIC)
    m = Image.new("L", big.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((int(8 * sc), int(8 * sc), big.width - int(10 * sc), big.height - int(10 * sc)), int(30 * sc), fill=255)
    cx = (PILL_BOX[0] + PILL_BOX[2]) / 2; cy = (PILL_BOX[1] + PILL_BOX[3]) / 2
    img.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), m)

# ------------------------------------------------------------------ elementos de tela
def snowflake(size=120, col=(255, 255, 255)):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = size / 2; r = size * 0.46; w = max(2, size // 16)
    for i in range(6):
        a = math.radians(i * 60); ex, ey = c + r * math.cos(a), c + r * math.sin(a)
        d.line((c, c, ex, ey), fill=col + (255,), width=w)
        for f in (0.45, 0.7):
            bx, by = c + r * f * math.cos(a), c + r * f * math.sin(a)
            for s in (-1, 1):
                b = a + s * math.radians(40); L2 = r * 0.28
                d.line((bx, by, bx + L2 * math.cos(b), by + L2 * math.sin(b)), fill=col + (255,), width=w)
    d.ellipse((c - w * 1.5, c - w * 1.5, c + w * 1.5, c + w * 1.5), fill=col + (255,))
    g = im.filter(ImageFilter.GaussianBlur(4)); out = Image.new("RGBA", im.size); out.alpha_composite(g); out.alpha_composite(im)
    return out
FLAKE = snowflake(140)
FLAKES = [  # (x, y, tamanho, velocidade de giro, fase)
    (95, 800, 0.8, 70, 0), (60, 1060, 0.6, -90, 1), (105, 1300, 0.85, 55, 2), (70, 1490, 0.55, -80, 3),
    (995, 830, 0.75, -65, 4), (1030, 1040, 0.6, 85, 5), (990, 1240, 0.8, -60, 6),
]

def starburst(r=125, n=18, col=RED):
    sz = int(r * 2.3); im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = sz / 2
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n; rr = r if i % 2 == 0 else r * 0.82
        pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
    sh = Image.new("RGBA", im.size); ImageDraw.Draw(sh).polygon([(x + 6, y + 10) for x, y in pts], fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(im); d.polygon(pts, fill=(255, 255, 255, 255))
    pts2 = [(c + (x - c) * 0.9, c + (y - c) * 0.9) for x, y in pts]; d.polygon(pts2, fill=col + (255,))
    return im
BURST = starburst()

def pole_strip(h=30, period=120):
    w = W + period * 2; im = Image.new("RGBA", (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    cols = [(200, 16, 28), (255, 255, 255), (20, 40, 140), (255, 255, 255)]; step = period // 4
    for i, x in enumerate(range(-h, w + h, step)):
        d.polygon([(x, h), (x + step, h), (x + step + h, 0), (x + h, 0)], fill=cols[i % 4] + (255,))
    return im
POLE = pole_strip()

def rays(t):
    """Raios de luz girando atrás (aparecem nas margens)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cx, cy = W / 2, H / 2; Rr = 1600; n = 16; a0 = t * 0.25
    for i in range(n):
        a = a0 + i * 2 * math.pi / n
        d.polygon([(cx, cy), (cx + Rr * math.cos(a), cy + Rr * math.sin(a)), (cx + Rr * math.cos(a + 0.09), cy + Rr * math.sin(a + 0.09))], fill=(255, 200, 60, 26))
    return im.filter(ImageFilter.GaussianBlur(3))

random.seed(11)
SNOW = [(random.uniform(0, W), random.uniform(0, H), random.uniform(2, 6.5), random.uniform(50, 150), random.uniform(0, 6.28)) for _ in range(80)]
TWINK = [(random.uniform(275, 370), random.uniform(275, 400)) for _ in range(10)] + \
        [(random.uniform(0, SW), random.uniform(1000, SH)) for _ in range(6)] + [(820, 335), (835, 380), (300, 1350), (690, 1330)]
TWINK_PH = [random.uniform(0, 6.28) for _ in TWINK]

# ------------------------------------------------------------------ layout
IMG_W = W
IMG_H = int(SH * W / SW)          # 1338
IMG_CY = 318 + IMG_H / 2          # imagem logo abaixo do topo
SCALE = W / SW

def to_frame(x, y, z=1.0):
    return W / 2 + (x - SW / 2) * SCALE * z, IMG_CY + (y - SH / 2) * SCALE * z

def frame(t):
    beat_k = 1 - ease_out_cubic(((t % BEAT) / BEAT) / 0.55)   # 1 no tempo, cai rápido
    bar = int(t / BEAT)
    # ---------- arte animada (em coordenadas da imagem original)
    arr = BASE.copy()
    render_pole(arr, t)
    glint(arr, GOLD, t, 2.6, 0.0, 70, 1.1)
    glint(arr, TITLE, t, 3.4, 1.3, 50, 0.9, angle=0.3)
    row = bar % len(ROWS)
    row_light(arr, row, beat_k)
    img = Image.fromarray(arr.astype(np.uint8))
    pop_price(img, row, beat_k)
    pill_pulse(img, beat_k if bar % 2 == 0 else 0.4 * beat_k)
    # brilho do cartão inteiro de 4 em 4 segundos
    # ---------- composição na tela
    canvas = BG_BIG.crop((60, 100, 60 + W, 100 + H)).copy()
    canvas.alpha_composite(rays(t))
    intro = ease_out_back(t / 0.45, 1.4)
    z = (1.18 - 0.18 * intro if t < 0.45 else 1.0) * (1 + 0.010 * beat_k)
    fw, fh = int(IMG_W * z), int(IMG_H * z)
    fimg = img.resize((fw, fh), Image.BICUBIC).convert("RGBA")
    sh = Image.new("RGBA", (fw + 80, fh + 80), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle((40, 50, fw + 40, fh + 50), fill=(0, 0, 0, 200))
    canvas.paste(fimg, (int(W / 2 - fw / 2), int(IMG_CY - fh / 2)))
    d = ImageDraw.Draw(canvas)
    # brilhinhos (árvore, papai noel, bolinhas)
    for (x, y), ph in zip(TWINK, TWINK_PH):
        k = max(0.0, math.sin(t * 4.0 + ph * 3)) ** 8
        if k < 0.05: continue
        fx, fy = to_frame(x, y, z); Ls = 22 * k + 3; c = (255, 240, 170, int(255 * k))
        d.line((fx - Ls, fy, fx + Ls, fy), fill=c, width=3); d.line((fx, fy - Ls, fx, fy + Ls), fill=c, width=3)
        d.ellipse((fx - 3, fy - 3, fx + 3, fy + 3), fill=(255, 255, 255, int(255 * k)))
    # flocos girando nas laterais
    for x, y, s, sp, ph in FLAKES:
        yy = y + math.sin(t * 0.9 + ph) * 25
        place(canvas, FLAKE, x + math.sin(t * 0.6 + ph) * 10, yy, scale=s * (1 + 0.08 * beat_k), rot=t * sp + ph * 40, alpha=0.85)
    # neve caindo
    for x0, y0, r, sp, ph in SNOW:
        y = (y0 + t * sp) % (H + 20) - 10; x = x0 + math.sin(t * 1.2 + ph) * 16
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 140 if r < 4.5 else 200))
    # ---------- topo
    off = int((t * 160) % 120); strip = POLE.crop((off, 0, off + W, POLE.height))
    canvas.alpha_composite(strip, (0, 0)); canvas.alpha_composite(strip, (0, H - strip.height))
    place(canvas, text_img("CONFIRA NOSSOS", "mont9", 62, WHITE, stroke=2), W / 2 - 70, 112)
    place(canvas, text_img("VALORES", "anton", 150, YEL, stroke=5, glow=(255, 60, 0)), W / 2 - 70, 222, scale=1 + 0.06 * beat_k)
    # selo girando
    bx, by = 905, 175
    place(canvas, BURST, bx, by, scale=0.95 + 0.06 * beat_k, rot=-t * 40)
    place(canvas, text_img("PREÇO", "anton", 46, WHITE, shadow=False), bx - 2, by - 34, rot=8)
    place(canvas, text_img("JUSTO!", "anton", 62, YEL, stroke=2, shadow=False), bx + 6, by + 30, rot=8)
    # ---------- rodapé
    yb = 1765
    cta = ["AGENDE JÁ SEU HORÁRIO", "@barbearia_dimaria", "@mingal07"]
    ci = int(t / 2.5) % 3; lt = (t % 2.5)
    kin = ease_out_back(lt / 0.35, 1.8)
    tx = text_img(cta[ci], "mont9", 64 if ci else 56, (20, 10, 10) if ci == 0 else WHITE, shadow=False)
    pill = Image.new("RGBA", (tx.width + 10, tx.height - 22), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle((0, 0, pill.width, pill.height), 32, fill=(YEL if ci == 0 else RED) + (255,))
    pill.alpha_composite(tx, (5, -11))
    place(canvas, pill, W / 2, yb, scale=kin * (1 + 0.03 * beat_k))
    # flashes
    if t < 0.25: canvas.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * (1 - t / 0.25)))))
    if t > DUR - 0.5: canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * clamp((t - (DUR - 0.5)) / 0.5)))))
    return canvas

# ------------------------------------------------------------------ áudio
def make_audio(path):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n, np.float32); rng = np.random.default_rng(3)
    def add(sig, t0, g=1.0):
        i = int(t0 * sr); j = min(n, i + len(sig))
        if i < n: out[i:j] += sig[: j - i] * g
    tt = np.arange(int(0.35 * sr)) / sr
    K = np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-tt * 30)) / sr) * np.exp(-tt * 9)
    th = np.arange(int(0.06 * sr)) / sr; HT = np.diff(np.concatenate([[0], rng.standard_normal(len(th))])) * np.exp(-th * 70) * 0.35
    tc = np.arange(int(0.2 * sr)) / sr; CL = np.diff(np.concatenate([[0], rng.standard_normal(len(tc))])) * (np.exp(-tc * 25) + 0.6 * np.exp(-np.maximum(tc - 0.012, 0) * 25) * (tc > 0.012)) * 0.4
    tb = np.arange(int(0.9 * sr)) / sr; BM = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-tb * 12)) / sr) * np.exp(-tb * 4) * 1.1
    def bass(f):
        x = np.arange(int(0.9 * sr)) / sr
        return (np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x)) * np.minimum(1, x * 80) * np.exp(-x * 3.2) * 0.45
    def bell(f):
        x = np.arange(int(0.5 * sr)) / sr
        return (np.sin(2 * np.pi * f * x) + 0.4 * np.sin(2 * np.pi * f * 2.76 * x)) * np.exp(-x * 7) * 0.12
    notes = [55.0, 55.0, 65.41, 49.0]; mel = [880, 987.8, 1046.5, 1318.5, 1174.7, 1046.5, 987.8, 880]
    for b in range(int(DUR / BEAT)):
        t0 = b * BEAT
        if t0 >= DUR - 0.5: break
        add(K, t0, 0.95); add(HT, t0 + BEAT / 2, 0.8)
        if b % 2 == 1: add(CL, t0, 0.7)
        if b % 2 == 0: add(bass(notes[(b // 8) % 4]), t0)
        add(bell(mel[b % 8]), t0 + 0.25)
    add(BM, 0.0, 0.9)
    fl = int(0.6 * sr); out[-fl:] *= np.linspace(1, 0, fl)
    pcm = (np.tanh(out * 1.1) * 0.85 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "preview":
        for ts in [float(x) for x in sys.argv[4].split(",")]:
            frame(ts).convert("RGB").save(f"{S}/p2_{ts:05.2f}.jpg", quality=88)
        sys.exit()
    wav = S + "/beat2.wav"; make_audio(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f_ in range(N):
        p.stdin.write(frame(f_ / FPS).convert("RGB").tobytes())
        if f_ % 150 == 0: print("frame", f_, flush=True)
    p.stdin.close(); p.wait(); print("ok", OUT)
