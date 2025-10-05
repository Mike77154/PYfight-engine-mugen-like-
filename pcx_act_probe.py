# -*- coding: utf-8 -*-
from __future__ import print_function
import sys, os, struct
try:
    from PIL import Image
except:
    Image = None

def read_file(path):
    f = open(path, "rb")
    try:
        return f.read()
    finally:
        f.close()

def pcx_has_palette(raw_bytes):
    """
    PCX 8bpp con paleta: el byte en -769 debe ser 0x0C, seguido de 768 bytes RGB.
    (Py2: raw_bytes es str; usar ord()).
    """
    if not raw_bytes or len(raw_bytes) < 769:
        return False
    return ord(raw_bytes[-769]) == 12

def pcx_read_embedded_palette(raw_bytes):
    """
    Devuelve lista de 256 (r,g,b) si hay paleta embebida; si no, None.
    """
    if not pcx_has_palette(raw_bytes):
        return None
    pal = []
    base = len(raw_bytes) - 768
    for i in range(256):
        off = base + i*3
        r = ord(raw_bytes[off+0])
        g = ord(raw_bytes[off+1])
        b = ord(raw_bytes[off+2])
        pal.append((r,g,b))
    return pal

def load_act_palette(path):
    if not os.path.exists(path):
        print("No existe .ACT:", path); return None
    data = read_file(path)
    if len(data) < 768:
        print("ACT demasiado corto:", len(data)); return None
    pal = []
    for i in range(256):
        base = i*3
        if base+2 < len(data):
            r = ord(data[base+0]); g = ord(data[base+1]); b = ord(data[base+2])
            pal.append((r,g,b))
        else:
            pal.append((0,0,0))
    return pal

def dump_palette_txt(pal, path_txt):
    """
    Escribe un txt con líneas: idx  R G B  #RRGGBB
    """
    f = open(path_txt, "w")
    try:
        for i,(r,g,b) in enumerate(pal):
            f.write("%3d  %3d %3d %3d  #%02X%02X%02X\n" % (i,r,g,b,r,g,b))
    finally:
        f.close()

