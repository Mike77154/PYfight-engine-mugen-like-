# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import os
import pygame

# libs propias
from viewer_lib import (
    SFFSpriteBank,
    load_act_palette,
    _flatten_palette_rgb,   # solo para dibujar grids
)

# parser sff v1 ya funcional
from sff_v1 import SFFv1

WIN_W, WIN_H = 1280, 800
BG_COLOR = (24, 24, 28)
FG_COLOR = (240, 240, 240)

GRID_X = 16
GRID_Y = 16
GRID_CELL = 10  # tamaño cuadrito paleta

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
        try:
            img = pygame.transform.smoothscale(src, (tw, th))
        except Exception:
            img = pygame.transform.scale(src, (tw, th))
    x = dw // 2 - tw // 2 + int(pan[0])
    y = dh // 2 - th // 2 + int(pan[1])
    dst.blit(img, (x, y))
    return (x, y, tw, th)

def prompt(texto):
    if sys.version_info[0] < 3:
        return raw_input(texto).strip()
    else:
        return input(texto).strip()

def draw_palette_grid(screen, x, y, pal_flat_or_rgb_list, title, cell=GRID_CELL):
    """
    Dibuja una cuadricula 16x16 de colores (256).
    Acepta pal plana (768) o lista de 256 (r,g,b).
    """
    # marco
    pygame.draw.rect(screen, (40,40,40), (x-6, y-20, 16*cell+12, 16*cell+26), 0)
    pygame.draw.rect(screen, (90,90,90), (x-6, y-20, 16*cell+12, 16*cell+26), 1)

    font = pygame.font.SysFont("consolas,monospace", 14)
    screen.blit(font.render(title, True, (180, 200, 255)), (x-2, y-18))

    # normaliza a lista rgb de 256
    rgb = None
    if pal_flat_or_rgb_list is None:
        rgb = [(0,0,0)] * 256
    elif isinstance(pal_flat_or_rgb_list, list) and len(pal_flat_or_rgb_list) == 256 \
         and isinstance(pal_flat_or_rgb_list[0], tuple):
        rgb = pal_flat_or_rgb_list
    else:
        # asumimos flat
        flat = pal_flat_or_rgb_list
        rgb = []
        for i in range(256):
            rgb.append((flat[i*3+0], flat[i*3+1], flat[i*3+2]))

    # cuadritos
    for row in range(16):
        for col in range(16):
            idx = row * 16 + col
            r, g, b = rgb[idx]
            rect = pygame.Rect(x + col*cell, y + row*cell, cell, cell)
            pygame.draw.rect(screen, (r, g, b), rect)
            pygame.draw.rect(screen, (30,30,30), rect, 1)

