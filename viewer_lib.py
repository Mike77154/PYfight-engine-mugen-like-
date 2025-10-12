# -*- coding: utf-8 -*-
from __future__ import print_function
import os, struct, io
import pygame
from PIL import Image

# ============================================================================
#  Lector / helpers de paletas ACT (Photoshop / M.U.G.E.N)
# ============================================================================

def load_act_palette(path):
    """
    Lee .ACT (768 o 772 bytes) y devuelve lista de 256 tuplas (r,g,b).
    (RAW; las variantes slot/full se hornean dentro del banco)
    """
    if not os.path.exists(path):
        print("No existe .ACT:", path); return None
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 768:
        print("ACT demasiado corto:", len(data)); return None
    pal = []
    for i in range(256):
        base = i * 3
        if base + 2 < len(data):
            r, g, b = struct.unpack("BBB", data[base:base+3])
            pal.append((r, g, b))
        else:
            pal.append((0, 0, 0))
    return pal

def _flatten_palette_rgb(pal_rgb):
    """[(r,g,b), ...] -> flat [r,g,b,r,g,b,...] (768 bytes)"""
    flat = []
    for (r, g, b) in pal_rgb:
        flat.extend([int(r)&255, int(g)&255, int(b)&255])
    if len(flat) < 768:
        flat += [0] * (768 - len(flat))
    return flat[:768]

def _pil_to_surface(pil_im):
    """PIL.Image -> pygame.Surface RGBA sin tocar disco."""
    if pil_im.mode != "RGBA":
        pil_im = pil_im.convert("RGBA")
    raw = pil_im.tobytes("raw", "RGBA")
    w, h = pil_im.size
    return pygame.image.fromstring(raw, (w, h), "RGBA")

# ----------------- PCX helpers ------------------------------------------------
def _pcx_has_palette(raw_bytes):
    """PCX: último 769º byte debe ser 0x0C si hay paleta a 256 col."""
    if not raw_bytes or len(raw_bytes) < 769:
        return False
    marker = raw_bytes[-769]
    # Py3 ya entrega int; en Py2 sería 1-byte string
    try:
        return (marker if isinstance(marker, int) else ord(marker)) == 12  # 0x0C
    except Exception:
        return False

# ----------------- ACT normalización a SLOT ----------------------------------
def _is_black(rgb):
    return rgb == (0,0,0)

def _find_largest_color_block(pal):
    """
    Busca el bloque no-negro más largo.
    Devuelve (start, length). Si todo es negro, (0,0).
    """
    best_s, best_len = 0, 0
    s, n = None, 0
    for i, rgb in enumerate(pal):
        if not _is_black(rgb):
            if s is None:
                s, n = i, 1
            else:
                n += 1
        else:
            if s is not None and n > best_len:
                best_s, best_len = s, n
            s, n = None, 0
    if s is not None and n > best_len:
        best_s, best_len = s, n
    if best_len == 0:
        return 0, 0
    return best_s, best_len

def act_to_slot(pal_rgb, dest_start=16, keep_len=16, reverse_block=False):
    """
    Coloca el bloque de color más largo dentro del rango [dest_start .. dest_start+keep_len-1].
    reverse_block=True invierte el orden del bloque.
    """
    if not pal_rgb or len(pal_rgb) < 256:
        return pal_rgb
    src_s, src_len = _find_largest_color_block(pal_rgb)
    if src_len <= 0:
        return [(0,0,0)] * 256
    L = min(keep_len, src_len, 256)
    out = [(0,0,0)] * 256
    out[0] = (0,0,0)
    segment = pal_rgb[src_s:src_s+L]
    if reverse_block:
        segment = list(reversed(segment))
    dst_end = min(dest_start + L, 256)
    for i in range(dest_start, dst_end):
        out[i] = segment[i - dest_start]
    return out

# ----------------- Helpers de paleta/índices ---------------------------------
def _rgb_list_from_flat(flat):
    """flat(768) -> lista 256 de (r,g,b)"""
    if not flat or len(flat) < 768:
        return None
    out = []
    for i in range(256):
        out.append((int(flat[i*3+0]) & 255,
                    int(flat[i*3+1]) & 255,
                    int(flat[i*3+2]) & 255))
    return out