def save_palette_swatch_png(pal, out_png, cell=16, cols=16):
    """
    Crea una imagen 16x16 celdas con los 256 colores de la paleta.
    Requiere PIL.
    """
    if Image is None:
        return False
    rows = (len(pal)+cols-1)//cols
    w, h = cols*cell, rows*cell
    img = Image.new("RGB", (w,h), (32,32,32))
    for i,(r,g,b) in enumerate(pal):
        x = (i % cols)*cell
        y = (i // cols)*cell
        for yy in range(y, y+cell):
            for xx in range(x, x+cell):
                img.putpixel((xx,yy), (r,g,b))
    img.save(out_png)
    return True

def rgb_dist2(a, b):
    dr = a[0]-b[0]; dg = a[1]-b[1]; db = a[2]-b[2]
    return dr*dr + dg*dg + db*db

def compare_palettes(pcx_pal, act_pal, top=10):
    """
    Compara paletas índice por índice.
    - Para cada índice i en paleta PCX, busca el color más cercano en ACT.
    - Reporta distancias, mismatches y algunos casos peores.
    """
    if pcx_pal is None or act_pal is None:
        return None
    pairs = []
    total_d = 0
    worst = []
    for i,src in enumerate(pcx_pal):
        best_k = 0; best_d = 1<<30
        for k,tgt in enumerate(act_pal):
            d = rgb_dist2(src, tgt)
            if d < best_d:
                best_d = d; best_k = k
                if d == 0: break
        pairs.append((i, best_k, best_d))
        total_d += best_d
        worst.append((best_d, i, best_k, src, act_pal[best_k]))
    worst.sort(reverse=True)
    # Métricas
    avg = float(total_d)/256.0
    exact = sum(1 for (i,k,d) in pairs if d == 0)
    return dict(
        avg_dist2 = avg,
        exact_matches = exact,
        worst = worst[:top],  # lista de (dist2, idx_src, idx_act, rgb_src, rgb_act)
        pairs = pairs
    )

def pil_index_histogram(pcx_path):
    """
    Abre el PCX con PIL y retorna histograma de índices (0..255) si es 'P'.
    También devuelve color del borde (esquina sup-izq) para intentar detectar fondo.
    """
    if Image is None:
        return None, None
    try:
        im = Image.open(pcx_path)
        im.load()
        if im.mode != "P":
            im = im.convert("P")
        data = list(im.getdata())
        hist = [0]*256
        for p in data:
            hist[p] += 1
        w,h = im.size
        corner_idx = im.getpixel((0,0))
        return hist, corner_idx
    except Exception as e:
        print("PIL no pudo abrir PCX:", e)
        return None, None

def guess_transparent_index(hist, corner_idx):
    """
    Heurística simple:
      - si el índice 0 es enorme y/o coincide con el borde, sugiera 0;
      - si no, sugiere el índice del borde si es dominante;
      - si no, el más frecuente.
    """
    if hist is None:
        return 0
    total = sum(hist) or 1
    top_idx = max(range(256), key=lambda x: hist[x])
    # borde dominante?
    if corner_idx is not None and hist[corner_idx] > total*0.05:
        return corner_idx
    # índice 0 muy dominante?
    if hist[0] > total*0.10:
        return 0
    return top_idx

def main():
    if len(sys.argv) < 2:
        print("Uso: python pcx_act_probe.py sprite.pcx [paleta.act]")
        return 1

    pcx_path = sys.argv[1]
    act_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(pcx_path):
        print("No existe PCX:", pcx_path); return 2

    raw = read_file(pcx_path)
    has_pal = pcx_has_palette(raw)
    pcx_pal = pcx_read_embedded_palette(raw)

    print("== PCX ==")
    print("Ruta:", pcx_path)
    print("Tamaño:", len(raw), "bytes")
    print("¿Paleta embebida real?:", "SI" if has_pal else "NO")
    if has_pal and pcx_pal:
        dump_palette_txt(pcx_pal, "pcx_palette.txt")
        if save_palette_swatch_png(pcx_pal, "pcx_palette.png"):
            print("Guardé pcx_palette.txt y pcx_palette.png")
        else:
            print("Guardé pcx_palette.txt (sin PIL para PNG)")

    act_pal = None
    if act_path:
        if not os.path.exists(act_path):
            print("No existe ACT:", act_path)
        else:
            act_pal = load_act_palette(act_path)
            if act_pal:
                dump_palette_txt(act_pal, "act_palette.txt")
                if save_palette_swatch_png(act_pal, "act_palette.png"):
                    print("Guardé act_palette.txt y act_palette.png")
                else:
                    print("Guardé act_palette.txt (sin PIL para PNG)")

    # Histograma de índices del PCX
    hist, corner_idx = pil_index_histogram(pcx_path)
    if hist is not None:
        total = sum(hist) or 1
        top = sorted([(hist[i], i) for i in range(256)], reverse=True)[:5]
        print("Top índices usados (conteo, índice):", top)
        print("Índice en esquina (0,0):", corner_idx)
        guess_t = guess_transparent_index(hist, corner_idx)
        print("Índice transparente (heurística):", guess_t)

    # Comparar PCX vs ACT
    if pcx_pal and act_pal:
        cmpres = compare_palettes(pcx_pal, act_pal, top=12)
        if cmpres:
            print("== Comparación paletas (PCX vs ACT) ==")
            print("Coincidencias exactas:", cmpres["exact_matches"], "/ 256")
            print("Dist² promedio:", int(cmpres["avg_dist2"]))
            print("Peores 12 (dist², idxPCX -> idxACT, RGBsrc -> RGBact):")
            for d2, i_src, i_act, rgb_src, rgb_act in cmpres["worst"]:
                print("  %5d  %3d -> %3d   (%3d,%3d,%3d) -> (%3d,%3d,%3d)" %
                      (d2, i_src, i_act,
                       rgb_src[0],rgb_src[1],rgb_src[2],
                       rgb_act[0],rgb_act[1],rgb_act[2]))
        else:
            print("No se pudo comparar.")

    print("\nListo. Revisa los TXT/PNG generados en esta carpeta.")
    print("Si ves gran divergencia o muchos 0,0,0, el ACT no corresponde o estás remapeando desde paleta equivocada.")

    return 0

if __name__ == "__main__":
    sys.exit(main())

