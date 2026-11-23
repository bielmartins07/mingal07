"""Gera o vídeo animado (30s, 1080x1920) da tabela de valores da Di Maria Barbershop."""
import math, random, struct, subprocess, sys, wave, os
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

SRC = sys.argv[1]
OUT = sys.argv[2]
S = os.path.dirname(os.path.abspath(__file__))
F = S + "/fonts"
W, H, FPS, DUR = 1080, 1920, 30, 30.0
N = int(FPS * DUR)

FONT = {
    "anton": F + "/anton/files/anton-latin-400-normal.woff2",
    "bebas": F + "/bebas-neue/files/bebas-neue-latin-400-normal.woff2",
    "mont9": F + "/montserrat/files/montserrat-latin-900-normal.woff2",
    "mont8": F + "/montserrat/files/montserrat-latin-800-normal.woff2",
    "mont7": F + "/montserrat/files/montserrat-latin-700-normal.woff2",
}
YEL = (255, 212, 0)
WHITE = (255, 255, 255)
RED = (214, 16, 24)
DARK = (12, 6, 6)

SERVICOS = [
    ("Corte Simples", 20), ("Corte Disfarçado", 30), ("Corte na Gilete", 35),
    ("Corte Infantil", 35), ("Barba", 20), ("Acabamento / Pé", 15),
    ("Reflexo + Corte", 90), ("Platinado + Corte", 90), ("Pigmentação", 15),
    ("Sobrancelha", 5),
]
# timeline (s)
T_INTRO, T_BANNER, T_ITEMS = 0.0, 2.5, 4.0
SLOT = 2.0
T_FULL = T_ITEMS + SLOT * len(SERVICOS)   # 24.0
T_CTA = 27.0

# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_cubic(t): t = clamp(t); return t ** 3
def ease_out_back(t, s=1.9):
    t = clamp(t); t -= 1; return t * t * ((s + 1) * t + s) + 1
def ease_out_elastic(t):
    t = clamp(t)
    if t in (0, 1): return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1

@lru_cache(None)
def font(name, size): return ImageFont.truetype(FONT[name], size)

@lru_cache(None)
def text_img(text, fname, size, color=WHITE, stroke=0, stroke_color=(0, 0, 0),
             shadow=True, spacing=0, glow=None):
    """Renderiza texto em RGBA (com sombra/contorno/brilho opcionais)."""
    f = font(fname, size)
    chars = list(text) if spacing else [text]
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] if spacing else 0 for c in chars]
    if spacing:
        tw = sum(f.getlength(c) for c in chars) + spacing * (len(chars) - 1)
    else:
        tw = f.getlength(text)
    asc, desc = f.getmetrics()
    pad = stroke + 40
    w, h = int(tw + 2 * pad), int(asc + desc + 2 * pad)
    def draw_layer(fill, strk, strk_col):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = pad
        for c in chars:
            d.text((x, pad), c, font=f, fill=fill, stroke_width=strk, stroke_fill=strk_col)
            x += (f.getlength(c) + spacing) if spacing else 0
        return im
    main = draw_layer(color + (255,), stroke, stroke_color + (255,))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow:
        g = draw_layer(glow + (255,), stroke + 6, glow + (255,)).filter(ImageFilter.GaussianBlur(18))
        out = Image.alpha_composite(out, g)
    if shadow:
        sh = draw_layer((0, 0, 0, 200), stroke, (0, 0, 0, 200)).filter(ImageFilter.GaussianBlur(6))
        tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0)); tmp.paste(sh, (6, 10))
        out = Image.alpha_composite(out, tmp)
    out = Image.alpha_composite(out, main)
    return out

@lru_cache(None)
def outline_img(text, fname, size, color=WHITE, width=4):
    f = font(fname, size)
    pad = width + 20
    w = int(f.getlength(text) + 2 * pad); asc, desc = f.getmetrics(); h = asc + desc + 2 * pad
    a = Image.new("L", (w, h), 0); ImageDraw.Draw(a).text((pad, pad), text, font=f, fill=255, stroke_width=width, stroke_fill=255)
    b = Image.new("L", (w, h), 0); ImageDraw.Draw(b).text((pad, pad), text, font=f, fill=255)
    m = ImageChops.subtract(a, b)
    im = Image.new("RGBA", (w, h), color + (0,)); im.putalpha(m)
    return im

