# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
"""
air_viewer.py — GUI simple para ver animaciones .AIR (Python 2.7)

Controles:
  Botones (2 filas x 10 columnas): Frame-/Play/Frame+/Loop/Grid/Zoom-/Zoom+/FlipH/FlipV/BoxFlip
                                   BoxH/BoxV/Sprite/⟲ Rewind/FF-Auto/PrevAnim/NextAnim/(huecos libres)
  Teclas : ← → frame step | ESPACIO play/pause | [ y ] cambia anim | -/+ zoom
           G grid | L loop | H/V flips | B BoxFlip link | J BoxH | K BoxV | S Sprite on/off | R Rewind | F FF-Auto
"""

import os, sys
import pygame

# Asegura que el directorio del script esté en sys.path
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from air_parser import parse_air
from air_draw_anim import Animator, SpriteRouter, ListSource, draw_anim_frame, SpriteSource

# ---------------------- Layout / Visual ----------------------
W, H          = 1060, 720
TOP_HUD_H     = 120           # HUD arriba
BTN_ROWS      = 2
BTN_COLS      = 10
BTN_W, BTN_H  = 90, 35
BTN_MARGIN    = 10
BOT_PANEL_H   = BTN_MARGIN*3 + BTN_ROWS*BTN_H + (BTN_ROWS-1)*BTN_MARGIN  # altura panel inferior
BG            = (16, 16, 16)
GRID_LIGHT    = (40, 40, 40)
GRID_DARK     = (28, 28, 28)
PANEL_BG      = (32, 32, 32)
BTN_BG        = (70, 70, 70)
BTN_HL        = (100, 120, 180)
TXT           = (240, 240, 240)
FPS           = 60

GRID_Y0       = TOP_HUD_H
GRID_Y1       = H - BOT_PANEL_H

# ---------------------- UI helpers ---------------------------
def draw_grid(surf, cell=32):
    # verticales
    for x in range(0, W, cell):
        c = GRID_DARK if (x // cell) % 2 == 0 else GRID_LIGHT
        pygame.draw.line(surf, c, (x, GRID_Y0), (x, GRID_Y1))
    # horizontales
    y = GRID_Y0
    band = 0
    while y <= GRID_Y1:
        c = GRID_DARK if band % 2 == 0 else GRID_LIGHT
        pygame.draw.line(surf, c, (0, y), (W, y))
        y += cell
        band += 1

def make_button(x, y, w, h, label):
    return {"rect": pygame.Rect(x, y, w, h), "label": label}

def draw_button(screen, btn, font, hover=False):
    color = BTN_HL if hover else BTN_BG
    pygame.draw.rect(screen, color, btn["rect"], 0)
    pygame.draw.rect(screen, (0, 0, 0), btn["rect"], 1)
    txt = font.render(btn["label"], True, TXT)
    tr = txt.get_rect(center=btn["rect"].center)
    screen.blit(txt, tr)

# ---------------------- Boxes helpers ------------------------
DBG_RED_FILL  = (255,  40,  40, 110)  # Clsn1
DBG_BLUE_FILL = ( 40, 120, 255, 110)  # Clsn2
DBG_RED_LINE  = (255,  60,  60)
DBG_BLUE_LINE = ( 60, 140, 255)

def _rect_from_box(px, py, x1, y1, x2, y2, xoff, yoff, scale):
    x1 += xoff; x2 += xoff
    y1 += yoff; y2 += yoff
    left   = min(x1, x2) * scale
    right  = max(x1, x2) * scale
    topY   = max(y1, y2) * scale
    botY   = min(y1, y2) * scale
    scr_left = int(px + left)
    scr_top  = int(py - topY)
    width    = int(right - left)
    height   = int(topY - botY)
    return pygame.Rect(scr_left, scr_top, width, height)

def _apply_flip_to_box(x1, y1, x2, y2, flip):
    if flip and 'H' in flip: x1, x2 = -x2, -x1
    if flip and 'V' in flip: y1, y2 = -y2, -y1
    return x1, y1, x2, y2

def draw_boxes_custom(screen, px, py, boxes, xoff=0, yoff=0, scale=1.0,
                      flip_str=None, link_flip=False, line_thickness=2):
    if boxes is None: return
    w, h = screen.get_size()
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)

    def _paint(lst, fill_rgba, line_rgb):
        for b in lst:
            x1,y1,x2,y2 = b.x1,b.y1,b.x2,b.y2
            if link_flip and flip_str:
                x1,y1,x2,y2 = _apply_flip_to_box(x1,y1,x2,y2, flip_str)
            rect = _rect_from_box(px,py, x1,y1,x2,y2, xoff,yoff, scale)
            pygame.draw.rect(overlay, fill_rgba, rect, 0)
            pygame.draw.rect(overlay, line_rgb, rect, line_thickness)

    _paint(getattr(boxes,'clsn1',[]), DBG_RED_FILL,  DBG_RED_LINE)
    _paint(getattr(boxes,'clsn2',[]), DBG_BLUE_FILL, DBG_BLUE_LINE)
    screen.blit(overlay, (0,0))

