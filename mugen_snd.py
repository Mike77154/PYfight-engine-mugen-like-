# -*- coding: utf-8 -*-
"""
mugen_snd.py  (Python 2.7)
Lector de archivos ElecbyteSnd (.SND) estilo M.U.G.E.N / Ikemen.

- Carga cabecera "ElecbyteSnd\0"
- Itera subheaders (numberOfSounds) a partir de subHeaderOffset
- Para cada entrada (group, number) parsea un sub-WAV (PCM) con chunks fmt/data
- Expone:
    MugenSND(path).get_sound(g, n) -> SoundEntry or None
    MugenSND(path).export_wav(g, n, out_path) -> bool
    MugenSND(path).to_pygame_sound(g, n) -> pygame.mixer.Sound

Notas:
- Replica offsets del código SSZ: WAV empieza en subHeaderOffset + 28
- Acepta 8/16 bits, mono/estéreo, little-endian
- No usa NumPy; trabaja con struct + bytearray
"""

from __future__ import division, print_function
import io
import os
import struct

try:
    # pygame es opcional
    import pygame
    _HAS_PYGAME = True
except Exception:
    _HAS_PYGAME = False


ELECBYTE_SIGNATURE = b'ElecbyteSnd\x00'  # 12 bytes

def _u32_le(b):  # unsigned 32
    return struct.unpack('<I', b)[0]

def _s32_le(b):  # signed 32
    return struct.unpack('<i', b)[0]

def _u16_le(b):  # unsigned 16
    return struct.unpack('<H', b)[0]

def _read_exact(f, n):
    data = f.read(n)
    if data is None or len(data) != n:
        raise EOFError("Unexpected EOF")
    return data

class SoundEntry(object):
    """ Contenedor de un sonido PCM extraído del .SND """
    __slots__ = ('group', 'number', 'channels', 'sample_rate',
                 'bits_per_sample', 'bytes_per_sample', 'pcm_bytes')
    def __init__(self, group, number, channels, sample_rate, bits_per_sample, pcm_bytes):
        self.group = group
        self.number = number
        self.channels = channels
        self.sample_rate = sample_rate
        self.bits_per_sample = bits_per_sample
        self.bytes_per_sample = bits_per_sample // 8
        self.pcm_bytes = pcm_bytes  # raw PCM little-endian

    def __repr__(self):
        return ("<SoundEntry g={0} n={1} ch={2} sr={3} bits={4} len={5}>"
                .format(self.group, self.number, self.channels,
                        self.sample_rate, self.bits_per_sample, len(self.pcm_bytes)))