def place(canvas, img, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01: return
    if abs(scale - 1) > 1e-3:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if abs(rot) > 0.05:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = img.getchannel("A").point(lambda v: int(v * alpha)); img = img.copy(); img.putalpha(a)
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2))) if (
        cx - img.width / 2 >= 0 and cy - img.height / 2 >= 0 and cx + img.width / 2 <= W and cy + img.height / 2 <= H
    ) else canvas.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)

def wrap(text, fname, size, maxw):
    f = font(fname, size); words = text.split(); lines = [""]
    for w_ in words:
        t = (lines[-1] + " " + w_).strip()
        if f.getlength(t) <= maxw or not lines[-1]: lines[-1] = t
        else: lines.append(w_)
    return lines

# ---------------------------------------------------------------- assets
src = Image.open(SRC).convert("RGB")

def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))

BG_BIG = cover(src, int(W * 1.25), int(H * 1.25)).filter(ImageFilter.GaussianBlur(22))
BG_BIG = ImageEnhance.Brightness(BG_BIG).enhance(0.38).convert("RGBA")

# vinheta vermelha
yy, xx = np.mgrid[0:H, 0:W]
d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.6)) ** 2)
vig = np.clip(d, 0, 1) ** 1.6
VIGNETTE = np.zeros((H, W, 4), np.uint8)
VIGNETTE[..., 0] = 40; VIGNETTE[..., 3] = (vig * 235).astype(np.uint8)
VIGNETTE = Image.fromarray(VIGNETTE, "RGBA")

# brilho vermelho central
glow = np.exp(-(((xx - W / 2) / 520) ** 2 + ((yy - H * 0.52) / 640) ** 2))
GLOW = np.zeros((H, W, 4), np.uint8); GLOW[..., 0] = 200; GLOW[..., 1] = 10; GLOW[..., 2] = 18
GLOW[..., 3] = (glow * 150).astype(np.uint8); GLOW = Image.fromarray(GLOW, "RGBA")
del xx, yy, d, vig, glow

LOGO = src.crop((262, 160, 486, 264)).convert("RGBA")
# remove o fundo escuro do logo (fica só o branco)
la = np.array(LOGO).astype(np.float32)
lum = la[..., :3].mean(axis=2)
alpha = np.clip((lum - 95) * 3.2, 0, 255)
la[..., :3] = 255; la[..., 3] = alpha
LOGO = Image.fromarray(la.astype(np.uint8), "RGBA")
LOGO = LOGO.resize((LOGO.width * 4, LOGO.height * 4), Image.LANCZOS)
LOGO_SH = Image.new("RGBA", LOGO.size, (0, 0, 0, 0))
LOGO_SH.putalpha(LOGO.getchannel("A").filter(ImageFilter.GaussianBlur(10)))

CARD_W = 960
CARD = src.resize((CARD_W, int(src.height * CARD_W / src.width)), Image.LANCZOS).convert("RGBA")
mask = Image.new("L", CARD.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, CARD.width, CARD.height), 36, fill=255)
CARD.putalpha(mask)
CARD_SH = Image.new("RGBA", (CARD.width + 120, CARD.height + 120), (0, 0, 0, 0))
CARD_SH.paste((0, 0, 0, 220), (60, 75, 60 + CARD.width, 75 + CARD.height), mask)
CARD_SH = CARD_SH.filter(ImageFilter.GaussianBlur(28))

# barra estilo "barber pole" (listras animadas)
def pole_strip(h=34, period=120):
    w = W + period * 2
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    cols = [(200, 16, 28), (255, 255, 255), (20, 40, 140), (255, 255, 255)]
    step = period // 4
    for i, x in enumerate(range(-h, w + h, step)):
        d.polygon([(x, h), (x + step, h), (x + step + h, 0), (x + h, 0)], fill=cols[i % 4] + (255,))
    return im
POLE = pole_strip()

random.seed(7)
SNOW = [(random.uniform(0, W), random.uniform(0, H), random.uniform(2, 7), random.uniform(40, 140), random.uniform(0, 6.28)) for _ in range(90)]
SPARK = [(random.uniform(60, W - 60), random.uniform(200, H - 200), random.uniform(0, 3), random.uniform(0.6, 1.4)) for _ in range(26)]

# ---------------------------------------------------------------- layers
def background(t, zoom_pulse=0.0):
    z = 1.0 + 0.06 * (t / DUR) + zoom_pulse
    bw, bh = int(W * z), int(H * z)
    ox = (BG_BIG.width - bw) / 2 + math.sin(t * 0.35) * 40
    oy = (BG_BIG.height - bh) / 2 + math.cos(t * 0.27) * 50
    bg = BG_BIG.crop((int(ox), int(oy), int(ox) + bw, int(oy) + bh)).resize((W, H), Image.BILINEAR)
    bg.alpha_composite(GLOW); bg.alpha_composite(VIGNETTE)
    return bg

