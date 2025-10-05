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
    (Se entrega RAW; la inversión/slotting se hace dentro del banco vía act_to_slot)
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
        flat.extend([int(r) & 255, int(g) & 255, int(b) & 255])
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
    return ord(raw_bytes[-769]) == 12  # 0x0C


# ----------------- ACT normalización a SLOT ----------------------------------
def _is_black(rgb):
    return rgb == (0, 0, 0)


def _find_largest_color_block(pal):
    """
    Busca el bloque no-negro más largo en la paleta ACT.
    Devuelve (start, length). Si todo es negro, (0, 0).
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
    Toma la ACT cruda (lista de 256 (r,g,b)), detecta el bloque no-negro más largo
    y lo coloca en el rango [dest_start .. dest_start+keep_len-1].
    reverse_block=True invierte el orden (útil cuando la rampa viene “al revés”).
    """
    if not pal_rgb or len(pal_rgb) < 256:
        return pal_rgb

    src_s, src_len = _find_largest_color_block(pal_rgb)
    if src_len <= 0:
        return [(0, 0, 0)] * 256

    L = min(keep_len, src_len, 256)
    out = [(0, 0, 0)] * 256
    out[0] = (0, 0, 0)

    segment = pal_rgb[src_s:src_s + L]
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
        out.append((int(flat[i * 3 + 0]) & 255,
                    int(flat[i * 3 + 1]) & 255,
                    int(flat[i * 3 + 2]) & 255))
    return out


def _used_palette_indices(imP):
    """Índices realmente usados en la imagen indexada 'P'."""
    hist = imP.histogram()[:256]
    return [i for i, c in enumerate(hist) if c]