class MugenSND(object):
    """
    Lector de .SND. Tras load(), self.sounds[(group,number)] -> SoundEntry
    """
    def __init__(self, path):
        self.path = path
        self.version_lo = 0
        self.version_hi = 0
        self.num_sounds = 0
        self.first_subheader_off = 0
        self.sounds = {}  # (group, number) -> SoundEntry
        self._load()

    # -------- WAV helpers (mínimos) --------
    @staticmethod
    def _write_wav(outfile_path, entry):
        """
        Escribe WAV PCM little-endian (RIFF/WAVE) desde un SoundEntry.
        """
        data = entry.pcm_bytes
        num_channels = entry.channels
        sample_rate = entry.sample_rate
        bits = entry.bits_per_sample
        block_align = (num_channels * bits) // 8
        byte_rate = sample_rate * block_align
        data_chunk_size = len(data)
        fmt_chunk_size = 16
        riff_chunk_size = 4 + (8 + fmt_chunk_size) + (8 + data_chunk_size)

        with open(outfile_path, 'wb') as wf:
            # RIFF header
            wf.write(b'RIFF')
            wf.write(struct.pack('<I', riff_chunk_size))
            wf.write(b'WAVE')
            # fmt chunk
            wf.write(b'fmt ')
            wf.write(struct.pack('<I', fmt_chunk_size))
            wf.write(struct.pack('<H', 1))  # PCM
            wf.write(struct.pack('<H', num_channels))
            wf.write(struct.pack('<I', sample_rate))
            wf.write(struct.pack('<I', byte_rate))
            wf.write(struct.pack('<H', block_align))
            wf.write(struct.pack('<H', bits))
            # data chunk
            wf.write(b'data')
            wf.write(struct.pack('<I', data_chunk_size))
            wf.write(data)
        return True

    @staticmethod
    def _read_chunk_id(f):
        cid = f.read(4)
        if not cid or len(cid) < 4:
            return None
        return cid

    def _parse_embedded_wav(self, f, sub_off, end_pos_hint, sub_len_hint):
        """
        Parsea RIFF/WAVE PCM dentro del rango [start,end).
        - start: sub_off
        - end:   end_pos_hint (si > sub_off), si no sub_off + sub_len_hint (si >0), si no EOF
        - primer intento: sub_off + 28
        - si falla: escaneo 'RIFF' seguido de 'WAVE' dentro del rango
        """
        # ------ calcular límites ------
        f.seek(0, os.SEEK_END)
        file_end = f.tell()
        if end_pos_hint and end_pos_hint > sub_off and end_pos_hint <= file_end:
            sub_end = end_pos_hint
        elif sub_len_hint and sub_len_hint > 0:
            sub_end = min(sub_off + sub_len_hint, file_end)
        else:
            sub_end = file_end  # sin pista: usar EOF como cota superior

        def _ensure(nbytes):
            if f.tell() + nbytes > sub_end:
                raise EOFError("Subfile bounds exceeded")

        def _try_at(start_pos):
            if start_pos < sub_off or start_pos + 12 > sub_end:
                raise ValueError("candidate out of range")
            f.seek(start_pos)
            _ensure(12)
            if _read_exact(f, 4) != b'RIFF':
                raise ValueError("Not RIFF")
            riff_size = _u32_le(_read_exact(f, 4))
            if _read_exact(f, 4) != b'WAVE':
                raise ValueError("Not WAVE")

            fmt_found = False
            data_found = False
            channels = None
            sample_rate = None
            bits = None
            pcm = None

            while True:
                if f.tell() + 8 > sub_end:
                    break
                cid = f.read(4)
                if not cid or len(cid) < 4:
                    break
                _ensure(4)
                csize = _u32_le(_read_exact(f, 4))

                if cid == b'fmt ':
                    _ensure(csize)
                    raw = _read_exact(f, csize)
                    if csize < 16:
                        raise ValueError("fmt too small")
                    fmt_code = _u16_le(raw[0:2])
                    if fmt_code != 1:
                        raise ValueError("Not linear PCM (fmt=%d)" % fmt_code)
                    channels = _u16_le(raw[2:4])
                    sample_rate = _u32_le(raw[4:8])
                    bits = _u16_le(raw[14:16])  # válido aun con fmt extendido
                    fmt_found = True
                elif cid == b'data':
                    _ensure(csize)
                    pcm = _read_exact(f, csize)
                    data_found = True
                else:
                    _ensure(csize)
                    f.seek(csize, os.SEEK_CUR)

                # padding par (RIFF)
                if (csize & 1) == 1 and f.tell() + 1 <= sub_end:
                    f.seek(1, os.SEEK_CUR)

                if fmt_found and data_found:
                    break

            if not fmt_found:
                raise ValueError("no fmt")
            if not data_found:
                raise ValueError("no data")

            if channels not in (1, 2):
                raise ValueError("bad channels=%r" % channels)
            if sample_rate < 1 or sample_rate >= 0x100000:
                raise ValueError("bad sr=%r" % sample_rate)
            if bits not in (8, 16):
                raise ValueError("bad bits=%r" % bits)

            return {
                'channels': int(channels),
                'sample_rate': int(sample_rate),
                'bits_per_sample': int(bits),
                'data': pcm
            }

        # 1) Intento rápido al estilo Ikemen
        try:
            return _try_at(sub_off + 28)
        except Exception:
            pass

        # 2) Escaneo acotado dentro del subarchivo
        block = 64 * 1024
        pos = sub_off
        needle = b'RIFF'
        while pos < sub_end:
            f.seek(pos)
            chunk = f.read(min(block, sub_end - pos))
            if not chunk:
                break
            i = 0
            while True:
                j = chunk.find(needle, i)
                if j < 0:
                    break
                cand = pos + j
                # Checar 'WAVE' a +8
                if cand + 12 <= sub_end and chunk[j+8:j+12] == b'WAVE':
                    try:
                        return _try_at(cand)
                    except Exception:
                        pass
                i = j + 1
            pos += len(chunk)

        raise ValueError("RIFF/WAVE not found inside subfile")


    # -------- Carga del .SND --------
    def _load(self):
        with open(self.path, 'rb') as f:
            sig = _read_exact(f, 12)
            if sig != ELECBYTE_SIGNATURE:
                raise ValueError("Not ElecbyteSnd")

            self.version_lo = _u16_le(_read_exact(f, 2))
            self.version_hi = _u16_le(_read_exact(f, 2))
            self.num_sounds = _u32_le(_read_exact(f, 4))
            self.first_subheader_off = _u32_le(_read_exact(f, 4))

            sub_off = self.first_subheader_off
            seen = 0
            guard = 0
            while sub_off and guard < (self.num_sounds + 4096):
                guard += 1
                f.seek(sub_off)
                try:
                    hdr = _read_exact(f, 16)
                except EOFError:
                    break
                next_sub = _u32_le(hdr[0:4])
                sub_len  = _u32_le(hdr[4:8])
                group    = _s32_le(hdr[8:12])
                number   = _s32_le(hdr[12:16])

                # Solo parsea entradas válidas
                if group >= 0 and number >= 0:
                    try:
                        wav = self._parse_embedded_wav(f, sub_off, next_sub if next_sub != 0 else None, sub_len)
                        entry = SoundEntry(group, number,
                                           wav['channels'],
                                           wav['sample_rate'],
                                           wav['bits_per_sample'],
                                           wav['data'])
                        self.sounds[(group, number)] = entry
                        seen += 1
                    except Exception:
                        # Silencio; si quieres depurar, imprime aquí
                        pass

                # Avanza por lista enlazada; si es inválido, intenta romper por count
                if next_sub == 0 or next_sub == sub_off:
                    break
                sub_off = next_sub

            # Fallback: si no vimos nada pero el archivo parece válido, intenta
            # una última pasada lineal escaneando subheaders cada 16 bytes (muy defensivo).
            if seen == 0:
                f.seek(self.first_subheader_off)
                # intentar hasta 8 MiB en saltos de 16 bytes
                limit = self.first_subheader_off + 8 * 1024 * 1024
                while f.tell() + 16 <= limit:
                    here = f.tell()
                    try:
                        hdr = _read_exact(f, 16)
                    except EOFError:
                        break
                    next_sub = _u32_le(hdr[0:4])
                    sub_len  = _u32_le(hdr[4:8])
                    group    = _s32_le(hdr[8:12])
                    number   = _s32_le(hdr[12:16])
                    if group >= 0 and number >= 0:
                        try:
                            wav = self._parse_embedded_wav(f, here, next_sub if next_sub != 0 else None, sub_len)
                            entry = SoundEntry(group, number,
                                               wav['channels'],
                                               wav['sample_rate'],
                                               wav['bits_per_sample'],
                                               wav['data'])
                            self.sounds[(group, number)] = entry
                            seen += 1
                        except Exception:
                            pass
                    f.seek(here + 16, os.SEEK_SET)


    # -------- API pública --------
    def list_keys(self):
        """ Devuelve lista de (group, number) presentes. """
        return sorted(self.sounds.keys())

    def get_sound(self, group, number):
        """ Devuelve SoundEntry o None. """
        return self.sounds.get((int(group), int(number)))

    def export_wav(self, group, number, out_path):
        """ Escribe el sonido como .wav en disco. """
        entry = self.get_sound(group, number)
        if not entry:
            return False
        return self._write_wav(out_path, entry)

    def to_pygame_sound(self, group, number):
        """
        Crea pygame.mixer.Sound desde el PCM del entry.
        Requiere que pygame.mixer esté inicializado *con el mismo formato*:
          - frecuencia = entry.sample_rate
          - tamaño = -16 si 16-bit signed; 8 si 8-bit unsigned
          - channels = entry.channels
        Si el mixer no coincide, conviértelo o reinit.
        """
        if not _HAS_PYGAME:
            raise RuntimeError("pygame no disponible")
        entry = self.get_sound(group, number)
        if not entry:
            return None

        # Comprobar formato del mixer
        freq, fmt, ch = pygame.mixer.get_init() or (None, None, None)
        wanted_bits = entry.bits_per_sample
        # pygame usa tamaño negativo para signed (e.g. -16)
        if wanted_bits == 16:
            required_fmt = -16
        elif wanted_bits == 8:
            required_fmt = 8  # unsigned 8-bit
        else:
            raise ValueError("Bits no soportados por pygame: %r" % wanted_bits)

        if (freq != entry.sample_rate) or (fmt != required_fmt) or (ch != entry.channels):
            raise RuntimeError("Formato mixer no coincide. mixer=%r, requerido=(%d,%d,%d)" %
                               ((freq, fmt, ch), entry.sample_rate, required_fmt, entry.channels))

        # pygame 1.9.6 acepta bytes raw como buffer
        return pygame.mixer.Sound(buffer=entry.pcm_bytes)


# ---------- Ejemplo de uso ----------
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python mugen_snd.py path_al_archivo.snd [export_dir]")
        sys.exit(1)

    snd_path = sys.argv[1]
    snd = MugenSND(snd_path)
    print("Version: %d.%d  NumSounds: %d" % (snd.version_lo, snd.version_hi, snd.num_sounds))
    keys = snd.list_keys()
    print("Entradas:", len(keys))
    for k in keys[:10]:
        print(" ", k, snd.get_sound(*k))

    # Export opcional
    if len(sys.argv) >= 3:
        outdir = sys.argv[2]
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        for (g, n) in keys:
            safe = "g{0}_n{1}.wav".format(g, n)
            outp = os.path.join(outdir, safe)
            ok = snd.export_wav(g, n, outp)
            if not ok:
                print("No se pudo exportar", (g, n))
        print("Export listo en:", outdir)
