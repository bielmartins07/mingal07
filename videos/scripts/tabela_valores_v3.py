"""Vídeo 30s no tamanho da foto, animando só dentro da arte:
poste de barbeiro girando, flocos girando, brilho nas navalhas/título, preços pulsando na batida."""
import math, random, subprocess, sys, wave, os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
S = os.path.dirname(os.path.abspath(__file__))
FPS, DUR, BEAT = 30, 30.0, 0.5
N = int(FPS * DUR)
YEL = (255, 212, 0)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3

src = Image.open(SRC).convert("RGB")
SW, SH = src.size
OW, OH = SW - SW % 2, SH - SH % 2          # dimensões pares p/ o vídeo
ORIG = np.asarray(src).astype(np.float32)

# ---------------------------------------------------------------- flocos da arte: recorta e preenche o fundo
FLAKES = [(75, 562, 54, 22), (170, 785, 34, -30), (104, 1130, 30, 26), (950, 775, 32, -24)]  # x, y, raio, graus/s
bgr = cv2.cvtColor(ORIG.astype(np.uint8), cv2.COLOR_RGB2BGR)
hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
inpaint_mask = np.zeros((SH, SW), np.uint8)
FLAKE_IMGS = []
for x, y, r, _ in FLAKES:
    circ = np.zeros((SH, SW), np.uint8); cv2.circle(circ, (x, y), r, 1, -1)
    if x > 918: circ[:, :921] = 0          # não mexe no cartão vermelho
    bright = ((hsv[..., 2] > 150) & (hsv[..., 1] < 70)).astype(np.uint8) & circ
    bright = cv2.dilate(bright, np.ones((5, 5), np.uint8))
    inpaint_mask |= bright
    # recorte RGBA do floco (alfa pela luminosidade)
    x0, y0, x1, y1 = x - r - 4, y - r - 4, x + r + 5, y + r + 5
    crop = ORIG[y0:y1, x0:x1]
    v = hsv[y0:y1, x0:x1, 2].astype(np.float32)
    local_bg = np.percentile(v[circ[y0:y1, x0:x1] > 0], 30)
    a = np.clip((v - local_bg - 15) / (235 - local_bg - 15), 0, 1) * (bright[y0:y1, x0:x1] > 0)
    a = cv2.GaussianBlur(a.astype(np.float32), (3, 3), 0)
    rgba = np.dstack([np.full_like(v, 245), np.full_like(v, 245), np.full_like(v, 250), a * 255]).astype(np.uint8)
    FLAKE_IMGS.append((Image.fromarray(rgba, "RGBA"), x0, y0))
BASE = cv2.inpaint(bgr, inpaint_mask, 7, cv2.INPAINT_TELEA)
BASE = cv2.cvtColor(BASE, cv2.COLOR_BGR2RGB).astype(np.float32)

# ---------------------------------------------------------------- poste de barbeiro
PX0, PY0, PX1, PY1 = 15, 90, 165, 322
SS = 4
ys, xs = np.mgrid[0:(PY1 - PY0) * SS, 0:(PX1 - PX0) * SS].astype(np.float32)
px = PX0 + (xs + 0.5) / SS; py = PY0 + (ys + 0.5) / SS
fy = (py - 100) / 210.0
xl = 49 + (26 - 49) * fy                 # borda esquerda do vidro
xr = 156.5 + (127 - 156.5) * fy        # borda direita do vidro
U = 2 * (px - xl) / (xr - xl) - 1        # -1..1 atravessando o cilindro
ytop = 98.5
ybot = 308.5 + 5 * (1 - np.clip(U, -1, 1) ** 2)
Uc = np.clip(U, -0.999, 0.999)
THETA = np.arcsin(Uc)
inside = np.clip((1 - np.abs(U)) * (xr - xl) / 2 / 0.8, 0, 1) * np.clip((py - ytop) / 0.8, 0, 1) * np.clip((ybot - py) / 0.8, 0, 1)
# sombreamento de cilindro + reflexos verticais de vidro
shade = 0.70 + 0.30 * np.cos(THETA)
spec = 0.45 * np.exp(-((Uc + 0.45) / 0.10) ** 2) + 0.15 * np.exp(-((Uc - 0.55) / 0.06) ** 2)
COLS = np.array([[22, 40, 118], [242, 242, 242], [180, 14, 38], [242, 242, 242]], np.float32)  # azul, branco, vermelho, branco
VV = (320 - py)                          # posição ao longo do poste (pra cima)
RISE = 9.0                               # quanto a listra sobe pra direita (px por rad)