def _used_palette_indices(imP):
    """Índices realmente usados en la imagen indexada 'P'."""
    hist = imP.histogram()[:256]
    return [i for i, c in enumerate(hist) if c]

def _border_index_histogram(imP):
    """
    Histograma de índices en el borde (arriba/abajo/izq/der) de la imagen 'P'.
    Devuelve lista de 256 contadores.
    """
    if imP.mode != "P":
        imP = imP.convert("P")
    w, h = imP.size
    px = imP.load()
    hist = [0]*256
    # fila superior e inferior
    for x in range(w):
        hist[px[x,0]] += 1
        hist[px[x,h-1]] += 1
    # columnas laterales (evitar contar esquinas otra vez)
    for y in range(1, h-1):
        hist[px[0,y]] += 1
        hist[px[w-1,y]] += 1
    return hist

# === NUEVO: chroma hard por color clave (sin degradados) ======================
def _key_rgb_from_flat(flat_pal, trans_index):
    """Devuelve (r,g,b) del color en trans_index dentro de una paleta plana 768."""
    if not flat_pal or len(flat_pal) < 768:
        return None
    i = max(0, min(255, int(trans_index))) * 3
    return (int(flat_pal[i+0]) & 255, int(flat_pal[i+1]) & 255, int(flat_pal[i+2]) & 255)

def _apply_rgb_key_alpha(im_rgba, key_rgb, enable_alpha=True):
    """
    Toma una RGBA y pone alpha=0 SOLO en píxeles cuyo RGB == key_rgb.
    No hay degradados; binario puro.
    """
    if not enable_alpha or not key_rgb:
        return im_rgba
    if im_rgba.mode != "RGBA":
        im_rgba = im_rgba.convert("RGBA")
    px = bytearray(im_rgba.tobytes())  # RGBA consecutivo
    rK, gK, bK = key_rgb
    for i in range(0, len(px), 4):
        if px[i] == rK and px[i+1] == gK and px[i+2] == bK:
            px[i+3] = 0
        else:
            px[i+3] = 255
    w, h = im_rgba.size
    return Image.frombytes("RGBA", (w, h), bytes(px))

# ============================================================================
#  Banco de sprites SFF (viewer / parser)
# ============================================================================

