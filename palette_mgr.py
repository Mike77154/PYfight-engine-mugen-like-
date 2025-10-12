# -*- coding: utf-8 -*-
from __future__ import print_function
import io

try:
    from PIL import Image
except Exception as e:
    raise SystemExit("Necesitas Pillow: %s" % e)

# ---------- Utilidades ----------

def _bytes_to_list_0_255(b):
    # Py2/3: convierte bytes/str -> lista de ints
    if isinstance(b, str):
        return [ord(c) for c in b]
    return list(b)

def _flatten_palette_rgb(pal_rgb):
    """[(r,g,b), ...] -> flat [r,g,b,...] (768)"""
    flat = []
    for (r,g,b) in pal_rgb:
        flat.extend([int(r)&255, int(g)&255, int(b)&255])
    if len(flat) < 768:
        flat += [0]*(768-len(flat))
    return flat[:768]

def _rgb_list_from_flat(flat):
    """flat(768) -> lista 256 de (r,g,b)"""
    if not flat or len(flat) < 768: return None
    out=[]
    for i in range(256):
        out.append((int(flat[i*3+0])&255,
                    int(flat[i*3+1])&255,
                    int(flat[i*3+2])&255))
    return out

def _border_index_histogram(imP):
    """Histograma de índices en el borde de una imagen 'P'."""
    if imP.mode != "P":
        imP = imP.convert("P")
    w,h = imP.size
    px  = imP.load()
    hist = [0]*256
    for x in range(w):
        hist[px[x,0]] += 1
        hist[px[x,h-1]] += 1
    for y in range(1,h-1):
        hist[px[0,y]] += 1
        hist[px[w-1,y]] += 1
    return hist

# ---------- Modelo de paleta ----------

class Palette(object):
    """
    Paleta de 256 colores (ACT/embebida). Guarda:
    - pal: lista de 768 ints (R,G,B,...)
    - trans_index: índice que se considera transparente (por defecto 0)
    """
    __slots__ = ("pal", "trans_index")

    def __init__(self, pal_768_list, trans_index=0):
        if not pal_768_list or len(pal_768_list) < 768:
            raise ValueError("Paleta inválida: se esperan 768 enteros")
        self.pal = pal_768_list[:768]
        self.trans_index = int(trans_index) if 0 <= int(trans_index) <= 255 else 0

    @staticmethod
    def from_act_file(path, trans_index=0):
        """
        Carga .ACT (768 o 772 bytes; si 772, ignora 4 finales).
        Por convención M.U.G.E.N: el índice 0 suele ser transparente.
        """
        with open(path, "rb") as f:
            data = f.read()
        if len(data) < 768:
            raise ValueError("ACT muy corto: %d bytes" % len(data))
        pal = _bytes_to_list_0_255(data[:768])
        return Palette(pal, trans_index=trans_index)

    @staticmethod
    def from_embedded_PIL_palette(pil_image, trans_index=0):
        """
        Toma la paleta embebida de una imagen 'P' (si existe) y construye Palette.
        """
        if pil_image.mode != "P":
            return None
        pal = pil_image.getpalette()
        if not pal or len(pal) < 768:
            return None
        return Palette(pal[:768], trans_index=trans_index)

    def apply_to_indexed_P(self, imP, use_alpha=True):
        """
        Aplica esta paleta a una imagen en modo 'P' y retorna un RGBA.
        - use_alpha=True: índice trans_index será alpha=0; el resto alpha=255.
        """
        if imP.mode != "P":
            imP = imP.convert("P")
        imP.putpalette(self.pal)

        if not use_alpha:
            return imP.convert("RGBA")

        # Máscara: 0 si píxel == trans_index, 255 en otro caso.
        idx_img = imP.copy()                 # copia indexada para 'point'
        mask = idx_img.point(lambda p: 0 if p == self.trans_index else 255).convert("L")
        rgba = imP.convert("RGBA")
        rgba.putalpha(mask)
        return rgba

