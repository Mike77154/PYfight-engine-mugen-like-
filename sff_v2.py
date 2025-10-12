# -*- coding: utf-8 -*-
from __future__ import print_function
import struct, io

try:
    from PIL import Image
except Exception:
    Image = None

def _u8(b, o=0):  return struct.unpack('<B',  b[o:o+1])[0]
def _u16(b, o=0): return struct.unpack('<H', b[o:o+2])[0]
def _u32(b, o=0): return struct.unpack('<I', b[o:o+4])[0]

def _read_at(fh, off, n):
    fh.seek(off)
    return fh.read(n)

# ---------------------- DECOMPRESORES (según SSZ) ----------------------

def _decompress_rle8_sff(blob, w, h):
    """
    RLE8 de SFF v2 (NO es BI_RLE8 de BMP).
    Regla SSZ: si (d & 0xC0) == 0x40 => run: count=(d&0x3F)+1; next byte=valor
               si no => literal de 1 byte
    Devuelve bytes indexados (top-down).
    """
    b = bytearray(blob)
    out = bytearray(w*h)
    i = 0
    j = 0
    n = len(out)
    L = len(b)
    while j < n and i < L:
        d = b[i]; i += 1
        if (d & 0xC0) == 0x40:
            count = (d & 0x3F) + 1
            if i >= L: break
            val = b[i]; i += 1
            # escribir count veces
            k = min(count, n - j)
            out[j:j+k] = bytes([val]) * k
            j += k
        else:
            out[j] = d
            j += 1
    return bytes(out)

def _decompress_rle5(blob, w, h):
    """
    RLE5 de SFF v2 (traducción directa del SSZ rle5Decode).
    """
    b = bytearray(blob)
    out = bytearray(w*h)
    i = 0; j = 0
    n = len(out); L = len(b)
    while j < n and i < L:
        rlen = b[i]; i += 1
        dlen = b[i] & 0x7F
        if i >= L: break
        # bit 7 del segundo byte indica si viene color explícito
        if (b[i] >> 7) != 0:
            if i+1 >= L: break
            c = b[i+1]
            i += 2
        else:
            c = 0
            i += 1
        # repeticiones del color c
        run = rlen + 1
        k = min(run, n - j)
        out[j:j+k] = bytes([c]) * k
        j += k

        # stream de paquetes de 5 bits
        while dlen >= 0 and j < n and i < L:
            byte_ = b[i]; i += 1
            c = byte_ & 0x1F
            rlen = (byte_ >> 5)
            run = rlen + 1
            k = min(run, n - j)
            out[j:j+k] = bytes([c]) * k
            j += k
            dlen -= 1
    return bytes(out)

def _decompress_lz5(blob, w, h):
    """
    LZ5 de SFF v2 (traducción directa del SSZ lz5Decode).
    """
    b = bytearray(blob)
    out = bytearray(w*h)
    i = 0; j = 0
    n = len(out); L = len(b)
    if L == 0:
        return bytes(out)
    s = 0
    rbc = 0
    rb = 0
    ct = b[i]; i += 1

    while j < n:
        if (ct & (1 << s)) != 0:
            # COPY (desde historia)
            if i >= L: break
            d = b[i]; i += 1
            if (d & 0x3F) == 0:
                if i+1 >= L: break
                d = ((d << 2) | b[i]); i += 1
                d += 1
                if i >= L: break
                size = b[i] + 2; i += 1
            else:
                rb |= (d & 0xC0) >> rbc
                rbc += 2
                size = (d & 0x3F)
                if rbc < 8:
                    if i >= L: break
                    d = b[i] + 1; i += 1
                else:
                    d = rb + 1
                    rbc = 0; rb = 0
            run = size + 1
            for _ in range(run):
                if j >= n: break
                out[j] = out[j - d]
                j += 1
        else:
            # LITERAL
            if i >= L: break
            d = b[i]; i += 1
            if (d & 0xE0) == 0:
                if i >= L: break
                size = b[i] + 8; i += 1
            else:
                size = (d >> 5)
                d = d & 0x1F
            run = size + 1
            k = min(run, n - j)
            out[j:j+k] = bytes([d]) * k
            j += k

        s += 1
        if s >= 8:
            s = 0
            if i >= L: break
            ct = b[i]; i += 1
    return bytes(out)

