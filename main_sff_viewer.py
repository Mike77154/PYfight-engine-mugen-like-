# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import os
import io
import pygame

from viewer_lib import (
    SFFSpriteBank,
    load_act_palette,
    _flatten_palette_rgb,  # sólo para HUD
)

from sff_v1 import SFFv1

# --- Compatibilidad SFF v2 (adaptador a la interfaz esperada por SFFSpriteBank)
try:
    from sff_v2 import SFFv2
    _SFFV2_AVAILABLE = True
except Exception:
    _SFFV2_AVAILABLE = False

# PaletteManager (opcional). Si existe y algún día quieres usarlo,
# puedes integrarlo fácilmente; por ahora mantenemos SFFSpriteBank.
try:
    from palette_mgr import PaletteManager  # noqa: F401
    _PALETTE_MGR_AVAILABLE = True
except Exception:
    _PALETTE_MGR_AVAILABLE = False

# -------------------------------------------------------------------
# Config ventana
WIN_W, WIN_H = 1024, 768
BG_COLOR = (24, 24, 28)
FG_COLOR = (240, 240, 240)

# Escalado: nearest (sin halos) por defecto; toggle [N]
USE_SMOOTH = False
USE_FULL_PALETTE = True    # ← true = usa ACT completa (256 colores)
REVERSE_PALETTE = True   # ← true = invierte el ACT completo
DEFAULT_ACT_MODE = "full"   # "full", "slot" o "auto"

# -------------------------------------------------------------------
# Helpers UI
def prompt(msg):
    try:
        return raw_input(msg).strip()
    except NameError:
        return input(msg).strip()