def snow(canvas, t):
    d = ImageDraw.Draw(canvas)
    for x0, y0, r, sp, ph in SNOW:
        y = (y0 + t * sp) % (H + 20) - 10
        x = x0 + math.sin(t * 1.3 + ph) * 18
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 150 if r < 4.5 else 210))

def sparkles(canvas, t, strength=1.0):
    d = ImageDraw.Draw(canvas)
    for x, y, ph, sp in SPARK:
        k = max(0.0, math.sin(t * 3.2 * sp + ph * 2)) ** 6 * strength
        if k < 0.05: continue
        L = 26 * k + 4
        c = (255, 230, 120, int(255 * k))
        d.line((x - L, y, x + L, y), fill=c, width=3); d.line((x, y - L, x, y + L), fill=c, width=3)
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255, int(255 * k)))

def poles(canvas, t, alpha=1.0):
    off = int((t * 160) % 120)
    strip = POLE.crop((off, 0, off + W, POLE.height))
    if alpha < 1:
        a = strip.getchannel("A").point(lambda v: int(v * alpha)); strip = strip.copy(); strip.putalpha(a)
    canvas.alpha_composite(strip, (0, 0)); canvas.alpha_composite(strip, (0, H - strip.height))

def flash(canvas, k, color=(255, 255, 255)):
    if k <= 0.01: return
    canvas.alpha_composite(Image.new("RGBA", (W, H), color + (int(255 * clamp(k)),)))

def shake(t, t0, amp=28, dur=0.35):
    if t < t0 or t > t0 + dur: return 0, 0
    k = 1 - (t - t0) / dur
    return (math.sin(t * 91) * amp * k, math.cos(t * 77) * amp * k)

def handle(canvas, y, alpha=1.0, big=False):
    txt = text_img("@barbearia_dimaria", "mont8", 54 if not big else 70, WHITE, stroke=2)
    place(canvas, txt, W / 2, y, alpha=alpha)

# ---------------------------------------------------------------- scenes
def scene_intro(t):
    c = background(t)
    snow(c, t)
    # logo: zoom-in com rotação
    k = ease_out_back((t - 0.05) / 0.7, 1.5)
    sx, sy = shake(t, 1.0, 34)
    if t >= 0.05:
        place(c, LOGO_SH, W / 2 + 8 + sx, 560 + 12 + sy, scale=0.95 * k, alpha=0.8)
        place(c, LOGO, W / 2 + sx, 560 + sy, scale=0.95 * k, rot=(1 - k) * -25)
    # TABELA DE (letras espaçadas)
    if t >= 0.55:
        k2 = ease_out_cubic((t - 0.55) / 0.35)
        place(c, text_img("TABELA DE", "mont9", 92, WHITE, spacing=26), W / 2 + (1 - k2) * -700 + sx, 880 + sy, alpha=k2)
    # VALORES slam
    if t >= 1.0:
        k3 = ease_out_back((t - 1.0) / 0.3, 2.4)
        sc = 3.0 - 2.0 * clamp((t - 1.0) / 0.22)
        img = text_img("VALORES", "anton", 250, YEL, stroke=6, glow=(255, 60, 0))
        place(c, img, W / 2 + sx, 1080 + sy, scale=sc, alpha=clamp((t - 1.0) / 0.12))
    # linha dourada
    if t >= 1.3:
        k4 = ease_out_cubic((t - 1.3) / 0.5)
        d = ImageDraw.Draw(c); L = 420 * k4
        d.rectangle((W / 2 - L, 1250, W / 2 + L, 1258), fill=YEL + (255,))
    if t >= 1.55:
        k5 = ease_out_cubic((t - 1.55) / 0.4)
        place(c, text_img("CONFIRA OS PREÇOS", "mont8", 64, WHITE), W / 2, 1340 + (1 - k5) * 60, alpha=k5)
    sparkles(c, t, 1.0)
    flash(c, 1 - t / 0.25)
    flash(c, 0.85 * (1 - (t - 1.0) / 0.18) if t >= 1.0 else 0)
    # saída
    if t > T_BANNER - 0.15:
        flash(c, (t - (T_BANNER - 0.15)) / 0.15)
    return c