def main():
    # parse args: sff [act]
    act_path = None
    args = []
    for a in sys.argv[1:]:
        if a.lower().endswith(".act"):
            act_path = a
        else:
            args.append(a)

    if len(args) < 1:
        path = prompt("Ruta a .sff (v1): ")
    else:
        path = args[0]

    if not os.path.exists(path):
        print("No existe:", path)
        return 1

    if not act_path:
        p = prompt("Ruta a .act (Enter para saltar): ")
        act_path = p if p else None

    pygame.init()
    pygame.display.set_caption("SFF v1 Viewer (pygame + ACT + donor)")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,monospace", 16)

    try:
        sff = SFFv1(path)
    except Exception as e:
        print("No pude abrir SFF:", e)
        return 2

    bank = SFFSpriteBank(sff)

    # setup básico
    bank.set_transparent_index(0)
    bank.set_use_transparency(True)
    bank.set_act_target_groups(0, 4999)  # forzar ACT solo a gameplay

    # donor auto (9000,0)
    bank.set_auto_donor_by_groupimage(9000, 0)
    bank.use_donor_alignment = True
    bank.donor_anchor_start  = 16
    bank.donor_anchor_len    = 16

    # ACT inicial
    if act_path and os.path.exists(act_path):
        pal_raw = load_act_palette(act_path)
        if pal_raw:
            # si tu ACT viene “al revés”, puedes activar inversión después (tecla V)
            bank.set_global_act(pal_raw)

    idx = 0
    if not bank.has_blob(idx):
        nxt = bank.next_with_blob(idx)
        if nxt is not None:
            idx = nxt

    zoom = 1.0
    panx, pany = 0, 0
    show_checker = True
    show_axis = True
    running = True

    PAN_STEP = 20
    PAN_STEP_FAST = 60

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                fast = bool(pygame.key.get_mods() & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL | pygame.KMOD_ALT))
                step = PAN_STEP_FAST if fast else PAN_STEP

                if ev.key == pygame.K_ESCAPE:
                    running = False

                # navegación
                elif ev.key == pygame.K_PERIOD:   # next
                    j = bank.next_with_blob(idx)
                    if j is not None:
                        idx = j; panx = pany = 0
                elif ev.key == pygame.K_COMMA:    # prev
                    j = bank.prev_with_blob(idx)
                    if j is not None:
                        idx = j; panx = pany = 0
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

                # zoom
                elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    zoom = min(zoom * 1.25, 32.0)
                elif ev.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                    zoom = max(zoom / 1.25, 0.03125)
                elif ev.key in (pygame.K_0, pygame.K_KP0):
                    zoom = 1.0; panx = pany = 0

                # pan
                elif ev.key == pygame.K_LEFT:
                    panx -= step
                elif ev.key == pygame.K_RIGHT:
                    panx += step
                elif ev.key == pygame.K_UP:
                    pany -= step
                elif ev.key == pygame.K_DOWN:
                    pany += step

                # toggles
                elif ev.key == pygame.K_b:
                    show_checker = not show_checker
                elif ev.key == pygame.K_a:
                    show_axis = not show_axis
                elif ev.key == pygame.K_t:
                    bank.set_use_transparency(not bank.use_transparency)

                # cargar ACT runtime
                elif ev.key == pygame.K_g:
                    p = prompt("Ruta a .act (Enter para cancelar): ")
                    if p and os.path.exists(p):
                        pal_raw = load_act_palette(p)
                        if pal_raw:
                            bank.set_global_act(pal_raw)

                # invertir rampa ACT (rehonea)
                elif ev.key == pygame.K_v:
                    bank.set_act_reverse(not bank.act_reverse)

                # toggle donor alignment
                elif ev.key == pygame.K_u:
                    bank.use_donor_alignment = not bank.use_donor_alignment
                    bank._surf_cache.clear()

                # mover slot start
                elif ev.key == pygame.K_LEFTBRACKET:    # '['
                    delta = -8 if fast else -1
                    bank.set_act_slot_start(bank.act_slot_start + delta)
                elif ev.key == pygame.K_RIGHTBRACKET:   # ']'
                    delta = +8 if fast else +1
                    bank.set_act_slot_start(bank.act_slot_start + delta)

                # ajustar largo del slot ; / '
                elif ev.key == pygame.K_SEMICOLON:      # ';'
                    delta = -8 if fast else -1
                    new_len = max(1, bank.act_slot_len + delta)
                    bank.set_act_slot_start(bank.act_slot_start, new_len)
                elif ev.key == pygame.K_QUOTE:          # '\''
                    delta = +8 if fast else +1
                    new_len = max(1, bank.act_slot_len + delta)
                    bank.set_act_slot_start(bank.act_slot_start, new_len)

        # render
        screen.fill(BG_COLOR)
        if show_checker:
            draw_checker(screen, cell=16)

        surf, meta, warn = bank.surface_for_index(idx)

        # sprite
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

        # HUD modo/act/donor
        mode_txt = "ACT(forced 0..4999)" if bank.act_global else "AUTO"
        info_lines.append(
            "Mode=%s | TranspIdx=%d | Alpha=%s | DonorAlign=%s" %
            (mode_txt, bank.trans_index, "ON" if bank.use_transparency else "OFF",
             "ON" if bank.use_donor_alignment else "OFF")
        )
        if bank.act_global:
            info_lines.append("ACT slot=%d..%d  | reverse=%s" %
                              (bank.act_slot_start, bank.act_slot_start + bank.act_slot_len - 1,
                               "YES" if bank.act_reverse else "NO"))
        if warn:
            info_lines.append("WARN: %s" % warn)

        # paletas en vivo (DONOR y ACT horneada)
        top_y = 8
        draw_palette_grid(
            screen, GRID_X, top_y + 22,
            bank.donor_palette_flat if bank.donor_palette_flat else None,
            "DONOR (9000,0) %s" % ("OK" if bank.donor_palette_flat else "(sin donor)"),
            cell=GRID_CELL
        )
        draw_palette_grid(
            screen, GRID_X + (16*GRID_CELL) + 32, top_y + 22,
            (_flatten_palette_rgb(bank.act_global) if bank.act_global else None),
            "ACT (slotted)",
            cell=GRID_CELL
        )

        # info text
        ytxt = 8
        for line in info_lines:
            txt = font.render(line, True, FG_COLOR)
            screen.blit(txt, (GRID_X, ytxt))
            ytxt += 18

        # ayuda
        help_lines = [
            "[, / .] prev/next   [PgUp/PgDn] +/-10",
            "[+/−/0] zoom in/out/reset   [←/→/↑/↓] pan (Shift=rápido)",
            "[B] checker   [A] axis   [T] alpha on/off",
            "[G] cargar .ACT   [V] invert ACT ramp   [U] donor align on/off",
            "[ [ / ] ] mover slot start (Shift=±8)   [; / ' ] slot length (Shift=±8)",
            "Forzando ACT en grupos 0..4999; (9000,1) respeta su paleta embebida."
        ]
        base_help_y = WIN_H - 6 - 18*len(help_lines)
        for i, line in enumerate(help_lines):
            txt = font.render(line, True, (180, 180, 200))
            screen.blit(txt, (GRID_X, base_help_y + (i * 18)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0

if __name__ == "__main__":
    sys.exit(main())