def draw_checker(surface, cell=16):
    w, h = surface.get_size()
    c1 = (60, 60, 60)
    c2 = (80, 80, 80)
    y = 0
    while y < h:
        x = 0
        flip = (y // cell) % 2
        while x < w:
            r = pygame.Rect(x, y, cell, cell)
            pygame.draw.rect(surface, c1 if flip else c2, r)
            flip = 1 - flip
            x += cell
        y += cell

def draw_axis_cross(surface, cx, cy, color=(255, 64, 64)):
    pygame.draw.line(surface, color, (cx - 12, cy), (cx + 12, cy))
    pygame.draw.line(surface, color, (cx, cy - 12), (cx, cy + 12))
    pygame.draw.circle(surface, color, (int(cx), int(cy)), 2)

def blit_center(dst, src, zoom=1.0, pan=(0, 0)):
    sw, sh = src.get_size()
    dw, dh = dst.get_size()
    tw, th = int(sw * zoom), int(sh * zoom)
    img = src
    if zoom != 1.0:
        if USE_SMOOTH:
            try:
                img = pygame.transform.smoothscale(src, (tw, th))
            except Exception:
                img = pygame.transform.scale(src, (tw, th))
        else:
            img = pygame.transform.scale(src, (tw, th))  # nearest-neighbor
    x = dw // 2 - tw // 2 + int(pan[0])
    y = dh // 2 - th // 2 + int(pan[1])
    dst.blit(img, (x, y))
    return (x, y, tw, th)

# --- HUD de paletas (3 cuadriculas de 16x16 = 256 c/u) -----------------------
def draw_palette_grid(surface, flat_pal, topleft, cell=8, label="", font=None):
    if not flat_pal or len(flat_pal) < 768:
        if font and label:
            surface.blit(font.render(label + " (N/A)", True, (200, 160, 160)), topleft)
        return
    x0, y0 = topleft
    # etiqueta
    if font and label:
        surface.blit(font.render(label, True, (200, 200, 220)), (x0, y0 - 18))
    # cuadricula 16x16
    for idx in range(256):
        r = flat_pal[idx*3+0]
        g = flat_pal[idx*3+1]
        b = flat_pal[idx*3+2]
        col = (int(r)&255, int(g)&255, int(b)&255)
        cx = idx % 16
        cy = idx // 16
        rx = x0 + cx*cell
        ry = y0 + cy*cell
        pygame.draw.rect(surface, col, (rx, ry, cell, cell))
    # marco
    pygame.draw.rect(surface, (90, 90, 100), (x0, y0, 16*cell, 16*cell), 1)

# -------------------------------------------------------------------
# Adaptador: convierte SFFv2 -> interfaz compatible con SFFSpriteBank
#  - Crea .subfiles (lista de objetos con: group, image, axis_x, axis_y)
#  - Llena ._blob_cache[i] con PNGs en memoria (desde PIL) para cada sprite
#    de forma lazy (se genera on-demand al pedírselo el viewer).
class _SFFv2Adapter(object):
    class _SFEntry(object):
        __slots__ = ("group", "image", "axis_x", "axis_y")
        def __init__(self, g, i, ax, ay):
            self.group = g
            self.image = i
            self.axis_x = ax
            self.axis_y = ay

    def __init__(self, sffv2):
        self._sffv2 = sffv2
        self.subfiles = []
        self._blob_cache = {}  # index -> PNG bytes (on demand)
        # precarga metadatos de sprites (rápido)
        for idx, sp in enumerate(self._sffv2.sprites):
            self.subfiles.append(self._SFEntry(sp['group'], sp['number'], sp['xaxis'], sp['yaxis']))

    def _ensure_blob(self, index):
        if index in self._blob_cache:
            return True
        try:
            im, meta = self._sffv2.get_pil_indexed(index)
            if im is None:
                return False
            # Exportar a PNG in-memory
            bio = io.BytesIO()
            im.save(bio, format="PNG")
            self._blob_cache[index] = bio.getvalue()
            return True
        except Exception:
            return False

    # Para SFFSpriteBank.has_blob / surface_for_index
    def get_blob(self, index):
        ok = self._ensure_blob(index)
        return self._blob_cache.get(index) if ok else None

# -------------------------------------------------------------------
def _open_sff_auto(path):
    """
    Abre SFF v1 o SFF v2 automáticamente.
    Devuelve: (sff_like, version_str)
      - v1: instancia SFFv1
      - v2: instancia _SFFv2Adapter (envolviendo SFFv2)
    Lanza excepción si no puede abrir.
    """
    # Intentar SFFv1 primero (su propio detector lanza si ve v2)
    try:
        sff1 = SFFv1(path)
        return sff1, "SFF v1"
    except Exception as e1:
        # Si es v2, SFFv1 te da un ValueError explícito; probamos v2
        if _SFFV2_AVAILABLE:
            try:
                sff2 = SFFv2(path)
                sff_adapt = _SFFv2Adapter(sff2)
                return sff_adapt, "SFF v2"
            except Exception as e2:
                raise RuntimeError("No pude abrir como v1 (%s) ni v2 (%s)" % (e1, e2))
        else:
            raise

# -------------------------------------------------------------------
def main():
    # Parse args:  sff_path [act_path]
    act_path = None
    args = []
    for a in sys.argv[1:]:
        if a.lower().endswith(".act"):
            act_path = a
        else:
            args.append(a)

    if len(args) < 1:
        path = prompt("Ruta a .sff (v1/v2): ")
    else:
        path = args[0]
    if not os.path.exists(path):
        print("No existe:", path)
        return 1

    # Preguntar ACT si no vino por CLI
    if not act_path:
        p = prompt("Ruta a .act (Enter para omitir): ")
        act_path = p if p else None

    pygame.init()

    # Abrimos el SFF auto (v1 o v2 con adaptador)
    try:
        sff_like, vstr = _open_sff_auto(path)
    except Exception as e:
        print("No pude abrir SFF:", e)
        return 2

    pygame.display.set_caption("SFF Viewer (%s) - pygame + ACT" % vstr)
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,monospace", 16)

    # --- Banco de sprites ---
    bank = SFFSpriteBank(sff_like)

    # Indexar paletas embebidas (solo PCX con paleta; en v2 con PNG indexado también sirve)
    bank.index_all_palettes()

    # Configuración base
    bank.set_use_transparency(True)
    bank.set_transparent_index(0)
    bank.set_auto_transparency(False)
    bank.set_auto_donor_by_groupimage(9000, 0)

    # Cargar paleta ACT si existe
    if act_path and os.path.exists(act_path):
        pal = load_act_palette(act_path)
        if pal:
            bank.set_global_act(pal)

            # Aplica modo por flag global
            bank.set_act_mode(DEFAULT_ACT_MODE)

            # Ajustes adicionales según modo
            if DEFAULT_ACT_MODE == "full":
                bank.set_act_reverse_full(REVERSE_PALETTE)
            elif DEFAULT_ACT_MODE == "slot":
                bank.set_act_slot_start(16, 16)
                bank.set_act_reverse(REVERSE_PALETTE)

    # Estado UI
    idx = 0
    # Si es v2 con adaptador, garantizamos blob on-demand
    if hasattr(sff_like, "get_blob"):
        if sff_like.get_blob(idx) is None:
            # buscar siguiente con blob
            j = None
            for k in range(len(sff_like.subfiles)):
                if sff_like.get_blob(k) is not None:
                    j = k; break
            if j is not None:
                idx = j
    else:
        if not bank.has_blob(idx):
            nxt = bank.next_with_blob(idx)
            if nxt is not None:
                idx = nxt

    zoom = 1.0
    panx, pany = 0, 0
    show_checker = True
    show_axis = True
    show_palettes = True  # HUD de 3 paletas
    running = True

    PAN_STEP = 20
    PAN_STEP_FAST = 60

    # --------- Loop ----------
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                fast = bool(pygame.key.get_mods() & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL | pygame.KMOD_ALT))
                step = PAN_STEP_FAST if fast else PAN_STEP

                if ev.key == pygame.K_ESCAPE:
                    running = False

                # Navegación sprites (, .) y saltos ±10 (PgUp/PgDn)
                elif ev.key == pygame.K_PERIOD:
                    j = bank.next_with_blob(idx)
                    if j is not None: idx = j; panx = pany = 0
                elif ev.key == pygame.K_COMMA:
                    j = bank.prev_with_blob(idx)
                    if j is not None: idx = j; panx = pany = 0
                elif ev.key == pygame.K_PAGEUP:
                    for _ in range(10):
                        j = bank.next_with_blob(idx)
                        if j is None: break
                        idx = j
                    panx = pany = 0
                elif ev.key == pygame.K_PAGEDOWN:
                    for _ in range(10):
                        j = bank.prev_with_blob(idx)
                        if j is None: break
                        idx = j
                    panx = pany = 0

                # Zoom
                elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    zoom = min(zoom * 1.25, 32.0)
                elif ev.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                    zoom = max(zoom / 1.25, 0.03125)
                elif ev.key in (pygame.K_0, pygame.K_KP0):
                    zoom = 1.0; panx = pany = 0

                # Pan
                elif ev.key == pygame.K_LEFT:
                    panx -= step
                elif ev.key == pygame.K_RIGHT:
                    panx += step
                elif ev.key == pygame.K_UP:
                    pany -= step
                elif ev.key == pygame.K_DOWN:
                    pany += step

                # Toggles visuales
                elif ev.key == pygame.K_b:
                    show_checker = not show_checker
                elif ev.key == pygame.K_a:
                    show_axis = not show_axis
                elif ev.key == pygame.K_p:
                    show_palettes = not show_palettes
                elif ev.key == pygame.K_n:
                    global USE_SMOOTH
                    USE_SMOOTH = not USE_SMOOTH

                # Alpha ON/OFF (sigue ligado al índice 0)
                elif ev.key == pygame.K_t:
                    bank.set_use_transparency(not bank.use_transparency)

                # Modo ACT: auto/slot/full
                elif ev.key == pygame.K_m:
                    mode_cycle = {"auto":"slot", "slot":"full", "full":"auto"}
                    bank.set_act_mode(mode_cycle.get(getattr(bank, "act_mode", "auto"), "auto"))

                # Invertir rampa sloteada
                elif ev.key == pygame.K_r:
                    bank.set_act_reverse(not getattr(bank, "act_reverse", False))

                # Invertir ACT completa (256)
                elif ev.key == pygame.K_f:
                    bank.set_act_reverse_full(not getattr(bank, "act_reverse_full", False))

                # Cargar ACT en runtime
                elif ev.key == pygame.K_g:
                    p = prompt("Ruta a .act (Enter para cancelar): ")
                    if p and os.path.exists(p):
                        pal = load_act_palette(p)
                        if pal:
                            bank.set_global_act(pal)
                            # respetamos el modo actual; si quieres forzar:
                            # bank.set_act_mode("slot")
                            panx = pany = 0

        # -------- Render ----------
        screen.fill(BG_COLOR)
        if show_checker:
            draw_checker(screen, cell=16)

        surf, meta, warn = bank.surface_for_index(idx)
        info_lines = []
        if surf:
            x, y, tw, th = blit_center(screen, surf, zoom=zoom, pan=(panx, pany))
            if show_axis and meta:
                ax = x + int(meta["axis_x"] * zoom)
                ay = y + int(meta["axis_y"] * zoom)
                draw_axis_cross(screen, ax, ay, color=(255, 96, 96))
            info_lines.append("Sprite %d / %d" % (idx, bank.n))
            if meta:
                info_lines.append("g:%d i:%d  (%dx%d) axis=(%d,%d)" % (
                    meta["group"], meta["image"], meta["width"], meta["height"],
                    meta["axis_x"], meta["axis_y"]
                ))
        else:
            info_lines.append("Sin datos para %d" % idx)

        # Estado paleta/alpha
        mode_txt = getattr(bank, "act_mode", "auto").upper()
        info_lines.append("ACT mode=%s | Alpha(idx0)=%s | Smooth=%s" %
                          (mode_txt, "ON" if bank.use_transparency else "OFF",
                           "ON" if USE_SMOOTH else "OFF"))
        if warn:
            info_lines.append("WARN: %s" % warn)

        # Texto info
        ytxt = 8
        for line in info_lines:
            txt = font.render(line, True, FG_COLOR)
            screen.blit(txt, (8, ytxt))
            ytxt += 18

        # HUD paletas (sprite/donor/act)
        if show_palettes:
            pals = bank.current_palettes_for_index(idx)
            cell = 8
            xgrid = 8
            ygrid = WIN_H - (16*cell + 40)
            draw_palette_grid(screen, pals.get("sprite_flat"),
                              (xgrid, ygrid), cell=cell, label="SPRITE", font=font)
            draw_palette_grid(screen, pals.get("donor_flat"),
                              (xgrid + 16*cell + 20, ygrid), cell=cell, label="DONOR", font=font)
            draw_palette_grid(screen, pals.get("act_flat"),
                              (xgrid + (16*cell + 20)*2, ygrid), cell=cell, label="ACT", font=font)

        # Ayuda
        help_lines = [
            "[, / .] prev/next   [PgUp/PgDn] +/-10   [←/→/↑/↓] pan (Shift=rápido)",
            "[+/−/0] zoom in/out/reset   [B] checker   [A] axis   [P] palettes HUD",
            "[T] alpha idx0 on/off   [N] nearest/smooth   [G] cargar .ACT",
            "[M] ACT auto/slot/full   [R] reverse slot   [F] reverse full   [ESC] salir"
        ]
        for i, line in enumerate(help_lines):
            txt = font.render(line, True, (180, 180, 200))
            screen.blit(txt, (8, WIN_H - 60 + (i * 18)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0

if __name__ == "__main__":
    sys.exit(main())