def scene_banner(t):
    lt = t - T_BANNER
    c = background(t)
    snow(c, t)
    poles(c, t, ease_out_cubic(lt / 0.4))
    # VALORES pequeno no topo
    place(c, text_img("TABELA DE VALORES", "anton", 120, YEL, stroke=4, glow=(255, 60, 0)), W / 2, 420, scale=ease_out_back(lt / 0.4))
    # pílula vermelha com data
    k = ease_out_back(lt / 0.45, 1.6)
    pw, ph = 900, 300
    pill = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(pill)
    d.rounded_rectangle((30, 40, pw + 30, ph + 40), 50, fill=(0, 0, 0, 160))
    pill = pill.filter(ImageFilter.GaussianBlur(14)); d = ImageDraw.Draw(pill)
    d.rounded_rectangle((30, 30, pw + 30, ph + 30), 50, fill=(255, 255, 255, 255))
    d.rounded_rectangle((44, 44, pw + 16, ph + 16), 40, fill=RED + (255,))
    place(c, pill, W / 2 + (1 - k) * W, 900)
    if lt > 0.25:
        k2 = ease_out_cubic((lt - 0.25) / 0.3)
        place(c, text_img("NOVA TABELA A PARTIR DE", "mont8", 50, WHITE, shadow=False), W / 2, 830, alpha=k2)
        pop = ease_out_elastic((lt - 0.4) / 0.8) if lt > 0.4 else 0
        place(c, text_img("01/12/2025", "anton", 150, YEL, stroke=4), W / 2, 950, scale=0.4 + 0.6 * pop, alpha=clamp((lt - 0.4) / 0.1))
    if lt > 0.6:
        k3 = ease_out_cubic((lt - 0.6) / 0.4)
        place(c, text_img("Di Maria Barbershop", "mont7", 56, WHITE), W / 2, 1220 + (1 - k3) * 40, alpha=k3)
    sparkles(c, t)
    flash(c, 1 - lt / 0.2)
    return c

ITEM_IMG_CACHE = {}
def scene_item(t, i):
    name, price = SERVICOS[i]
    lt = t - (T_ITEMS + i * SLOT)
    beat = (lt % 0.5) / 0.5
    pulse = 0.018 * (1 - ease_out_cubic(beat / 0.6))
    c = background(t, pulse)
    snow(c, t)
    poles(c, t)
    # número grande vazado ao fundo
    num = f"{i + 1:02d}"
    place(c, outline_img(num, "anton", 620, (255, 255, 255), 5), W / 2 + 140 - lt * 40, 760, alpha=0.22)
    # contador superior
    place(c, text_img(f"SERVIÇO {i + 1:02d}/{len(SERVICOS):02d}", "mont8", 40, YEL, spacing=6, shadow=False), W / 2, 270)
    # barra de progresso
    d = ImageDraw.Draw(c)
    prog = (i + clamp(lt / SLOT)) / len(SERVICOS)
    d.rounded_rectangle((140, 320, W - 140, 332), 6, fill=(255, 255, 255, 60))
    d.rounded_rectangle((140, 320, 140 + (W - 280) * prog, 332), 6, fill=YEL + (255,))
    # faixa vermelha atrás do nome (entra rasgando)
    kb = ease_out_cubic(lt / 0.3)
    band_h = 0
    lines = wrap(name.upper(), "mont9", 112, 900)
    band_h = 150 * len(lines) + 40
    by = 820 - band_h / 2
    x1 = -40 + (W + 80) * kb
    d.polygon([(-40, by), (x1, by), (x1 - 60, by + band_h), (-40, by + band_h)], fill=RED + (235,))
    if x1 - 60 > -40:
        d.rectangle((-40, by + band_h - 10, x1 - 60, by + band_h), fill=YEL + (255,))
    # nome: entra com chicote (whip) da direita
    kn = ease_out_back((lt - 0.05) / 0.4, 1.4)
    for j, ln in enumerate(lines):
        img = text_img(ln, "mont9", 112, WHITE, stroke=3)
        y = by + 20 + 150 * j + 75
        place(c, img, W / 2 + (1 - kn) * 900 + j * (1 - kn) * 200, y, alpha=clamp((lt - 0.05) / 0.15))
    # preço: slam no tempo 2 do compasso (0.5s), com contador
    if lt >= 0.45:
        kp = clamp((lt - 0.45) / 0.35)
        val = price if kp >= 1 else max(1, int(round(price * ease_out_cubic(kp))))
        sc = ease_out_back((lt - 0.45) / 0.35, 2.6)
        img = text_img(f"R${val},00", "anton", 230, YEL, stroke=7, glow=(255, 70, 0))
        sx, sy = shake(lt, 0.45, 20, 0.3)
        wob = math.sin(lt * 6) * 2.0
        place(c, img, W / 2 + sx, 1260 + sy, scale=sc, rot=wob * (lt > 0.8))
    if lt >= 0.85:
        kk = ease_out_cubic((lt - 0.85) / 0.3)
        place(c, text_img("Di Maria Barbershop", "mont7", 46, WHITE, shadow=True), W / 2, 1500, alpha=0.85 * kk)
    handle(c, H - 150, alpha=0.9)
    sparkles(c, t, 0.7)
    # flash no slam do preço + flash de corte
    flash(c, 0.55 * (1 - (lt - 0.45) / 0.15) if lt >= 0.45 else 0)
    flash(c, 0.9 * (1 - lt / 0.12))
    # saída: desliza pra esquerda com escurecida
    if lt > SLOT - 0.12:
        flash(c, (lt - (SLOT - 0.12)) / 0.12 * 0.6, (0, 0, 0))
    return c