# ---------- Gestor de paletas para visor/juego ----------

class PaletteManager(object):
    """
    Decide qué paleta usar:
    - Modo 'auto': usa embebida → exacta(g,i) → compartida → última por grupo → default.
    - Modo 'act' : fuerza la ACT global (tal cual).
    - Modo 'slot': fuerza ACT sloteada (rango ancla).
    - Modo 'full': usa ACT completa (256 cruda, sin slot).
    Transparencia: índice configurable (por defecto 0).
    Donor alignment (opcional): remapea índices usados a un rango ancla de una paleta donante.
    """
    def __init__(self, default_trans_index=0):
        # modos: 'auto' | 'act' | 'slot' | 'full'
        self.mode = "auto"
        self.use_alpha = True
        self.trans_index = int(default_trans_index)

        # Paletas
        self.global_act = None          # Palette (ACT original)
        self.global_act_slot = None     # Palette sloteada (derivada)
        self.global_act_full = None     # Palette 256 cruda (derivada)

        # Memorias
        self.group_last = {}            # group -> Palette
        self.default_palette = None     # Palette
        self.exact_map = {}             # (group,image) -> Palette
        self.shared_palette_key = (1,1) # clave de paleta compartida

        # Donor alignment
        self.donor_palette = None       # Palette (flat 768)
        self.use_donor_alignment = True
        self.donor_anchor_start = 16
        self.donor_anchor_len   = 16

        # Autotransparencia por borde
        self.auto_transparency = False
        self.auto_transp_threshold = 0.60  # 60%

    # ---- configuración pública ----
    def set_mode(self, mode):
        if mode in ("auto", "act", "slot", "full"):
            self.mode = mode

    def set_use_alpha(self, flag):
        self.use_alpha = bool(flag)

    def set_transparent_index(self, idx):
        self.trans_index = max(0, min(255, int(idx)))
        # sincroniza en las paletas que gestionamos
        for p in (self.global_act, self.global_act_slot, self.global_act_full, self.default_palette, self.donor_palette):
            if p:
                p.trans_index = self.trans_index
        for gp in self.group_last.values():
            gp.trans_index = self.trans_index
        for p in self.exact_map.values():
            p.trans_index = self.trans_index

    def set_auto_transparency(self, flag, threshold=None):
        self.auto_transparency = bool(flag)
        if threshold is not None:
            try:
                self.auto_transp_threshold = max(0.0, min(1.0, float(threshold)))
            except Exception:
                pass

    def set_shared_palette_key(self, g, i):
        self.shared_palette_key = (int(g), int(i))

    def load_act(self, path):
        self.global_act = Palette.from_act_file(path, trans_index=self.trans_index)
        # Hornea variantes
        self._bake_act_variants()
        return True

    def set_default_palette_from_image(self, pil_image):
        p = Palette.from_embedded_PIL_palette(pil_image, trans_index=self.trans_index)
        if p:
            self.default_palette = p
            return True
        return False

    def set_exact_palette(self, group, image, pil_image_or_palette):
        """Registra explícitamente una paleta exacta para (group,image)."""
        if isinstance(pil_image_or_palette, Palette):
            pal = pil_image_or_palette
        else:
            pal = Palette.from_embedded_PIL_palette(pil_image_or_palette, trans_index=self.trans_index)
        if pal:
            self.exact_map[(int(group), int(image))] = pal
            return True
        return False

    def set_donor_palette(self, pil_image_or_palette):
        """Define la paleta donante para alinear índices al rango ancla."""
        if isinstance(pil_image_or_palette, Palette):
            self.donor_palette = pil_image_or_palette
        else:
            p = Palette.from_embedded_PIL_palette(pil_image_or_palette, trans_index=self.trans_index)
            if p:
                self.donor_palette = p
            else:
                self.donor_palette = None
        return self.donor_palette is not None

    def set_donor_anchor(self, start, length):
        self.donor_anchor_start = max(0, min(255, int(start)))
        self.donor_anchor_len   = max(1, min(256, int(length)))

    # ---- helpers internos ----

    def _bake_act_variants(self):
        """Construye variantes slot/full de la ACT global."""
        if not self.global_act:
            self.global_act_slot = None
            self.global_act_full = None
            return
        # FULL = ACT cruda
        full = _rgb_list_from_flat(self.global_act.pal)
        self.global_act_full = Palette(_flatten_palette_rgb(full), trans_index=self.trans_index)

        # SLOT = detecta bloque de color y lo ubica en rango ancla
        slot = self._act_to_slot(full, self.donor_anchor_start, self.donor_anchor_len, reverse=False)
        self.global_act_slot = Palette(_flatten_palette_rgb(slot), trans_index=self.trans_index)

    @staticmethod
    def _find_largest_color_block(rgb256):
        """Devuelve (start,length) del mayor bloque no-negro."""
        def is_black(rgb): return rgb == (0,0,0)
        best_s, best_len = 0, 0
        s, n = None, 0
        for i, rgb in enumerate(rgb256):
            if not is_black(rgb):
                if s is None: s, n = i, 1
                else: n += 1
            else:
                if s is not None and n > best_len:
                    best_s, best_len = s, n
                s, n = None, 0
        if s is not None and n > best_len:
            best_s, best_len = s, n
        if best_len == 0:
            return 0, 0
        return best_s, best_len

    @classmethod
    def _act_to_slot(cls, pal_rgb, dest_start=16, keep_len=16, reverse=False):
        """Como en viewer_lib: coloca el bloque de color más largo en el slot."""
        if not pal_rgb or len(pal_rgb) < 256:
            return [(0,0,0)]*256
        src_s, src_len = cls._find_largest_color_block(pal_rgb)
        if src_len <= 0:
            return [(0,0,0)]*256
        L = min(keep_len, src_len, 256)
        out = [(0,0,0)]*256
        out[0] = (0,0,0)
        segment = pal_rgb[src_s:src_s+L]
        if reverse:
            segment = list(reversed(segment))
        dst_end = min(dest_start + L, 256)
        for i in range(dest_start, dst_end):
            out[i] = segment[i - dest_start]
        return out

    def _remember_group_palette(self, group, image, pil_image):
        """Memoriza embebida: exacta(g,i) y last-by-group/default."""
        p = Palette.from_embedded_PIL_palette(pil_image, trans_index=self.trans_index)
        if p:
            self.exact_map[(int(group), int(image))] = p
            self.group_last[int(group)] = p
            if self.default_palette is None:
                self.default_palette = p

    def _pick_auto_palette(self, group, image):
        """
        Orden de preferencia:
        1) exacta (g,i)
        2) compartida (shared_palette_key)
        3) última del grupo
        4) default
        """
        key = (int(group), int(image))
        if key in self.exact_map: return self.exact_map[key]
        if self.shared_palette_key in self.exact_map:
            return self.exact_map[self.shared_palette_key]
        if int(group) in self.group_last:
            return self.group_last[int(group)]
        return self.default_palette

    def _auto_pick_transparent_index(self, imP):
        """Elige índice transparente por borde si auto_transparency=True."""
        if not self.auto_transparency:
            return self.trans_index
        try:
            hist = _border_index_histogram(imP)
            total = float(sum(hist))
            if total <= 0:
                return self.trans_index
            k = max(range(256), key=lambda i: hist[i])
            if hist[k]/total >= float(self.auto_transp_threshold):
                return k
        except Exception:
            pass
        return self.trans_index

    def _build_index_mask(self, imP, trans_idx):
        """Máscara por índice fijo desde imagen en 'P'."""
        if imP.mode != "P":
            imP = imP.convert("P")
        return imP.point(lambda p: 0 if p == trans_idx else 255).convert("L")

    def _build_index_remap_to_donor(self, src_flat, donor_flat, used_idxs=None):
        """
        LUT índice→índice para llevar índices usados del sprite
        al orden del rango ancla de la paleta donante.
        0 sagrado (trans_index) permanece 0.
        """
        if not src_flat or not donor_flat:
            return [i for i in range(256)]
        src_rgb = _rgb_list_from_flat(src_flat)
        don_rgb = _rgb_list_from_flat(donor_flat)
        if not src_rgb or not don_rgb:
            return [i for i in range(256)]

        start = int(self.donor_anchor_start)
        end   = min(start + int(self.donor_anchor_len), 256)
        allowed = range(start, end)
        if not used_idxs:
            used_idxs = range(256)

        remap = [i for i in range(256)]
        T = self.trans_index
        for i in used_idxs:
            if i == T:
                remap[i] = T
                continue
            rs, gs, bs = src_rgb[i]
            best_k, best_d = start, 1<<30
            for k in allowed:
                r,g,b = don_rgb[k]
                d = (rs-r)*(rs-r) + (gs-g)*(gs-g) + (bs-b)*(bs-b)
                if d < best_d:
                    best_d, best_k = d, k
                    if d == 0: break
            # evita mapear a T
            remap[i] = best_k if best_k != T else (allowed[0] if allowed[0] != T else i)
        # nadie más cae en T
        for i in range(256):
            if i != T and remap[i] == T:
                remap[i] = i
        return remap

    # ---- API principal para el viewer/juego ----
    def render_to_rgba(self, pil_image, group, image=0):
        """
        pil_image: PIL.Image del sprite (PCX/PNG indexado, etc).
        group,image: usados para memoria de paletas exactas.
        Devuelve PIL.Image en RGBA.
        """
        # Si ya es RGBA (p.ej. PNG truecolor de SFFv2), respetar tal cual
        if pil_image.mode == "RGBA":
            return pil_image

        if pil_image.mode == "P":
            self._remember_group_palette(group, image, pil_image)

        # Modo ACT “full” o “act”: forzar ACT
        if self.mode in ("act", "slot", "full") and self.global_act:
            # Elegir variante
            if self.mode == "full" and self.global_act_full:
                target = self.global_act_full
            elif self.mode == "slot" and self.global_act_slot:
                target = self.global_act_slot
            else:
                target = self.global_act

            imP = pil_image.convert("P")

            # Autotransparencia por borde (opcional)
            t_idx = self._auto_pick_transparent_index(imP)
            target.trans_index = t_idx

            # Donor alignment (opcional; solo tiene sentido en slot/act)
            if self.use_donor_alignment and self.donor_palette:
                used = imP.histogram()[:256]
                used_idxs = [i for i,c in enumerate(used) if c]
                # paleta de origen: embebida si hay, si no default/last
                emb = Palette.from_embedded_PIL_palette(pil_image, trans_index=self.trans_index)
                src_flat = (emb.pal if emb else (self._pick_auto_palette(group, image).pal
                                                 if self._pick_auto_palette(group, image) else None))
                lut = self._build_index_remap_to_donor(src_flat, self.donor_palette.pal, used_idxs=used_idxs) if src_flat else None
                if lut:
                    imP = imP.point(lambda p: lut[p])

            return target.apply_to_indexed_P(imP, use_alpha=self.use_alpha)

        # AUTO
        if pil_image.mode == "P":
            emb = Palette.from_embedded_PIL_palette(pil_image, trans_index=self.trans_index)
        else:
            emb = None

        pal = self._pick_auto_palette(group, image) if not emb else emb
        if pal:
            imP = pil_image.convert("P")
            # Autotransparencia por borde (opcional)
            pal.trans_index = self._auto_pick_transparent_index(imP)
            return pal.apply_to_indexed_P(imP, use_alpha=self.use_alpha)

        # Sin paletas disponibles: degrade a RGBA directo
        return pil_image.convert("RGBA")
