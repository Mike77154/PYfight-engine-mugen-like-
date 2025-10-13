# -*- coding: utf-8 -*-
from __future__ import print_function

import pygame

try:
    # Estructuras del parser
    from air_parser import CollisionSet
except Exception:
    # Fallback mínimo si no se importó (para evitar crash al leer este módulo solo)
    class CollisionSet(object):
        __slots__ = ('clsn1','clsn2')
        def __init__(self, clsn1=None, clsn2=None):
            self.clsn1 = clsn1 or []
            self.clsn2 = clsn2 or []

"""
air_draw_anim.py
Animator + Drawer + Router multi-backend para animaciones AIR (Python 2.7).

Requiere:
- pygame (1.9.x)
- air_parser.py en el PYTHONPATH (para usar Animation/AnimFrame/CollisionSet)

Provee:
- SpriteSource abstracto + implementaciones:
  SFFSource, SpriteSheetSource, StripSource, TilemapSource, ListSource, FileSource
- SpriteRouter: remapeo por (group,image) a distintas fuentes backend
- Animator: reproducción a 60 ticks/s (o por conversión desde ms)
- Dibujo con blit, flip, trans (A=add, S=sub, ASxxDyy/A1 ~ alpha), overlay de boxes:
  Clsn1 en ROJO translúcido, Clsn2 en AZUL translúcido.
"""

# --------------------------- Sprite Sources ----------------------------------

class SpriteSource(object):
    def get_surface(self, key):
        raise NotImplementedError

class SFFSource(SpriteSource):
    """
    sff_index: dict {(group,image): Surface}
    """
    def __init__(self, sff_index):
        self.idx = sff_index
    def get_surface(self, key):
        return self.idx.get((int(key[0]), int(key[1])))

class SpriteSheetSource(SpriteSource):
    """
    sheet_surface: atlas (Surface)
    rect_index:    dict {(group,image): Rect}
    extractor:     fn(sheet, Rect) -> Surface
    """
    def __init__(self, sheet_surface, rect_index, extractor):
        self.sheet = sheet_surface
        self.rects = rect_index
        self.extractor = extractor
    def get_surface(self, key):
        r = self.rects.get((int(key[0]), int(key[1])))
        return self.extractor(self.sheet, r) if r else None

class StripSource(SpriteSource):
    """
    Tira equiespaciada horizontal (por simplicidad).
    """
    def __init__(self, surface, fw, fh, origin_x=0, origin_y=0, stride=None):
        self.img = surface
        self.fw  = int(fw); self.fh = int(fh)
        self.ox  = int(origin_x); self.oy = int(origin_y)
        self.stride = int(stride) if stride else self.fw
    def get_surface(self, key):
        g,i = int(key[0]), int(key[1])  # g ignorado
        x = self.ox + i * self.stride
        return self.img.subsurface((x, self.oy, self.fw, self.fh))