def down(a):
    h, w = a.shape[:2]
    return a.reshape(h // SS, SS, w // SS, SS, *a.shape[2:]).mean(axis=(1, 3))

P_MASK = down(inside.astype(np.float32))[..., None]
# mantém as linhas pretas de reflexo e as bordas escuras originais
orig_reg = ORIG[PY0:PY1, PX0:PX1]
mx = orig_reg.max(-1, keepdims=True)
keep_dark = np.clip((75 - mx) / 25, 0, 1)
gy, gx = np.mgrid[PY0:PY1, PX0:PX1]
keep_dark *= ((gx >= 92) & (gy >= 215))[..., None]   # só as riscas pretas de reflexo (canto inferior direito)
P_MASK = P_MASK * (1 - keep_dark)

def render_pole(arr, t):
    phase = (VV - RISE * THETA) / 100.0 - t * 0.85
    idx = np.floor((phase % 1.0) * 4).astype(np.int32)
    col = COLS[idx] * shade[..., None] + spec[..., None] * 255
    col = down(np.clip(col, 0, 255))
    reg = arr[PY0:PY1, PX0:PX1]
    arr[PY0:PY1, PX0:PX1] = reg * (1 - P_MASK) + col * P_MASK

# ---------------------------------------------------------------- brilhos
def hsv_np(a):
    a = a / 255.0; mx = a.max(-1); mn = a.min(-1); d = mx - mn + 1e-6
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return h, d / (mx + 1e-6), mx
Hh, Ss, Vv = hsv_np(ORIG)
gold = ((Hh > 22) & (Hh < 60) & (Ss > 0.28) & (Vv > 0.3)).astype(np.float32)
GOLD = np.zeros((SH, SW), np.float32)
for (x0, y0, x1, y1) in [(860, 120, SW, 450), (780, 1100, SW, SH)]:
    GOLD[y0:y1, x0:x1] = gold[y0:y1, x0:x1]
metal = ((Vv > 0.75) & (Ss < 0.2)).astype(np.float32)
GOLD[0:96, 0:190] = metal[0:96, 0:190]; GOLD[312:420, 0:190] = metal[312:420, 0:190]
GOLD = cv2.GaussianBlur(GOLD, (3, 3), 0)
TITLE = np.zeros((SH, SW), np.float32)
white = ((Vv > 0.8) & (Ss < 0.25)).astype(np.float32)
TITLE[300:400, 370:760] = white[300:400, 370:760]
TITLE[160:260, 270:810] = white[160:260, 270:810]
YY, XX = np.mgrid[0:SH, 0:SW].astype(np.float32)

def bbox(m):
    ys_, xs_ = np.nonzero(m > 0.02); return ys_.min(), ys_.max() + 1, xs_.min(), xs_.max() + 1
GOLD_BB, TITLE_BB = bbox(GOLD), bbox(TITLE)

def glint(arr, mask, bb, t, period, offset, width=60, strength=1.0, angle=0.6):
    k = ((t + offset) % period) / period
    if k > 0.6: return
    y0, y1, x0, x1 = bb
    pos = x0 + y0 * angle - 150 + k / 0.6 * ((x1 - x0) + (y1 - y0) * angle + 300)
    proj = XX[y0:y1, x0:x1] + YY[y0:y1, x0:x1] * angle
    band = (np.exp(-((proj - pos) / width) ** 2) * mask[y0:y1, x0:x1] * strength)[..., None]
    arr[y0:y1, x0:x1] = np.clip(arr[y0:y1, x0:x1] + band * 255 * np.array([1.0, 0.95, 0.75]), 0, 255)

# ---------------------------------------------------------------- preços pulsando
ROWS = [485, 560, 640, 722, 797, 873, 951, 1030, 1112, 1197]
def pop_price(img, row_i, k):
    if k <= 0.01: return
    y = ROWS[row_i]; box = (695, y - 34, 875, y + 34)
    crop = img.crop(box); sc = 1 + 0.18 * k
    big = crop.resize((int(crop.width * sc), int(crop.height * sc)), Image.BICUBIC)
    b = np.asarray(big).astype(np.float32)
    wm = np.clip((b.mean(-1, keepdims=True) - 170) / 60, 0, 1) * k
    big = Image.fromarray((b * (1 - wm) + np.array(YEL, np.float32) * wm).astype(np.uint8))
    m = Image.new("L", big.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((8, 8, big.width - 8, big.height - 8), 20, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(7))
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    img.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), m)

def row_light(arr, row_i, k):
    if k <= 0.01: return
    y = ROWS[row_i]; y0, y1 = y - 45, y + 45
    prof = np.exp(-((np.arange(y0, y1) - y) / 26.0) ** 2)[:, None, None]
    xr_ = np.linspace(0, 1, 918 - 210)[None, :, None]
    arr[y0:y1, 210:918] = np.clip(arr[y0:y1, 210:918] + prof * np.clip(np.minimum(xr_, 1 - xr_) * 12, 0, 1) * 60 * k, 0, 255)