# ============================================================================
#  Banco de sprites SFF (viewer / parser)
# ============================================================================
class SFFSpriteBank(object):
    """
    Política:
      - Si hay ACT: aplicar ACT a todos los grupos gameplay (0..4999) salvo (9000,1),
        que usa su paleta embebida si la trae.
      - Sin ACT: AUTO (paleta embebida -> última del grupo -> default).
    Transparencia SIEMPRE por índice (self.trans_index). Índice 0 por defecto.
    """

    def __init__(self, sff):
        self.sff = sff
        self.n = len(sff.subfiles) if sff else 0

        # Memorias de paletas observadas
        self.group_last_palette = {}     # group -> flat(768)
        self.default_palette = None      # primera embebida válida vista

        # Config transparencia
        self.use_transparency = True
        self.trans_index = 0

        # Cache de superficies y remaps
        self._surf_cache = {}
        self._remap_cache = {}

        # Rango de grupos a forzar ACT (gameplay)
        self.act_target_groups = (0, 4999)

        # ACT global (raw y “horneada” al slot)
        self.act_global_raw = None
        self.act_global = None
        self.act_slot_start = 16
        self.act_slot_len = 16
        self.act_reverse = False          # invierte la rampa si ACT vino “al revés”

        # Remapeo directo src->ACT (normalmente OFF para KFM clásico)
        self.use_index_remap_when_forcing_act = False

        # Donor (maestra) y alineación
        self.donor_palette_flat = None    # flat(768) de (9000,0) u otra
        self.use_donor_alignment = True   # ON: remapear índices al orden del donor
        self.donor_anchor_start  = 16     # rango ancla de colores “reales”
        self.donor_anchor_len    = 16     # típicamente 16..31 en chars clásicos

        # debug opcional
        self.debug_info = {}

    # ---------------- Config público ----------------
    def set_use_transparency(self, v):
        self.use_transparency = bool(v)
        self._surf_cache.clear()

    def set_transparent_index(self, idx):
        self.trans_index = max(0, min(255, int(idx)))
        self._surf_cache.clear()

    def set_donor_palette_flat(self, flat):
        self.donor_palette_flat = flat
        self._surf_cache.clear()

    def set_act_target_groups(self, gmin, gmax):
        self.act_target_groups = (int(gmin), int(gmax))
        self._surf_cache.clear()

    def set_global_act(self, pal):
        """
        Establece ACT cruda; la hornea a slot con inversión opcional.
        """
        if pal and len(pal) >= 256:
            self.act_global_raw = pal[:]
            self.act_global = act_to_slot(
                pal, self.act_slot_start, self.act_slot_len, self.act_reverse
            )
            self._surf_cache.clear()
            self._remap_cache.clear()
            return True
        return False

    def set_act_slot_start(self, start, length=None):
        self.act_slot_start = max(0, min(255, int(start)))
        if length is not None:
            self.act_slot_len = max(1, min(256, int(length)))
        if self.act_global_raw:
            self.act_global = act_to_slot(
                self.act_global_raw, self.act_slot_start, self.act_slot_len, self.act_reverse
            )
        self._surf_cache.clear()

    def set_act_reverse(self, value):
        self.act_reverse = bool(value)
        if self.act_global_raw:
            self.act_global = act_to_slot(
                self.act_global_raw, self.act_slot_start, self.act_slot_len, self.act_reverse
            )
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
        for j in range(i + 1, self.n):
            if self.has_blob(j):
                return j
        return None

    def prev_with_blob(self, i):
        for j in range(i - 1, -1, -1):
            if self.has_blob(j):
                return j
        return None

    # ---------------- Paleta & alpha helpers ----------------
    def _build_index_mask(self, im_indexed):
        """Máscara por índice (self.trans_index) desde imagen en 'P'."""
        if im_indexed.mode != "P":
            im_indexed = im_indexed.convert("P")
        t = self.trans_index
        return im_indexed.point(lambda p: 0 if p == t else 255).convert("L")

    def _apply_palette_and_alpha(self, imP, flat_pal):
        """
        Aplica paleta plana a imagen 'P' y devuelve RGBA con alpha por índice.
        """
        if imP.mode != "P":
            imP = imP.convert("P")
        mask = self._build_index_mask(imP)
        if flat_pal:
            imP.putpalette(flat_pal)
        rgba = imP.convert("RGBA")
        if self.use_transparency:
            rgba.putalpha(mask)
        else:
            rgba.putalpha(255)
        return rgba

    def _remember_embedded_palette(self, im, group, raw_bytes):
        """
        Memoriza paleta embebida válida solo si el PCX contiene paleta al final.
        Esto evita que PNG/BMP convertidos “ensucien” la memoria de paletas.
        """
        try:
            if not _pcx_has_palette(raw_bytes):
                return None
            if im.mode != "P":
                return None
            pal = im.getpalette()
            if pal and len(pal) >= 768:
                flat = pal[:768]
                self.group_last_palette[group] = flat
                if self.default_palette is None:
                    self.default_palette = flat
                return flat
        except:
            pass
        return None

    # ---------------- Remapeos de índice -------------------------------------
    def _build_index_remap_to_donor(self, src_flat, donor_flat, used_idxs=None):
        """
        Genera LUT índice→índice para llevar los índices usados del sprite
        al orden de índices de la paleta donor (dentro del rango ancla [start..end)),
        por color más cercano. Preserva el índice de transparencia.
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
            if i == self.trans_index:
                remap[i] = self.trans_index
                continue
            rs, gs, bs = src_rgb[i]
            best_k, best_d = start, 1 << 30
            for k in allowed:
                r, g, b = donor_rgb[k]
                dr, dg, db = rs - r, gs - g, bs - b
                d = dr * dr + dg * dg + db * db
                if d < best_d:
                    best_d, best_k = d, k
                    if d == 0:
                        break
            remap[i] = best_k

        # preserva transparencia
        try:
            remap[self.trans_index] = self.trans_index
        except:
            pass

        return remap

    # ---------------- Aplicación final ACT (con donor opcional) ---------------
    def _force_act_rgba(self, im, src_flat_or_none):
        """
        Flujo final:
          1) Máscara por índice (solo trans_index es transparente).
          2) Si hay donor y está activo use_donor_alignment:
               remap src índices → índices donor (en el rango ancla).
          3) Aplica paleta ACT ya colocada en el slot y convierte a RGBA.
        """
        if not self.act_global:
            return im.convert("RGBA")

        imP = im if im.mode == "P" else im.convert("P")
        mask = self._build_index_mask(imP)

        if self.use_donor_alignment and self.donor_palette_flat and src_flat_or_none:
            used = _used_palette_indices(imP)
            lut  = self._build_index_remap_to_donor(src_flat_or_none, self.donor_palette_flat, used_idxs=used)
            imP  = imP.point(lambda p: lut[p])

        # coloreamos con ACT “horneada” en el slot (e invertida si correspondía)
        imP.putpalette(_flatten_palette_rgb(self.act_global))

        rgba = imP.convert("RGBA")
        if self.use_transparency:
            rgba.putalpha(mask)
        else:
            rgba.putalpha(255)
        return rgba

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

            # Memoriza paleta embebida solo si el PCX la trae
            flat_emb = self._remember_embedded_palette(im, group, raw)

            # Paleta origen informativa / donor fallback
            src_flat = (self.donor_palette_flat or flat_emb or
                        self.group_last_palette.get(group) or self.default_palette)

            gmin, gmax = self.act_target_groups
            force_act_here = (self.act_global is not None) and (gmin <= group <= gmax)

            if force_act_here:
                # Retrato grande (9000,1) respeta embebida si la trae
                if (group == 9000 and image == 1) and flat_emb:
                    rgba = self._apply_palette_and_alpha(im, flat_emb)
                else:
                    rgba = self._force_act_rgba(im, src_flat)
            else:
                # AUTO sin ACT
                if flat_emb:
                    mask = self._build_index_mask(im)
                    rgba = im.convert("RGBA")
                    if self.use_transparency:
                        rgba.putalpha(mask)
                    else:
                        rgba.putalpha(255)
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
            surf = pygame.Surface((64, 64), pygame.SRCALPHA, 32)
            surf.fill((255, 0, 255, 255))
            meta = dict(group=sf.group, image=sf.image,
                        width=surf.get_width(), height=surf.get_height(),
                        axis_x=sf.axis_x, axis_y=sf.axis_y)
            self._surf_cache[i] = (surf, meta, warn)
            return self._surf_cache[i]
