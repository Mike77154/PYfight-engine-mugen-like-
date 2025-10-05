# -*- coding: utf-8 -*-
from __future__ import print_function
import io, os, struct, collections

# Py2/3 shims
try:
    basestring
except NameError:
    basestring = (str, bytes)
try:
    long
except NameError:
    long = int

try:
    from PIL import Image
    PIL_OK = True
except Exception:
    PIL_OK = False

SFFHeader = collections.namedtuple("SFFHeader", [
    "signature","verhi","verlo","verlo2","verlo3",
    "num_groups","num_images","first_subfile_offset",
    "subheader_size","palette_type","comments"
])

SFFSubfile = collections.namedtuple("SFFSubfile", [
    "index","offset","next_offset","length","axis_x","axis_y",
    "group","image","shared","raw","linked_index"
])

class SFFv1(object):
    """
    Parser SFF v1 tolerante:
    - Intenta primero el modo 'lista enlazada' (usando offsets).
    - Si falla, usa un escaneo lineal desde 0x200 (y/o first_off).
    - Nunca crashea: acumula avisos en self.warnings.
    """
    def __init__(self, fp, tolerant=True, force_subhdr_size=None, max_linear_scan=20000000):
        if isinstance(fp, basestring):
            self._fh = open(fp, "rb"); self._owns = True
        else:
            self._fh = fp; self._owns = False

        self.header = None
        self.subfiles = []
        self._blob_cache = {}
        self.tolerant = tolerant
        self.force_subhdr_size = force_subhdr_size
        self.max_linear_scan = max_linear_scan  # bytes to scan max
        self.warnings = []

        self._parse()

    def close(self):
        try:
            if self._owns and self._fh: self._fh.close()
        except:
            pass

    def _read(self, n):
        b = self._fh.read(n)
        if len(b) != n:
            raise IOError("EOF leyendo %d bytes" % n)
        return b

    # ------------------ PARSE ------------------

    def _parse(self):
        self._fh.seek(0, os.SEEK_SET)
        hdr = self._read(512)

        if hdr[0:12] != b"ElecbyteSpr\0":
            raise ValueError("SFF inválido (firma)")

        verhi, verlo, verlo2, verlo3 = struct.unpack("<BBBB", hdr[12:16])

        # Detecta SFF v2 explícito
        if (verhi, verlo) == (1, 1):
            raise ValueError("SFF v2 detectado (M.U.G.E.N 1.0/1.1). Este parser es SFF v1.")

        num_groups   = struct.unpack("<I", hdr[16:20])[0]
        num_images   = struct.unpack("<I", hdr[20:24])[0]
        first_off    = struct.unpack("<I", hdr[24:28])[0]
        subhdr_size0 = struct.unpack("<I", hdr[28:32])[0]
        palette_type = struct.unpack("<B", hdr[32:33])[0]
        comments     = hdr[36:512]

        # subheader size: usar override o caer a 32 si viene raro
        if self.force_subhdr_size:
            subhdr_size = int(self.force_subhdr_size)
        else:
            subhdr_size = subhdr_size0 if subhdr_size0 in (28, 32) else 32

        self.header = SFFHeader(
            signature=hdr[0:12],
            verhi=verhi, verlo=verlo, verlo2=verlo2, verlo3=verlo3,
            num_groups=num_groups, num_images=num_images,
            first_subfile_offset=first_off,
            subheader_size=subhdr_size, palette_type=palette_type,
            comments=comments
        )

        # Info de tamaño de archivo
        self._fh.seek(0, os.SEEK_END)
        fsize = self._fh.tell()

        # 1) Intento modo Linked-List exacto
        try:
            self._parse_linked(first_off, subhdr_size, fsize)
            return
        except Exception as e:
            if not self.tolerant:
                raise
            self.warnings.append("Fallo modo offsets: %s" % (e,))

        # 2) Modo lineal tolerante (recorre a partir de candidatos)
        self.subfiles[:] = []
        self._blob_cache.clear()
        parsed = self._parse_linear([first_off, 512], subhdr_size, fsize)
        if parsed == 0:
            raise IOError("No se encontraron subfiles en modo tolerante. Archivo quizá truncado o no v1.")

    def _parse_linked(self, off, subhdr_size, fsize):
        self._guard(off, subhdr_size, fsize)
        idx = 0
        seen = set()
        while off and off not in seen:
            seen.add(off)
            self._guard(off, subhdr_size, fsize)
            self._fh.seek(off, os.SEEK_SET)
            sh = self._read(subhdr_size)

            next_off  = struct.unpack("<I", sh[0:4])[0]
            length    = struct.unpack("<I", sh[4:8])[0]
            axis_x    = struct.unpack("<h", sh[8:10])[0]
            axis_y    = struct.unpack("<h", sh[10:12])[0]
            group     = struct.unpack("<H", sh[12:14])[0]
            image     = struct.unpack("<H", sh[14:16])[0]
            shared    = struct.unpack("<H", sh[16:18])[0] if subhdr_size >= 18 else 0

            raw = None
            linked = None

            if length > 0:
                self._guard(off + subhdr_size, length, fsize)
                self._fh.seek(off + subhdr_size, os.SEEK_SET)
                raw = self._read(length)
                self._blob_cache[idx] = raw
            else:
                linked = self._find_owner_index(idx, group, image)

            self.subfiles.append(SFFSubfile(
                index=idx, offset=off, next_offset=next_off, length=length,
                axis_x=axis_x, axis_y=axis_y, group=group, image=image,
                shared=shared, raw=raw, linked_index=linked
            ))

            idx += 1
            off = next_off

        # Resolver enlazados
        for sf in self.subfiles:
            if sf.length == 0 and sf.linked_index is not None:
                owner = self._blob_cache.get(sf.linked_index)
                if owner is not None:
                    self._blob_cache[sf.index] = owner

    def _parse_linear(self, starts, subhdr_size, fsize):
        """
        Escaneo tolerante: intenta desde varios 'starts' (first_off, 512).
        Si next_offset es inválido, avanza secuencialmente (subhdr+len).
        Se detiene si se sale de rango o supera max_linear_scan.
        """
        idx = 0
        seen_offsets = set()

        for start in starts:
            if not isinstance(start, (int, long)) or start <= 0:
                continue
            off = start
            scanned = 0

            while True:
                if off in seen_offsets:
                    break
                if off < 0 or off + subhdr_size > fsize:
                    break
                if scanned > self.max_linear_scan:
                    self.warnings.append("Escaneo lineal alcanzó límite de %d bytes" % self.max_linear_scan)
                    break

                self._fh.seek(off, os.SEEK_SET)
                try:
                    sh = self._read(subhdr_size)
                except Exception as e:
                    self.warnings.append("EOF leyendo subheader en off=%d: %s" % (off, e))
                    break

                try:
                    next_off  = struct.unpack("<I", sh[0:4])[0]
                    length    = struct.unpack("<I", sh[4:8])[0]
                    axis_x    = struct.unpack("<h", sh[8:10])[0]
                    axis_y    = struct.unpack("<h", sh[10:12])[0]
                    group     = struct.unpack("<H", sh[12:14])[0]
                    image     = struct.unpack("<H", sh[14:16])[0]
                    shared    = struct.unpack("<H", sh[16:18])[0] if subhdr_size >= 18 else 0
                except Exception as e:
                    self.warnings.append("Header inválido en off=%d: %s" % (off, e))
                    break

                raw = None
                linked = None
                blob_pos = off + subhdr_size

                if length > 0 and (0 <= blob_pos <= fsize) and (blob_pos + length <= fsize):
                    # Leer blob
                    self._fh.seek(blob_pos, os.SEEK_SET)
                    try:
                        raw = self._read(length)
                        self._blob_cache[idx] = raw
                    except Exception as e:
                        self.warnings.append("EOF en blob off=%d len=%d: %s" % (blob_pos, length, e))
                        raw = None
                else:
                    # Considerar sprite enlazado
                    linked = self._find_owner_index(idx, group, image)
                    if length > 0:
                        # length parece inválido → warning
                        self.warnings.append("Longitud fuera de rango en off=%d len=%d; tratando como linked" % (off, length))

                self.subfiles.append(SFFSubfile(
                    index=idx, offset=off, next_offset=next_off, length=length,
                    axis_x=axis_x, axis_y=axis_y, group=group, image=image,
                    shared=shared, raw=raw, linked_index=linked
                ))
                seen_offsets.add(off)
                idx += 1
                # Resolver next (siempre define 'step')
                # Caso 1: usar puntero de lista enlazada si es válido y avanza
                step = None
                if next_off and (next_off > off) and (next_off <= fsize):
                    step = next_off - off
                    off = next_off

                # Caso 2: fallback secuencial si 'next_off' no sirve
                if step is None:
                    blob_ok = (length > 0) and ((blob_pos + length) <= fsize)
                    step = subhdr_size + (length if blob_ok else 0)

                    # Paso mínimo de seguridad (evita bucles infinitos)
                    if step <= 0:
                        self.warnings.append(
                            "Step <= 0 en off=%d (len=%d, blob_ok=%s)" % (off, length, blob_ok)
                        )
                        break

                    # No salirse del archivo
                    if off + step > fsize:
                        self.warnings.append(
                            "Step fuera de rango: off=%d step=%d size=%d" % (off, step, fsize)
                        )
                        break

                    off += step

                # Avance total escaneado
                scanned += step


            if idx > 0:
                break  # ya parseamos algo útil; no probar más starts

        # Resolver enlazados
        for sf in self.subfiles:
            if sf.length == 0 and sf.linked_index is not None:
                owner = self._blob_cache.get(sf.linked_index)
                if owner is not None:
                    self._blob_cache[sf.index] = owner

        return idx

    # ------------------ HELPERS ------------------

    def _guard(self, off, need, fsize):
        if off < 0 or off + need > fsize:
            raise IOError("Offset fuera de rango (off=%d, need=%d, size=%d)" % (off, need, fsize))

    def _find_owner_index(self, idx, g, i):
        best = None
        for j in range(idx - 1, -1, -1):
            sf = self.subfiles[j]
            if sf.length > 0 and self._blob_cache.get(j):
                if sf.group == g and sf.image == i:
                    return j
                if best is None:
                    best = j
        return best

    # ------------------ API ------------------

    def list_sprites(self):
        return [(sf.index, sf.group, sf.image, sf.axis_x, sf.axis_y)
                for sf in self.subfiles]

    def _resolve_index(self, key):
        if isinstance(key, (int, long)):
            return key if 0 <= key < len(self.subfiles) else None
        if isinstance(key, tuple) and len(key) == 2:
            g, i = key
            for sf in self.subfiles:
                if sf.group == g and sf.image == i:
                    return sf.index
        return None

    def get_blob(self, key):
        idx = self._resolve_index(key)
        return self._blob_cache.get(idx) if idx is not None else None

    def export_png(self, key, out_path):
        blob = self.get_blob(key)
        if not blob:
            raise ValueError("Sin datos para %r" % (key,))
        if PIL_OK:
            bio = io.BytesIO(blob)
            try:
                im = Image.open(bio); im.load(); im.save(out_path, "PNG")
                return ("png", out_path)
            except Exception:
                base,_ = os.path.splitext(out_path); pcx = base + ".pcx"
                f = open(pcx,"wb"); f.write(blob); f.close()
                return ("pcx-raw", pcx)
        base,_ = os.path.splitext(out_path); pcx = base + ".pcx"
        f = open(pcx,"wb"); f.write(blob); f.close()
        return ("pcx-raw", pcx)

    def export_all(self, out_dir):
        if not os.path.isdir(out_dir): os.makedirs(out_dir)
        res=[]
        for sf in self.subfiles:
            name = "spr_%05d_g%d_i%d.png"%(sf.index,sf.group,sf.image)
            kind,path = self.export_png(sf.index, os.path.join(out_dir,name))
            res.append((sf.index, kind, path))
        return res