class SFFSpriteBank(object):
    """
    Modos ACT:
      - act_mode="auto": embebida o ACT sloteada según reglas.
      - act_mode="slot": fuerza ACT sloteada (tipo KFM clásico).
      - act_mode="full": usa los 256 colores del ACT tal cual vienen (sin slot).
      - act_mode="act" : alias de "full" para compatibilidad con gestores externos.
    Transparencia:
      - Por índice. trans_index por defecto = 0.
      - auto_transparency=True: detecta el índice de transparencia por borde.
    """

    def __init__(self, sff):
        self.sff = sff
        self.n = len(sff.subfiles) if sff else 0

        # Memorias de paletas observadas
        self.group_last_palette = {}     # group -> flat(768)
        self.default_palette = None      # primera embebida válida vista

        # Cache
        self._surf_cache = {}
        self._remap_cache = {}

        # Rango de grupos a forzar ACT (gameplay)
        self.act_target_groups = (0, 4999)

        # ACT buffers y configuración
        self.act_mode = "full"   # en lugar de "auto"
        self.act_global_raw = None
        self.act_global = None           # sloteada
        self.act_full = None             # 256 colores crudos
        self.act_slot_start = 16
        self.act_slot_len = 16
        self.act_reverse = False         # invierte la rampa sloteada
        self.act_reverse_full = False    # invierte los 256 colores crudos

        # Donor (alineación opcional)
        self.donor_palette_flat = None
        self.use_donor_alignment = True
        self.donor_anchor_start  = 16
        self.donor_anchor_len    = 16

        # debug opcional
        self.debug_info = {}

        # ——— Parches “0 sagrado” (final override sin quitar nada) ———
        self.use_transparency   = True
        self.trans_index        = 0
        self.auto_transparency  = False
        self.auto_transp_threshold = 0.60 # umbral de borde para elegir índice

        # Paletas indexadas por clave exacta (group, image)
        self.palette_map = {}          # {(group, image): flat(768)}
        self.shared_palette_key = (1, 1)  # convención: paleta compartida en (1,1)

    # ---------------- Config público ----------------
    def set_use_transparency(self, v):
        self.use_transparency = bool(v)
        self._surf_cache.clear()

    def set_transparent_index(self, idx):
        self.trans_index = max(0, min(255, int(idx)))
        self._surf_cache.clear()

    def set_auto_transparency(self, v):
        self.auto_transparency = bool(v)
        self._surf_cache.clear()

    def set_auto_transparency_threshold(self, t):
        """Define el umbral (0..1) de borde para autodetectar índice transparente."""
        try:
            self.auto_transp_threshold = max(0.0, min(1.0, float(t)))
        except Exception:
            pass
        self._surf_cache.clear()

    def set_donor_palette_flat(self, flat):
        self.donor_palette_flat = flat
        self._surf_cache.clear()

    def set_act_target_groups(self, gmin, gmax):
        self.act_target_groups = (int(gmin), int(gmax))
        self._surf_cache.clear()

    def set_act_mode(self, mode):
        # Soporta 'act' como alias de 'full' para compatibilidad externa
        if mode == "act":
            mode = "full"
        if mode in ("auto","slot","full"):
            self.act_mode = mode
            self._surf_cache.clear()

    def _bake_act_variants(self):
        # SLOT
        self.act_global = act_to_slot(
            self.act_global_raw, self.act_slot_start, self.act_slot_len, self.act_reverse
        )
        # FULL
        full = self.act_global_raw[:]
        if self.act_reverse_full:
            full = list(reversed(full))
        self.act_full = full

    def set_global_act(self, pal):
        if pal and len(pal) >= 256:
            self.act_global_raw = pal[:]
            self._bake_act_variants()
            self._surf_cache.clear()
            self._remap_cache.clear()
            return True
        return False

    def set_act_slot_start(self, start, length=None):
        self.act_slot_start = max(0, min(255, int(start)))
        if length is not None:
            self.act_slot_len = max(1, min(256, int(length)))
        if self.act_global_raw:
            self._bake_act_variants()
        self._surf_cache.clear()

    def set_act_reverse(self, value):
        self.act_reverse = bool(value)
        if self.act_global_raw:
            self._bake_act_variants()
        self._surf_cache.clear()

    def set_act_reverse_full(self, value):
        self.act_reverse_full = bool(value)
        if self.act_global_raw:
            self._bake_act_variants()
        self._surf_cache.clear()

    def set_auto_donor_by_groupimage(self, g=9000, i=0):
        """
        Busca el primer subfile con (group,image)=(g,i) y si tiene paleta embebida
        la guarda como donor_palette_flat.
        """
        try:
            for idx, sf in enumerate(self.sff.subfiles):
                if sf.group == g and sf.image == i:
                    raw = self.sff._blob_cache.get(idx)
                    if not raw:
                        continue
                    im = Image.open(io.BytesIO(raw))
                    im.load()
                    if im.mode == "P":
                        pal = im.getpalette()
                        if pal and len(pal) >= 768:
                            self.donor_palette_flat = pal[:768]
                            self._surf_cache.clear()
                            return True
            return False
        except Exception:
            return False

    # ---------------- Navegación ----------------
    def has_blob(self, i):
        try:
            return self.sff._blob_cache.get(i) is not None
        except:
            return False

    def next_with_blob(self, i):
        for j in range(i+1, self.n):
            if self.has_blob(j): return j
        return None

    def prev_with_blob(self, i):
        for j in range(i-1, -1, -1):
            if self.has_blob(j): return j
        return None

    # ---------------- Paleta & alpha helpers ----------------
    def _auto_pick_transparent_index(self, imP):
        """
        Autodetecta índice transparente por borde: si algún índice ocupa >= umbral,
        lo adopta; si no, conserva self.trans_index.
        (Queda desactivado por defecto con auto_transparency=False)
        """
        try:
            if not self.auto_transparency:
                return self.trans_index
            hist = _border_index_histogram(imP)
            total = sum(hist)
            if total <= 0:
                return self.trans_index
            k = max(range(256), key=lambda i: hist[i])
            if hist[k] / float(total) >= float(self.auto_transp_threshold):
                return k
        except Exception:
            pass
        return self.trans_index

    def _build_index_mask(self, im_indexed, trans_idx=None):
        """Máscara por índice (auto si corresponde) desde imagen en 'P'."""
        if im_indexed.mode != "P":
            im_indexed = im_indexed.convert("P")
        t = self._auto_pick_transparent_index(im_indexed) if trans_idx is None else int(trans_idx)
        return im_indexed.point(lambda p: 0 if p == t else 255).convert("L")

    def _apply_palette_and_alpha(self, imP, flat_pal):
        """
        Aplica paleta plana a imagen 'P' y devuelve RGBA con alpha por índice.
        Respeta auto_transparency si está habilitado.
        + Luego aplica **chroma duro por RGB** del color en trans_index.
        """
        if imP.mode != "P":
            imP = imP.convert("P")
        if flat_pal:
            imP.putpalette(flat_pal)

        # Construir RGBA primero
        rgba = imP.convert("RGBA")

        if self.use_transparency:
            # 1) Chroma por índice (por si fuese necesario en algún flujo)
            #    (se mantiene para compatibilidad y por si el usuario activa auto)
            mask = self._build_index_mask(imP)  # usa auto o self.trans_index
            rgba.putalpha(mask)

            # 2) Chroma **duro** por color exacto del índice trans_index de ESTA paleta
            key_rgb = _key_rgb_from_flat(imP.getpalette(), self.trans_index)
            rgba = _apply_rgb_key_alpha(rgba, key_rgb, enable_alpha=True)
        else:
            rgba.putalpha(255)

        return rgba

    def _remember_embedded_palette(self, im, group, image, raw_bytes):
        """
        Memoriza paleta embebida válida solo si el PCX contiene paleta a 256.
        Indexa por (group,image) y además mantiene last-by-group y default.
        """
        try:
            if not _pcx_has_palette(raw_bytes):
                return None
            if im.mode != "P":
                return None
            pal = im.getpalette()
            if pal and len(pal) >= 768:
                flat = pal[:768]

                # índice exacto (group,image)
                self.palette_map[(int(group), int(image))] = flat

                # compat: memoria por grupo y default
                self.group_last_palette[group] = flat
                if self.default_palette is None:
                    self.default_palette = flat
                return flat
        except:
            pass
        return None

    # ---------------- Candado de LUT: índice 0 sagrado ------------------------
    def _sacredize_lut(self, lut):
        """
        Garantiza 0 sagrado:
          - lut[0] = 0 (o el índice self.trans_index si no es 0)
          - ningún otro índice mapea a ese índice transparente
        """
        t = self.trans_index
        if 0 <= t < 256:
            lut[t] = t
            for i in range(256):
                if i != t and lut[i] == t:
                    lut[i] = i
        return lut

    #-------------------------------------------------------------------------
    def set_shared_palette_key(self, g, i):
        """Define la clave (group,index) que se tratará como paleta compartida."""
        self.shared_palette_key = (int(g), int(i))
        self._surf_cache.clear()

    #-------------------------------------------------------------------------
    def index_all_palettes(self, max_scan=None):
        """
        Recorre subfiles y memoriza paletas embebidas (si PCX trae 256-col).
        max_scan: limita cantidad si te preocupa performance en chars gigantes.
        """
        count = 0
        for i, sf in enumerate(self.sff.subfiles):
            if max_scan and count >= max_scan:
                break
            raw = self.sff._blob_cache.get(i)
            if not raw:
                continue
            try:
                im = Image.open(io.BytesIO(raw)); im.load()
                self._remember_embedded_palette(im, sf.group, sf.image, raw)
                count += 1
            except Exception:
                pass
        return count

    #-------------------------------------------------------------------------
    def _resolve_sprite_palette_flat(self, group, image):
        # Orden de preferencia:
        #  1) Paleta exacta del sprite: (group,image)
        #  2) Paleta compartida (1,1)
        #  3) Última paleta observada del grupo
        #  4) Paleta default global (primera válida vista)
        # No incluye ACT aquí: ACT se aplica después según act_mode.

        # 1) exacta
        flat = self.palette_map.get((group, image))
        if flat:
            return flat

        # 2) compartida (1,1)
        flat = self.palette_map.get(self.shared_palette_key)
        if flat:
            return flat

        # 3) última por grupo
        flat = self.group_last_palette.get(group)
        if flat:
            return flat

        # 4) default global
        return self.default_palette

    # ---------------- Remapeos de índice -------------------------------------
    def _build_index_remap_to_donor(self, src_flat, donor_flat, used_idxs=None):
        """
        LUT índice→índice para llevar índices usados del sprite
        al orden de índices de la paleta donor (rango ancla).
        """
        if not src_flat or not donor_flat:
            return [i for i in range(256)]
        donor_rgb = _rgb_list_from_flat(donor_flat)
        src_rgb   = _rgb_list_from_flat(src_flat)
        if not donor_rgb or not src_rgb:
            return [i for i in range(256)]

        start = int(self.donor_anchor_start)
        end   = min(start + int(self.donor_anchor_len), 256)
        allowed = range(start, end)

        if not used_idxs:
            used_idxs = range(256)

        remap = [i for i in range(256)]
        for i in used_idxs:
            rs, gs, bs = src_rgb[i]
            best_k, best_d = start, 1 << 30
            for k in allowed:
                r, g, b = donor_rgb[k]
                dr, dg, db = rs - r, gs - g, bs - b
                d = dr*dr + dg*dg + db*db
                if d < best_d:
                    best_d, best_k = d, k
                    if d == 0: break
            remap[i] = best_k

        # preserva transparencia: trans_index -> trans_index
        try:
            remap[self.trans_index] = self.trans_index
        except:
            pass

        # seguridad extra: evita que otros índices terminen en trans_index
        for i in range(256):
            if i != self.trans_index and remap[i] == self.trans_index:
                remap[i] = i  # o allowed[0], según tu política

        remap = self._sacredize_lut(remap)
        return remap

    # ---------------- Aplicación final ACT ------------------------------------
    def _force_act_rgba(self, im, src_flat_or_none):
        """
        Aplica ACT según self.act_mode:
          - "slot": usa self.act_global (sloteada).
          - "full"/"act": usa self.act_full (256 tal cual).
          - "auto": comportamiento previo (sloteada) con donor-align opcional.
        """
        if not (self.act_global or self.act_full):
            return im.convert("RGBA")

        # Si ya es RGBA (p.ej. PNG truecolor), no tiene sentido paletizar
        if im.mode == "RGBA":
            return im

        imP = im if im.mode == "P" else im.convert("P")

        mode = self.act_mode
        if mode == "full":
            # Respeta ACT cruda (no tiene sentido donor-align por rangos)
            pal_flat = _flatten_palette_rgb(self.act_full if self.act_full else self.act_global)
            imP.putpalette(pal_flat)
        else:
            # "slot" o "auto": opción de alinear a donor en el rango ancla
            if self.use_donor_alignment and self.donor_palette_flat and src_flat_or_none:
                used = _used_palette_indices(imP)
                lut  = self._build_index_remap_to_donor(src_flat_or_none, self.donor_palette_flat, used_idxs=used)
                lut  = self._sacredize_lut(lut)  # doble candado por si acaso
                imP  = imP.point(lambda p: lut[p])

            pal_flat = _flatten_palette_rgb(self.act_global if self.act_global else self.act_full)
            # (Opcional estético) asegurar que el RGB del índice 0 sea negro:
            pal_flat[0:3] = [0,0,0]
            imP.putpalette(pal_flat)

        # ------ NUEVO: alpha SOLO por el color RGB del trans_index ----------
        rgba = imP.convert("RGBA")
        if self.use_transparency:
            # color clave a partir de la paleta actualmente aplicada a imP
            key_rgb = _key_rgb_from_flat(imP.getpalette(), self.trans_index)
            rgba = _apply_rgb_key_alpha(rgba, key_rgb, enable_alpha=True)
        else:
            rgba.putalpha(255)
        return rgba

    # ---------------- Paletas “visibles” para HUD -----------------------------
    def current_palettes_for_index(self, i):
        """
        Devuelve dict con paletas planas para dibujar en HUD:
          {
            "sprite_flat": flat embebida si hay (sólo si PCX trae paleta),
            "donor_flat" : donor plana o None,
            "act_flat"   : la paleta ACT que se está usando (full o slot según act_mode)
          }
        """
        out = {"sprite_flat": None, "donor_flat": self.donor_palette_flat, "act_flat": None}
        if i < 0 or i >= self.n: return out
        sf = self.sff.subfiles[i]
        raw = self.sff._blob_cache.get(i)
        if not raw: return out
        try:
            im = Image.open(io.BytesIO(raw)); im.load()
            flat_emb = self._remember_embedded_palette(im, sf.group, sf.image, raw)
            out["sprite_flat"] = flat_emb
        except Exception:
            pass

        # ACT visible según modo
        if self.act_mode == "full" and self.act_full:
            out["act_flat"] = _flatten_palette_rgb(self.act_full)
        elif self.act_global:
            out["act_flat"] = _flatten_palette_rgb(self.act_global)
        return out

    # ---------------- Render principal ----------------------------------------
    def surface_for_index(self, i):
        if i in self._surf_cache:
            return self._surf_cache[i]
        if i < 0 or i >= self.n:
            return None, None, "Fuera de rango"

        sf = self.sff.subfiles[i]
        raw = self.sff._blob_cache.get(i)
        if not raw:
            return None, None, "Sin datos"

        warn = None
        try:
            im = Image.open(io.BytesIO(raw)); im.load()
            group, image = sf.group, sf.image

            # Si ya es RGBA (ej. sprites PNG truecolor en SFFv2), no aplicar paletas/ACT
            if im.mode == "RGBA":
                rgba = im
            else:
                # Memoriza paleta embebida solo si el PCX la trae (indexa por (g,i))
                flat_emb = self._remember_embedded_palette(im, group, image, raw)

                # Paleta origen informativa / donor fallback
                # primero resolvemos la que le toca al sprite por (g,i) / (1,1) / group / default
                sprite_flat = self._resolve_sprite_palette_flat(group, image)

                # Donor sigue teniendo prioridad si lo definiste (para realineación de índices)
                src_flat = self.donor_palette_flat or sprite_flat

                gmin, gmax = self.act_target_groups
                force_act_here = ((self.act_mode in ("slot","full")) or (self.act_global is not None)) and (gmin <= group <= gmax)

                if force_act_here:
                    # Retrato grande (9000,1) respeta embebida si la trae (excepto en mode "full")
                    if (group == 9000 and image == 1) and flat_emb and self.act_mode != "full":
                        rgba = self._apply_palette_and_alpha(im, flat_emb)
                    else:
                        rgba = self._force_act_rgba(im, src_flat)
                else:
                    # AUTO sin ACT
                    if flat_emb:
                        rgba = self._apply_palette_and_alpha(im, flat_emb)
                    elif src_flat:
                        rgba = self._apply_palette_and_alpha(im.convert("P"), src_flat)
                    else:
                        rgba = im.convert("RGBA")

            surf = _pil_to_surface(rgba)
            meta = dict(group=sf.group, image=sf.image,
                        width=surf.get_width(), height=surf.get_height(),
                        axis_x=sf.axis_x, axis_y=sf.axis_y)
            self._surf_cache[i] = (surf, meta, warn)
            return self._surf_cache[i]

        except Exception as e:
            warn = "Error al decodificar: %s" % e
            surf = pygame.Surface((64,64), pygame.SRCALPHA, 32)
            surf.fill((255,0,255,255))
            meta = dict(group=sf.group, image=sf.image,
                        width=surf.get_width(), height=surf.get_height(),
                        axis_x=sf.axis_x, axis_y=sf.axis_y)
            self._surf_cache[i] = (surf, meta, warn)
            return self._surf_cache[i]