# ---------------------- main viewer -------------------------
def main():
    if len(sys.argv) < 2:
        print("Uso: python air_viewer.py archivo.air [encoding]")
        sys.exit(1)

    air_path = sys.argv[1]
    encoding = sys.argv[2] if len(sys.argv) > 2 else "utf-8"

    air = parse_air(air_path, encoding)
    if not air.actions:
        print("No hay animaciones en", air_path); return

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("AIR Viewer — parser+drawer integrados (Py2.7)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 16)
    font_small = pygame.font.SysFont("consolas", 14)

    # Dummy invisible
    dummy = pygame.Surface((64, 64), pygame.SRCALPHA)
    class DummySource(SpriteSource):
        def __init__(self, surf): self._surf = surf
        def get_surface(self, key): return self._surf

    router = SpriteRouter(default_source=DummySource(dummy))
    lst = ListSource([dummy] * 256)
    router.register("list", lst)
    for i in range(256):
        router.set_remap(0, i, "list", (0, i))

    anim_keys = sorted(air.actions.keys())

    # --- Estado ---
    state = {
        "cur_anim_i": 0,
        "anim": air.actions[anim_keys[0]],
        "animator": Animator(air.actions[anim_keys[0]]),
        "playing": True,
        "zoom": 1.0,
        "cx": W // 2,
        "cy": GRID_Y0 + (GRID_Y1 - GRID_Y0)//2,  # centro entre HUD y panel de botones
        "show_grid": True,
        "loop_on": True,
        "box_flip_linked": True,     # cajas siguen flip (sprite + H/V)
        "box_extra_flip_h": False,   # flips extra SOLO cajas
        "box_extra_flip_v": False,
        "show_sprite": False,        # sprite oculto por defecto
        "ff_auto": True,             # rebobinado auto si último frame time=-1
    }
    flags = {"flip_h": False, "flip_v": False}

    # --------- Botonera en 2 filas x 10 columnas -----------
    # Orden deseado (<=20). Si faltan huecos, se dejan en blanco.
    labels = [
        "⏮ Frame-", "▶/⏸ Play", "Frame+ ⏭", "Loop", "Grid",
        "Zoom-", "Zoom+", "FlipH", "FlipV", "BoxFlip",
        "BoxH", "BoxV", "Sprite", "⟲ Rewind", "FF-Auto",
        "PrevAnim", "NextAnim"
    ]
    buttons = []
    # cálculo de área usable y offset para centrar rejilla
    total_w = BTN_COLS*BTN_W + (BTN_COLS-1)*BTN_MARGIN
    start_x = (W - total_w)//2
    # fila 0 y fila 1: y base dentro del panel inferior
    base_y = GRID_Y1 + BTN_MARGIN   # inicio del panel de botones
    row0_y = base_y + BTN_MARGIN
    row1_y = row0_y + BTN_H + BTN_MARGIN
    for idx, label in enumerate(labels):
        r = idx // BTN_COLS
        c = idx % BTN_COLS
        if r >= BTN_ROWS: break
        x = start_x + c*(BTN_W + BTN_MARGIN)
        y = row0_y if r == 0 else row1_y
        buttons.append(make_button(x, y, BTN_W, BTN_H, label))

    # Hotkeys
    KEY_LEFT, KEY_RIGHT = pygame.K_LEFT, pygame.K_RIGHT
    KEY_SPACE = pygame.K_SPACE
    KEY_PREV, KEY_NEXT = pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET
    KEY_MINUS, KEY_PLUS = pygame.K_MINUS, pygame.K_EQUALS
    KEY_G, KEY_L, KEY_H, KEY_V = pygame.K_g, pygame.K_l, pygame.K_h, pygame.K_v
    KEY_B, KEY_J, KEY_K, KEY_S, KEY_R, KEY_F = pygame.K_b, pygame.K_j, pygame.K_k, pygame.K_s, pygame.K_r, pygame.K_f

    # --- Helpers ---
    def next_anim(delta):
        i = (state["cur_anim_i"] + delta) % len(anim_keys)
        state["cur_anim_i"] = i
        state["anim"] = air.actions[anim_keys[i]]
        state["animator"] = Animator(state["anim"])

    def toggle_flip_h(): flags["flip_h"] = not flags["flip_h"]
    def toggle_flip_v(): flags["flip_v"] = not flags["flip_v"]

    def do_rewind():
        nxt = state["anim"].loopstart_idx if (state["anim"].loopstart_idx is not None) else 0
        state["animator"].frame_idx = max(0, min(state["anim"].frame_count()-1, nxt))
        state["animator"].tick_in_frame = 0

    def combined_flip(orig_flip):
        s = (orig_flip or '')
        if flags["flip_h"]: s += 'H'
        if flags["flip_v"]: s += 'V'
        out = ''
        if 'H' in s: out += 'H'
        if 'V' in s: out += 'V'
        return out

    def box_flip_for(orig_flip):
        base = combined_flip(orig_flip) if state["box_flip_linked"] else ''
        if state["box_extra_flip_h"]:
            base = (base.replace('H','')) if ('H' in base) else ('H' + base)
        if state["box_extra_flip_v"]:
            base = (base.replace('V','')) if ('V' in base) else (base + 'V')
        final = ''
        if 'H' in base: final += 'H'
        if 'V' in base: final += 'V'
        return final

    # -------------------- Main loop -------------------------
    running = True
    while running:
        dt = clock.tick(FPS)
        mouse = pygame.mouse.get_pos()
        click = False

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: running = False
                elif ev.key == KEY_LEFT and state["anim"].frame_count() > 0:
                    state["animator"].frame_idx = max(0, state["animator"].frame_idx - 1); state["animator"].tick_in_frame = 0
                elif ev.key == KEY_RIGHT and state["anim"].frame_count() > 0:
                    state["animator"].frame_idx = min(state["anim"].frame_count() - 1, state["animator"].frame_idx + 1); state["animator"].tick_in_frame = 0
                elif ev.key == KEY_SPACE: state["playing"] = not state["playing"]
                elif ev.key == KEY_PREV:  next_anim(-1)
                elif ev.key == KEY_NEXT:  next_anim(+1)
                elif ev.key == KEY_MINUS: state["zoom"] = max(0.25, round(state["zoom"] - 0.1, 2))
                elif ev.key == KEY_PLUS:  state["zoom"] = min(6.0, round(state["zoom"] + 0.1, 2))
                elif ev.key == KEY_G:     state["show_grid"] = not state["show_grid"]
                elif ev.key == KEY_L:     state["loop_on"] = not state["loop_on"]
                elif ev.key == KEY_H:     toggle_flip_h()
                elif ev.key == KEY_V:     toggle_flip_v()
                elif ev.key == KEY_B:     state["box_flip_linked"] = not state["box_flip_linked"]
                elif ev.key == KEY_J:     state["box_extra_flip_h"] = not state["box_extra_flip_h"]
                elif ev.key == KEY_K:     state["box_extra_flip_v"] = not state["box_extra_flip_v"]
                elif ev.key == KEY_S:     state["show_sprite"] = not state["show_sprite"]
                elif ev.key == KEY_R:     do_rewind()
                elif ev.key == KEY_F:     state["ff_auto"] = not state["ff_auto"]
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                click = True

        # Avance del animador (60 ticks/s)
        if state["playing"] and state["anim"].frame_count() > 0:
            ticks = int(dt * 60 / 1000.0)
            state["animator"].update_ticks(ticks)
            if state["animator"].frame_idx >= state["anim"].frame_count():
                if state["loop_on"]: do_rewind()
                else:
                    state["animator"].frame_idx = state["anim"].frame_count() - 1
                    state["playing"] = False
            else:
                last = state["anim"].frame_count() - 1
                curf = state["anim"].frames[state["animator"].frame_idx]
                if (state["animator"].frame_idx == last and curf.time == -1
                    and state["loop_on"] and state["ff_auto"]):
                    do_rewind()

        # ------------------- Dibujo --------------------------
        screen.fill(BG)

        # HUD arriba
        pygame.draw.rect(screen, PANEL_BG, (0, 0, W, TOP_HUD_H))
        if state["anim"].frame_count() > 0:
            fr = state["anim"].frames[state["animator"].frame_idx]
            info = [
                "Action: %d" % state["anim"].number,
                "Frame: %d / %d" % (state["animator"].frame_idx + 1, state["anim"].frame_count()),
                "Group: %d  Index: %d" % (fr.group, fr.image),
                "xoff=%d yoff=%d  time=%d ticks" % (fr.xoff, fr.yoff, fr.time),
                "Flip(.air): %s  ViewFlip: H=%s V=%s  Trans: %s" %
                ((fr.flip or "none"), flags["flip_h"], flags["flip_v"], fr.trans or "none"),
                "LoopStart: %s  Playing: %s" % (state["anim"].loopstart_idx, state["playing"]),
                "Zoom: %.2fx  Loop: %s  Grid: %s" %
                (state["zoom"], state["loop_on"], state["show_grid"]),
                "Boxes: link=%s  BoxH=%s  BoxV=%s  Sprite=%s  FF-Auto=%s" %
                (state["box_flip_linked"], state["box_extra_flip_h"], state["box_extra_flip_v"], state["show_sprite"], state["ff_auto"]),
                "Tips: H/V giran sprite; J/K giran SOLO cajas; B alterna link; R/F Rewind/FF-Auto; [ / ] anim."
            ]
            for i, line in enumerate(info):
                t = font_small.render(line, True, TXT)
                screen.blit(t, (20, 8 + i * 16))

        # Grid en el área central
        if state["show_grid"]:
            draw_grid(screen)

        # Sprite + Cajas en el área central
        if state["anim"].frame_count() > 0:
            f = state["anim"].frames[state["animator"].frame_idx]
            orig_flip = f.flip

            # sprite (opcional)
            if state["show_sprite"]:
                merged = combined_flip(orig_flip)
                f.flip = merged
                try:
                    draw_anim_frame(screen, state["cx"], state["cy"], state["anim"], router,
                                    state["animator"].frame_idx, scale=state["zoom"], draw_boxes=False)
                finally:
                    f.flip = orig_flip

            # cajas (siguen flip combinado + extras si están activos)
            boxes = state["anim"].resolve_boxes_for(state["animator"].frame_idx)
            flip_boxes = box_flip_for(orig_flip)
            draw_boxes_custom(
                screen, state["cx"], state["cy"], boxes,
                xoff=int(f.xoff * state["zoom"]),
                yoff=int(f.yoff * state["zoom"]),
                scale=state["zoom"],
                flip_str=flip_boxes,
                link_flip=(flip_boxes != '')
            )

        # Panel inferior (botonera)
        pygame.draw.rect(screen, PANEL_BG, (0, GRID_Y1, W, BOT_PANEL_H))
        for btn in buttons:
            hovered = btn["rect"].collidepoint(mouse)
            draw_button(screen, btn, font, hovered)

        if click:
            for btn in buttons:
                if btn["rect"].collidepoint(mouse):
                    lbl = btn["label"]
                    if "Frame-" in lbl and state["anim"].frame_count() > 0:
                        state["animator"].frame_idx = max(0, state["animator"].frame_idx - 1); state["animator"].tick_in_frame = 0
                    elif "Frame+ " in lbl and state["anim"].frame_count() > 0:
                        state["animator"].frame_idx = min(state["anim"].frame_count() - 1, state["animator"].frame_idx + 1); state["animator"].tick_in_frame = 0
                    elif "Play" in lbl:      state["playing"] = not state["playing"]
                    elif "Loop" in lbl:      state["loop_on"] = not state["loop_on"]
                    elif "Grid" in lbl:      state["show_grid"] = not state["show_grid"]
                    elif "Zoom-" in lbl:     state["zoom"] = max(0.25, round(state["zoom"] - 0.1, 2))
                    elif "Zoom+" in lbl:     state["zoom"] = min(6.0, round(state["zoom"] + 0.1, 2))
                    elif "FlipH" in lbl:     toggle_flip_h()
                    elif "FlipV" in lbl:     toggle_flip_v()
                    elif "BoxFlip" in lbl:   state["box_flip_linked"] = not state["box_flip_linked"]
                    elif "BoxH" in lbl:      state["box_extra_flip_h"] = not state["box_extra_flip_h"]
                    elif "BoxV" in lbl:      state["box_extra_flip_v"] = not state["box_extra_flip_v"]
                    elif "Sprite" in lbl:    state["show_sprite"] = not state["show_sprite"]
                    elif "Rewind" in lbl:    do_rewind()
                    elif "FF-Auto" in lbl:   state["ff_auto"] = not state["ff_auto"]
                    elif "PrevAnim" in lbl:  next_anim(-1)
                    elif "NextAnim" in lbl:  next_anim(+1)

        pygame.display.flip()

    pygame.quit()

# ----------------------------------------------------------
if __name__ == "__main__":
    main()