class TilemapSource(SpriteSource):
    """
    Grid/tilemap; index lineal = group*cols + image.
    """
    def __init__(self, surface, tile_w, tile_h, cols):
        self.sheet = surface
        self.tw = int(tile_w); self.th = int(tile_h)
        self.cols = int(cols)
    def get_surface(self, key):
        g,i = int(key[0]), int(key[1])
        idx = g * self.cols + i
        cx = (idx % self.cols) * self.tw
        cy = (idx // self.cols) * self.th
        return self.sheet.subsurface((cx, cy, self.tw, self.th))

class ListSource(SpriteSource):
    """
    Lista de Surfaces; usa 'image' como índice.
    """
    def __init__(self, surfaces_list):
        self.lst = list(surfaces_list)
    def get_surface(self, key):
        i = int(key[1])
        return self.lst[i] if 0 <= i < len(self.lst) else None

class FileSource(SpriteSource):
    """
    Carga por ruta: key = ('file', 'path/to.png')
    loader_fn(path) -> Surface
    """
    def __init__(self, loader_fn):
        self.loader = loader_fn
        self.cache = {}
    def get_surface(self, key):
        if not key or len(key) < 2 or key[0] != 'file':
            return None
        path = key[1]
        if path in self.cache:
            return self.cache[path]
        surf = self.loader(path)
        self.cache[path] = surf
        return surf

# ------------------------------ Router ---------------------------------------

class SpriteRouter(object):
    """
    Remapea (group,image) -> (source_name, backend_key) para elegir backend.
    Si no hay remap, usa default_source (típicamente SFF).
    """
    def __init__(self, default_source):
        self.default = default_source
        self.sources = {}
        self.remap_table = {}  # (g,i) -> (src_name, backend_key)
    def register(self, name, source):
        self.sources[name] = source
    def set_remap(self, group, image, source_name, backend_key):
        self.remap_table[(int(group), int(image))] = (source_name, backend_key)
    def get_surface(self, group, image):
        key = (int(group), int(image))
        if key in self.remap_table:
            src_name, bkey = self.remap_table[key]
            src = self.sources.get(src_name)
            return src.get_surface(bkey) if src else None
        return self.default.get_surface(key) if self.default else None

# ------------------------------ Animator -------------------------------------

class Animator(object):
    TICKS_PER_SEC = 60
    def __init__(self, animation):
        self.anim = animation
        self.frame_idx = 0
        self.tick_in_frame = 0
    def reset(self, i=0):
        self.frame_idx = int(i)
        self.tick_in_frame = 0
    def update_ticks(self, ticks):
        while ticks > 0 and self.anim.frame_count() > 0:
            cur = self.anim.frames[self.frame_idx]
            if cur.time == -1:
                break
            remain = cur.time - self.tick_in_frame
            step = remain if remain <= ticks else ticks
            self.tick_in_frame += step
            ticks -= step
            if self.tick_in_frame >= cur.time:
                # next
                self.tick_in_frame = 0
                nidx = self.anim.frame_idx_next(self.frame_idx) if hasattr(self.anim, 'frame_idx_next') else None
                if nidx is None:
                    # compat con air_parser.Animation.next_index(...)
                    self.frame_idx = self._next_index_compat(self.frame_idx)
                else:
                    self.frame_idx = nidx
    def _next_index_compat(self, idx):
        if idx < 0 or idx >= self.anim.frame_count():
            return 0
        cur = self.anim.frames[idx]
        if cur.time == -1:
            return idx
        nidx = idx + 1
        if nidx < self.anim.frame_count():
            return nidx
        if self.anim.loopstart_idx is not None and self.anim.loopstart_idx < self.anim.frame_count():
            return self.anim.loopstart_idx
        return idx

# ------------------------------ Drawer ---------------------------------------

# Colores RGBA debug
DBG_RED_FILL  = (255,  40,  40, 110)  # Clsn1: rojo translúcido
DBG_BLUE_FILL = ( 40, 120, 255, 110)  # Clsn2: azul translúcido
DBG_RED_LINE  = (255,  60,  60)
DBG_BLUE_LINE = ( 60, 140, 255)

def _apply_flip_to_box(x1, y1, x2, y2, flip):
    if flip and 'H' in flip:
        x1, x2 = -x2, -x1
    if flip and 'V' in flip:
        y1, y2 = -y2, -y1
    return x1, y1, x2, y2

def _rect_from_box(px, py, x1, y1, x2, y2, xoff, yoff, scale):
    # sumar offsets (coords MUGEN)
    x1 += xoff; x2 += xoff
    y1 += yoff; y2 += yoff
    # ordenar
    left   = min(x1, x2) * scale
    right  = max(x1, x2) * scale
    topY   = max(y1, y2) * scale
    botY   = min(y1, y2) * scale
    # convertir a coords pantalla (y hacia abajo)
    scr_left = int(px + left)
    scr_top  = int(py - topY)
    width    = int(right - left)
    height   = int(topY - botY)
    return pygame.Rect(scr_left, scr_top, width, height)

def draw_collision_boxes(screen, px, py, boxes, xoff=0, yoff=0, flip='', scale=1.0, line_thickness=2):
    if boxes is None:
        return
    w, h = screen.get_size()
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)

    def _paint(lst, fill_rgba, line_rgb):
        for b in lst:
            x1,y1,x2,y2 = b.x1,b.y1,b.x2,b.y2
            x1,y1,x2,y2 = _apply_flip_to_box(x1,y1,x2,y2, flip)
            rect = _rect_from_box(px,py, x1,y1,x2,y2, xoff,yoff, scale)
            pygame.draw.rect(overlay, fill_rgba, rect, 0)
            pygame.draw.rect(overlay, line_rgb, rect, line_thickness)

    _paint(getattr(boxes,'clsn1',[]), DBG_RED_FILL,  DBG_RED_LINE)
    _paint(getattr(boxes,'clsn2',[]), DBG_BLUE_FILL, DBG_BLUE_LINE)
    screen.blit(overlay, (0,0))

# ----------------------------- Trans/Flip/Blit -------------------------------