# (Opcional) Conservamos tu BI_RLE8 por si te sirve en otro contexto.
def _decompress_rle8_bmp(blob, w, h, bottom_up=False):
    px = bytearray(w * h)
    x = 0
    y = (h - 1) if bottom_up else 0
    y_step = -1 if bottom_up else 1
    i = 0
    L = len(blob)
    def new_line():
        return 0, (y + y_step)
    while i < L and 0 <= y < h:
        if i + 1 > L: break
        cnt = blob[i]; i += 1
        if cnt > 0:
            if i >= L: break
            val = blob[i]; i += 1
            for _ in range(cnt):
                if x >= w:
                    x, y = new_line()
                    if not (0 <= y < h): break
                px[y*w + x] = val
                x += 1
            continue
        # cnt == 0 => comando
        if i >= L: break
        cmd = blob[i]; i += 1
        if cmd == 0:   # EOL
            x, y = new_line()
        elif cmd == 1: # EOB
            break
        elif cmd == 2: # Delta
            if i + 1 >= L: break
            dx = blob[i]; dy = blob[i+1]; i += 2
            x += dx
            y += (dy * y_step)
        else:          # Absolutos
            n = cmd
            if i + n > L: n = max(0, L - i)
            for k in range(n):
                if x >= w:
                    x, y = new_line()
                    if not (0 <= y < h): break
                px[y*w + x] = blob[i + k]
                x += 1
            i += n
            if (n & 1) == 1 and i < L:
                i += 1
    return bytes(px)

# ----------------------------------------------------------------------