def scene_full(t):
    lt = t - T_FULL
    c = background(t)
    snow(c, t)
    poles(c, t)
    k = ease_out_back(lt / 0.6, 1.3)
    z = (0.62 + 0.30 * k) * (1 + 0.05 * clamp((lt - 0.6) / 2.4))
    rot = (1 - ease_out_cubic(lt / 0.6)) * 12
    cy = 1000
    place(c, CARD_SH, W / 2, cy + 20, scale=z, alpha=clamp(lt / 0.3))
    place(c, CARD, W / 2, cy, scale=z, rot=rot)
    kt = ease_out_cubic((lt - 0.2) / 0.4)
    place(c, text_img("TABELA COMPLETA", "anton", 110, YEL, stroke=4, glow=(255, 60, 0)), W / 2, 200 - (1 - kt) * 120, alpha=kt)
    if lt > 1.0:
        kb = ease_out_back((lt - 1.0) / 0.4, 2)
        tag = text_img("SALVA PRA NÃO ESQUECER!", "mont9", 58, (20, 10, 10), shadow=False)
        box = Image.new("RGBA", (tag.width + 20, tag.height - 30), YEL + (255,))
        box.alpha_composite(tag, (10, -15))
        place(c, box, W / 2, 1810, scale=kb, rot=-3)
    sparkles(c, t)
    flash(c, 1 - lt / 0.2)
    return c

def scene_cta(t):
    lt = t - T_CTA
    c = background(t)
    snow(c, t)
    poles(c, t)
    k = ease_out_back(lt / 0.5, 1.6)
    place(c, LOGO_SH, W / 2 + 8, 420 + 12, scale=0.75 * k, alpha=0.8)
    place(c, LOGO, W / 2, 420, scale=0.75 * k)
    sx, sy = shake(lt, 0.25, 24)
    if lt > 0.25:
        k2 = clamp((lt - 0.25) / 0.2)
        sc = 2.4 - 1.4 * k2
        beat = (lt % 0.5) / 0.5
        p = 1 + 0.05 * (1 - ease_out_cubic(beat / 0.5))
        place(c, text_img("AGENDE JÁ", "anton", 210, YEL, stroke=6, glow=(255, 60, 0)), W / 2 + sx, 820 + sy, scale=sc * p, alpha=k2)
        place(c, text_img("SEU HORÁRIO", "mont9", 92, WHITE, stroke=2), W / 2 + sx, 990 + sy, alpha=k2)
    if lt > 0.6:
        k3 = ease_out_back((lt - 0.6) / 0.4, 1.8)
        ig = text_img("@barbearia_dimaria", "mont9", 72, WHITE, shadow=False)
        box = Image.new("RGBA", (ig.width + 10, ig.height - 20), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width, box.height), 28, fill=RED + (255,))
        box.alpha_composite(ig, (5, -10))
        place(c, box, W / 2, 1250, scale=k3)
    if lt > 0.9:
        k4 = ease_out_cubic((lt - 0.9) / 0.4)
        place(c, text_img("siga também  @mingal07", "mont8", 56, WHITE), W / 2, 1400 + (1 - k4) * 50, alpha=k4)
    if lt > 1.3:
        k5 = ease_out_cubic((lt - 1.3) / 0.4)
        place(c, text_img("CHAMA NO DIRECT!", "bebas", 110, YEL, stroke=3), W / 2, 1600, alpha=k5, scale=0.8 + 0.2 * k5)
    sparkles(c, t, 1.2)
    flash(c, 1 - lt / 0.2)
    flash(c, 0.6 * (1 - (lt - 0.25) / 0.15) if lt >= 0.25 else 0)
    if lt > 2.7:
        flash(c, (lt - 2.7) / 0.3, (0, 0, 0))
    return c