def _parse_trans_alpha(trans_str):
    """
    Devuelve (mode, alpha_src, alpha_dst)
    mode: 'A'(add) | 'S'(sub) | ''
    alpha_src/dst: 0..255 o None
    A1 => ('A', 255, 128)
    AS64D192 => ('A', 64, 192)
    """
    if not trans_str:
        return '', None, None
    t = trans_str.upper().strip()
    if t == 'A':
        return 'A', None, None
    if t == 'S':
        return 'S', None, None
    if t == 'A1':
        return 'A', 255, 128
    if t.startswith('AS') and 'D' in t:
        try:
            body = t[2:]
            a_s, a_d = body.split('D', 1)
            asrc = int(a_s)
            adst = int(a_d)
            asrc = max(0, min(asrc, 255))
            adst = max(0, min(adst, 255))
            return 'A', asrc, adst
        except:
            return 'A', None, None
    return '', None, None

def _blit_with_trans(dst, surf, pos, trans):
    """
    Aplica trans: 'A' -> add, 'S' -> sub. Si trae alpha, ajusta set_alpha.
    """
    mode, a_src, a_dst = _parse_trans_alpha(trans)
    if mode == 'A':
        if a_src is not None:
            try:
                old_alpha = surf.get_alpha()
                surf.set_alpha(a_src)
                dst.blit(surf, pos, special_flags=pygame.BLEND_ADD)
                surf.set_alpha(old_alpha)
                return
            except:
                pass
        dst.blit(surf, pos, special_flags=pygame.BLEND_ADD)
        return
    if mode == 'S':
        dst.blit(surf, pos, special_flags=pygame.BLEND_SUB)
        return
    dst.blit(surf, pos)

def draw_anim_frame(screen, x, y, animation, router, frame_idx, scale=1.0, draw_boxes=True):
    """
    Dibuja un frame de 'animation' en (x,y) usando 'router'.
    - Respeta flip/trans/xoff/yoff.
    - scale: escala sprite y cajas
    - draw_boxes: True para overlay de colisiones
    """
    if animation.frame_count() == 0:
        return
    f = animation.frames[frame_idx]
    surf = router.get_surface(f.group, f.image)
    if not surf:
        return

    spr = surf
    if f.flip:
        h = ('H' in f.flip)
        v = ('V' in f.flip)
        spr = pygame.transform.flip(spr, h, v)

    pos = (x + int(f.xoff * scale), y + int(f.yoff * scale))
    if scale and scale != 1.0:
        w,h = spr.get_width(), spr.get_height()
        spr = pygame.transform.smoothscale(spr, (int(w*scale), int(h*scale)))

    _blit_with_trans(screen, spr, pos, f.trans)

    if draw_boxes:
        boxes = animation.resolve_boxes_for(frame_idx)
        draw_collision_boxes(screen, x, y, boxes,
                             xoff=int(f.xoff*scale), yoff=int(f.yoff*scale),
                             flip=f.flip, scale=scale)

# --------------------------- Demo opcional CLI --------------------------------

def _dummy_loader(path):
    return pygame.image.load(path).convert_alpha()

if __name__ == '__main__':
    # Demo super simple: muestra un surface y algunas cajas de ejemplo.
    pygame.init()
    screen = pygame.display.set_mode((640, 360))
    clock = pygame.time.Clock()

    # Surface de prueba (si no tienes PNGs a mano)
    test = pygame.Surface((64,64), pygame.SRCALPHA)
    test.fill((255,255,255,255))
    pygame.draw.circle(test, (200,60,60,255), (32,32), 20)

    # Router mínimo con ListSource
    lst = ListSource([test]*8)
    router = SpriteRouter(default_source=None)
    router.register('list', lst)
    for gi in range(8):
        router.set_remap(0, gi, 'list', (0, gi))

    # Animación fake (sin .air) para probar dibujo
    from air_parser import Animation, AnimFrame, CollisionSet
    a = Animation(0)
    a.defaults = CollisionSet()
    for i in range(8):
        a.frames.append(AnimFrame(0, i, 0, 0, 6,
                                  flip='' if i%2==0 else 'H',
                                  trans='A' if i%3==0 else ''))
    a.loopstart_idx = 0

    anim = Animator(a)

    running = True
    while running:
        dt = clock.tick(60)  # ms
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

        ticks = int(dt * 60 / 1000.0)
        anim.update_ticks(ticks)

        screen.fill((18,18,22))
        draw_anim_frame(screen, 320-32, 180-32, a, router, anim.frame_idx,
                        scale=1.0, draw_boxes=True)

        pygame.display.flip()

    pygame.quit()