class SFFv2(object):
    """
    Lector SFF v2 (Elecbyte). Devuelve PIL.Image en modo 'P' por índice:
        im = sff.get_pil_indexed(i)  # 'P', con palette aplicada
    Ahora soporta: NONE (0x00), RLE8 (0x02 SFF), RLE5 (0x03), LZ5 (0x04),
                   PNG8 (0x0A), PNG truecolor/alpha (0x0B/0x0C).
    """
    def __init__(self, path):
        if Image is None:
            raise RuntimeError("Pillow requerido para SFFv2")
        self._fh = open(path, 'rb')
        self._parse_header()
        self._read_palette_map()
        self._read_sprite_list()

    def close(self):
        try:
            self._fh.close()
        except:
            pass

    # ---------------- Header ----------------
    def _parse_header(self):
        fh = self._fh
        hdr = _read_at(fh, 0, 0x44 + 444)
        if hdr[0:12] != b'ElecbyteSpr\x00':
            raise ValueError("Firma inválida")
        self.ver_lo3 = _u8(hdr, 0x0C)
        self.ver_lo2 = _u8(hdr, 0x0D)
        self.ver_lo1 = _u8(hdr, 0x0E)
        self.ver_hi  = _u8(hdr, 0x0F)

        # offsets/contadores clave (según layout v2)
        self.palette_map_offset  = _u32(hdr, 0x1A)
        self.sprite_list_offset  = _u32(hdr, 0x24)
        self.num_sprites         = _u32(hdr, 0x28)
        self._unk_0x2C           = _u32(hdr, 0x2C)
        self.num_palettes        = _u32(hdr, 0x30)
        self.palette_bank_offset = _u32(hdr, 0x34)
        self.ondemand_size       = _u32(hdr, 0x38)
        self.ondemand_total      = _u32(hdr, 0x3C)
        self.onload_size         = _u32(hdr, 0x40)

        # bases
        self.header_size       = 0x44 + 444
        self.palette_map_base  = self.palette_map_offset
        self.sprite_list_base  = self.sprite_list_offset
        self.palette_bank_base = self.palette_bank_offset

        self.sprite_list_size  = self.num_sprites * 28
        self.onload_base       = self.sprite_list_base + self.sprite_list_size
        self.ondemand_base     = self.onload_base + self.onload_size

    # --------------- Palette map ---------------
    def _read_palette_map(self):
        """
        Paleta v2: cada entrada son 16 bytes:
            0x00: group   (u16)
            0x02: number  (u16)
            0x04: dummy   (u16)
            0x06: link    (u16)  -> índice a otra paleta si length==0
            0x08: ofs     (u32)  -> relativo a palette_bank_base
            0x0C: length  (u32)  -> 4*colors (r,g,b,dummy)
        """
        self.pal_entries = []
        base = self.palette_map_base
        for i in range(self.num_palettes):
            ent = _read_at(self._fh, base + i*16, 16)
            group   = _u16(ent, 0x00)
            number  = _u16(ent, 0x02)
            dummy   = _u16(ent, 0x04)
            link    = _u16(ent, 0x06)
            data_of = _u32(ent, 0x08)  # relativo al palette_bank_base
            length  = _u32(ent, 0x0C)
            self.pal_entries.append({
                'group': group, 'number': number, 'dummy': dummy,
                'link': link, 'data_ofs': data_of, 'length': length
            })

    def _read_palette_rgba(self, pal_index, _seen=None):
        """
        Devuelve lista de 256 (r,g,b,a=255). Si length==0 usa paleta 'link'.
        Los elementos del banco son 4 bytes: r, g, b, dummy (SSZ).
        """
        if pal_index is None or pal_index < 0 or pal_index >= len(self.pal_entries):
            return [(0,0,0,255)] * 256
        if _seen is None: _seen = set()
        if pal_index in _seen:
            # Evitar ciclos de link
            return [(0,0,0,255)] * 256
        _seen.add(pal_index)

        p = self.pal_entries[pal_index]
        if p['length'] == 0:
            # paleta linkeada
            link = p['link']
            if 0 <= link < len(self.pal_entries):
                return self._read_palette_rgba(link, _seen=_seen)
            return [(0,0,0,255)] * 256

        raw = _read_at(self._fh, self.palette_bank_base + p['data_ofs'], p['length'])
        cols = len(raw) // 4  # cada color: r,g,b,dummy
        out = []
        for c in range(cols):
            off = 4*c
            if off+3 >= len(raw): break
            r = raw[off+0] & 0xFF
            g = raw[off+1] & 0xFF
            b = raw[off+2] & 0xFF
            # raw[off+3] es dummy
            out.append((r,g,b,255))
        # normaliza a 256 entradas
        if len(out) < 256:
            out += [(0,0,0,255)] * (256 - len(out))
        return out[:256]

    def _palette_rgba_to_flat_rgb(self, pal_rgba):
        flat = []
        for (r,g,b,a) in pal_rgba:
            flat.extend([r & 255, g & 255, b & 255])
        if len(flat) < 768:
            flat += [0] * (768 - len(flat))
        return flat[:768]

    # --------------- Sprite list ---------------
    def _read_sprite_list(self):
        """
        Sprite header v2 (28 bytes):
          0x00 group(u16) 0x02 number(u16) 0x04 w(u16) 0x06 h(u16)
          0x08 xaxis(i16) 0x0A yaxis(i16) 0x0C link(u16)
          0x0E fmt(u8)    0x0F depth(u8)   0x10 ofs(u32) 0x14 len(u32)
          0x18 pal(u16)   0x1A load(u16)
        """
        self.sprites = []
        base = self.sprite_list_base
        for i in range(self.num_sprites):
            ent = _read_at(self._fh, base + i*28, 28)
            group  = _u16(ent, 0x00)
            number = _u16(ent, 0x02)
            w      = _u16(ent, 0x04)
            h      = _u16(ent, 0x06)
            xaxis  = struct.unpack('<h', ent[0x08:0x0A])[0]
            yaxis  = struct.unpack('<h', ent[0x0A:0x0C])[0]
            linked = _u16(ent, 0x0C)
            comp   = _u8 (ent, 0x0E)
            depth  = _u8 (ent, 0x0F)
            data_of= _u32(ent, 0x10)
            length = _u32(ent, 0x14)
            palnum = _u16(ent, 0x18)
            loadmd = _u16(ent, 0x1A)

            data_base = self.onload_base if loadmd == 0x01 else self.ondemand_base
            eff = None
            if length > 0:
                eff = data_base + data_of
            else:
                # heredar del enlace si es válido y ya leído
                if 0 <= linked < i:
                    eff = self.sprites[linked]['data_ofs']
                    # heredar paleta también (como shareCopy en SSZ)
                    palnum = self.sprites[linked]['palette_index']
                else:
                    # fallback al último con datos (no ideal pero común)
                    # busca hacia atrás el primer data_ofs no None
                    eff = None
                    for j in range(i-1, -1, -1):
                        if self.sprites[j]['data_ofs'] is not None:
                            eff = self.sprites[j]['data_ofs']
                            palnum = self.sprites[j]['palette_index']
                            break

            self.sprites.append({
                'i': i, 'group': group, 'number': number,
                'w': w, 'h': h, 'xaxis': xaxis, 'yaxis': yaxis,
                'compression': comp, 'depth': depth,
                'data_ofs': eff, 'length': length,
                'palette_index': palnum, 'load_mode': loadmd,
                'linked': linked,
            })

    # --------------- API: imagen indexada PIL ---------------
    def get_pil_indexed(self, index):
        """
        Devuelve PIL.Image con paleta aplicada cuando corresponde.
        - Para 0x0A (PNG8): respeta paleta del PNG (modo 'P').
        - Para 0x0B/0x0C (PNG truecolor): devuelve RGBA y NO aplica paleta.
        """
        if index < 0 or index >= len(self.sprites):
            return None, None
        sp = self.sprites[index]
        if sp['data_ofs'] is None or sp['length'] == 0:
            return None, None

        blob = _read_at(self._fh, sp['data_ofs'], sp['length'])
        w, h = sp['w'], sp['h']
        comp = sp['compression']

        # Descomprimir/decodificar según formato
        if comp == 0x00:  # NONE (indexado crudo)
            pixels = blob[:w*h]
            if len(pixels) < (w*h):
                pixels = pixels + b'\x00' * (w*h - len(pixels))
                pixels = pixels[:w*h]
            im = Image.frombytes('P', (w, h), pixels)
            # aplica paleta externa
            pal_rgba = self._read_palette_rgba(sp['palette_index'])
            im.putpalette(self._palette_rgba_to_flat_rgb(pal_rgba))
            meta = dict(group=sp['group'], image=sp['number'],
                        axis_x=sp['xaxis'], axis_y=sp['yaxis'],
                        width=w, height=h)
            return im, meta

        elif comp == 0x02:  # RLE8 (SFF)
            pixels = _decompress_rle8_sff(blob, w, h)
            if len(pixels) < (w*h):
                pixels += b'\x00' * ((w*h) - len(pixels))
                pixels = pixels[:w*h]
            im = Image.frombytes('P', (w, h), pixels)
            pal_rgba = self._read_palette_rgba(sp['palette_index'])
            im.putpalette(self._palette_rgba_to_flat_rgb(pal_rgba))
            meta = dict(group=sp['group'], image=sp['number'],
                        axis_x=sp['xaxis'], axis_y=sp['yaxis'],
                        width=w, height=h)
            return im, meta

        elif comp == 0x03:  # RLE5
            pixels = _decompress_rle5(blob, w, h)
            if len(pixels) < (w*h):
                pixels += b'\x00' * ((w*h) - len(pixels))
                pixels = pixels[:w*h]
            im = Image.frombytes('P', (w, h), pixels)
            pal_rgba = self._read_palette_rgba(sp['palette_index'])
            im.putpalette(self._palette_rgba_to_flat_rgb(pal_rgba))
            meta = dict(group=sp['group'], image=sp['number'],
                        axis_x=sp['xaxis'], axis_y=sp['yaxis'],
                        width=w, height=h)
            return im, meta

        elif comp == 0x04:  # LZ5
            pixels = _decompress_lz5(blob, w, h)
            if len(pixels) < (w*h):
                pixels += b'\x00' * ((w*h) - len(pixels))
                pixels = pixels[:w*h]
            im = Image.frombytes('P', (w, h), pixels)
            pal_rgba = self._read_palette_rgba(sp['palette_index'])
            im.putpalette(self._palette_rgba_to_flat_rgb(pal_rgba))
            meta = dict(group=sp['group'], image=sp['number'],
                        axis_x=sp['xaxis'], axis_y=sp['yaxis'],
                        width=w, height=h)
            return im, meta

        elif comp == 0x0A:  # PNG8 (indexado en el blob)
            bio = io.BytesIO(blob)
            im = Image.open(bio); im.load()
            if im.mode != 'P':
                im = im.convert('P')
            # La paleta viene del PNG; no sobrescribimos
            meta = dict(group=sp['group'], image=sp['number'],
                        axis_x=sp['xaxis'], axis_y=sp['yaxis'],
                        width=im.size[0], height=im.size[1], rgba=False)
            return im, meta

        elif comp in (0x0B, 0x0C):  # PNG truecolor/alpha
            bio = io.BytesIO(blob)
            im = Image.open(bio); im.load()
            if im.mode != 'RGBA':
                im = im.convert('RGBA')
            # RGBA: NO aplicar paleta externa
            meta = dict(group=sp['group'], image=sp['number'],
                        axis_x=sp['xaxis'], axis_y=sp['yaxis'],
                        width=im.size[0], height=im.size[1], rgba=True)
            return im, meta

        else:
            raise NotImplementedError("Compresión 0x%02X no soportada" % comp)