PILL_BOX = (300, 22, 838, 150)
def pill_pulse(img, k):
    crop = img.crop(PILL_BOX); sc = 1 + 0.04 * k
    big = crop.resize((int(crop.width * sc), int(crop.height * sc)), Image.BICUBIC)
    m = Image.new("L", big.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((int(8 * sc), int(8 * sc), big.width - int(10 * sc), big.height - int(10 * sc)), int(30 * sc), fill=255)
    cx, cy = (PILL_BOX[0] + PILL_BOX[2]) / 2, (PILL_BOX[1] + PILL_BOX[3]) / 2
    img.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), m)

random.seed(5)
TWINK = [(random.uniform(278, 368), random.uniform(280, 400)) for _ in range(9)] + [(820, 335), (835, 380), (300, 1350), (690, 1330), (60, 1110), (1060, 1000)]
TWINK_PH = [random.uniform(0, 6.28) for _ in TWINK]

def frame(t):
    beat_k = 1 - ease_out_cubic(((t % BEAT) / BEAT) / 0.55)
    bar = int(t / BEAT)
    arr = BASE.copy()
    render_pole(arr, t)
    glint(arr, GOLD, GOLD_BB, t, 2.6, 0.0, 70, 1.0)
    glint(arr, TITLE, TITLE_BB, t, 3.4, 1.3, 50, 0.9, angle=0.3)
    row = bar % len(ROWS)
    row_light(arr, row, beat_k)
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
    for (fim, x0, y0), (x, y, r, sp) in zip(FLAKE_IMGS, FLAKES):
        rot = fim.rotate(t * sp, resample=Image.BICUBIC, center=(x - x0, y - y0))
        img.alpha_composite(rot, (x0, y0))
    img = img.convert("RGB")
    pop_price(img, row, beat_k)
    pill_pulse(img, beat_k if bar % 2 == 0 else 0.4 * beat_k)
    d = ImageDraw.Draw(img, "RGBA")
    for (x, y), ph in zip(TWINK, TWINK_PH):
        k = max(0.0, math.sin(t * 4.0 + ph * 3)) ** 8
        if k < 0.05: continue
        L = 18 * k + 3; c = (255, 240, 170, int(255 * k))
        d.line((x - L, y, x + L, y), fill=c, width=3); d.line((x, y - L, x, y + L), fill=c, width=3)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255, int(255 * k)))
    return img.crop((0, 0, OW, OH))

def make_audio(path):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n, np.float32); rng = np.random.default_rng(3)
    def add(sig, t0, g=1.0):
        i = int(t0 * sr); j = min(n, i + len(sig))
        if i < n: out[i:j] += sig[: j - i] * g
    tt = np.arange(int(0.35 * sr)) / sr
    K = np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-tt * 30)) / sr) * np.exp(-tt * 9)
    th = np.arange(int(0.06 * sr)) / sr; HT = np.diff(np.concatenate([[0], rng.standard_normal(len(th))])) * np.exp(-th * 70) * 0.35
    tc = np.arange(int(0.2 * sr)) / sr; CL = np.diff(np.concatenate([[0], rng.standard_normal(len(tc))])) * (np.exp(-tc * 25) + 0.6 * np.exp(-np.maximum(tc - 0.012, 0) * 25) * (tc > 0.012)) * 0.4
    def bass(f):
        x = np.arange(int(0.9 * sr)) / sr
        return (np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x)) * np.minimum(1, x * 80) * np.exp(-x * 3.2) * 0.45
    def bell(f):
        x = np.arange(int(0.5 * sr)) / sr
        return (np.sin(2 * np.pi * f * x) + 0.4 * np.sin(2 * np.pi * f * 2.76 * x)) * np.exp(-x * 7) * 0.12
    notes = [55.0, 55.0, 65.41, 49.0]; mel = [880, 987.8, 1046.5, 1318.5, 1174.7, 1046.5, 987.8, 880]
    for b in range(int(DUR / BEAT)):
        t0 = b * BEAT
        add(K, t0, 0.95); add(HT, t0 + BEAT / 2, 0.8)
        if b % 2 == 1: add(CL, t0, 0.7)
        if b % 2 == 0: add(bass(notes[(b // 8) % 4]), t0)
        add(bell(mel[b % 8]), t0 + 0.25)
    fl = int(0.6 * sr); out[-fl:] *= np.linspace(1, 0, fl)
    pcm = (np.tanh(out * 1.1) * 0.85 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "preview":
        for ts in [float(x) for x in sys.argv[4].split(",")]:
            frame(ts).save(f"{S}/p3_{ts:05.2f}.png")
        sys.exit()
    wav = S + "/beat3.wav"; make_audio(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f_ in range(N):
        p.stdin.write(frame(f_ / FPS).tobytes())
        if f_ % 150 == 0: print("frame", f_, flush=True)
    p.stdin.close(); p.wait(); print("ok", OUT)