def frame(t):
    if t < T_BANNER: return scene_intro(t)
    if t < T_ITEMS: return scene_banner(t)
    if t < T_FULL: return scene_item(t, int((t - T_ITEMS) // SLOT))
    if t < T_CTA: return scene_full(t)
    return scene_cta(t)

# ---------------------------------------------------------------- áudio (batida 120 BPM sintetizada)
def make_audio(path):
    sr = 44100; n = int(sr * DUR); out = np.zeros(n, np.float32)
    rng = np.random.default_rng(3)
    def add(sig, t0, gain=1.0):
        i = int(t0 * sr); j = min(n, i + len(sig))
        if i < n: out[i:j] += sig[: j - i] * gain
    def kick():
        tt = np.arange(int(0.35 * sr)) / sr
        f = 50 + 110 * np.exp(-tt * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 9)
    def hat():
        tt = np.arange(int(0.06 * sr)) / sr
        x = rng.standard_normal(len(tt)); x = np.diff(np.concatenate([[0], x]))
        return x * np.exp(-tt * 70) * 0.35
    def clap():
        tt = np.arange(int(0.2 * sr)) / sr
        x = rng.standard_normal(len(tt))
        env = np.exp(-tt * 25) + 0.6 * np.exp(-np.maximum(tt - 0.012, 0) * 25) * (tt > 0.012)
        return np.diff(np.concatenate([[0], x])) * env * 0.4
    def bass(freq, dur):
        tt = np.arange(int(dur * sr)) / sr
        s = np.sin(2 * np.pi * freq * tt) + 0.3 * np.sin(4 * np.pi * freq * tt)
        return s * np.minimum(1, tt * 80) * np.exp(-tt * 3.2) * 0.45
    def whoosh(dur=0.45):
        m = int(dur * sr); x = rng.standard_normal(m)
        tt = np.arange(m) / m
        env = np.sin(np.pi * tt) ** 2
        # filtro passa-baixa variável (simples)
        y = np.zeros(m); a = 0.0
        for k in range(m):
            alpha = 0.02 + 0.5 * tt[k]
            a += alpha * (x[k] - a); y[k] = a
        return y * env * 0.9
    def boom():
        tt = np.arange(int(0.9 * sr)) / sr
        f = 40 + 80 * np.exp(-tt * 12)
        return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 4) * 1.1
    WH = whoosh(); BM = boom(); K = kick(); HT = hat(); CL = clap()
    notes = [55.0, 55.0, 65.41, 49.0]  # A1 A1 C2 G1
    bt = 0.5
    for b in range(int(DUR / bt)):
        t0 = b * bt
        if t0 < 1.0 or t0 >= DUR - 0.5: continue
        add(K, t0, 0.95)
        add(HT, t0 + bt / 2, 0.8)
        if b % 2 == 1: add(CL, t0, 0.7)
        if b % 2 == 0: add(bass(notes[(b // 8) % 4], 0.9), t0)
    add(BM, 1.0); add(BM, T_CTA + 0.25, 0.9)
    for tw in [T_BANNER - 0.25, T_ITEMS - 0.25, T_FULL - 0.25, T_CTA - 0.25] + [T_ITEMS + i * SLOT - 0.25 for i in range(1, len(SERVICOS))]:
        add(WH, tw, 0.8)
    for i in range(len(SERVICOS)):
        add(BM[: int(0.4 * sr)], T_ITEMS + i * SLOT + 0.45, 0.5)
    fade = np.ones(n); fl = int(0.6 * sr); fade[-fl:] = np.linspace(1, 0, fl)
    out *= fade
    out = np.tanh(out * 1.1) * 0.85
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[3] == "preview":
        for ts in [float(x) for x in sys.argv[4].split(",")]:
            frame(ts).convert("RGB").save(f"{S}/prev_{ts:05.2f}.jpg", quality=85)
        sys.exit()
    wav = S + "/beat.wav"; make_audio(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f_ in range(N):
        p.stdin.write(frame(f_ / FPS).convert("RGB").tobytes())
        if f_ % 90 == 0: print("frame", f_, flush=True)
    p.stdin.close(); p.wait()
    print("ok", OUT)
