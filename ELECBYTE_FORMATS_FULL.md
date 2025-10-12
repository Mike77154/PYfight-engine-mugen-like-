# 📘 Elecbyte File Formats — SFF, SFFv2, SND, FNT

Este documento describe con precisión byte a byte las estructuras internas de los formatos usados por **M.U.G.E.N.**, desarrollados por **Elecbyte**.  
Incluye los formatos **SFF v1.01**, **SFF v2**, **SND**, y **FNT**.

---

## 🧩 SFF v1.01 — Sprite File Format (Clásico)

### 📄 Header (512 bytes)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–11 | 12 | Firma `"ElecbyteSpr\0"` |
| 12–15 | 4 | Versión: 1 verhi, 1 verlo, 1 verlo2, 1 verlo3 |
| 16–19 | 4 | Número de grupos |
| 20–23 | 4 | Número de imágenes |
| 24–27 | 4 | Offset del primer subarchivo |
| 28–31 | 4 | Tamaño del subheader en bytes |
| 32 | 1 | Tipo de paleta (1 = compartida, 0 = individual) |
| 33–35 | 3 | Relleno en cero |
| 36–511 | 476 | Espacio libre o comentarios |

---

### 🧱 Subfile Header (32 bytes)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–03 | 4 | Offset del siguiente subarchivo (0 si es el último) |
| 04–07 | 4 | Longitud del subarchivo (sin incluir header) |
| 08–09 | 2 | Coordenada X del eje de imagen |
| 10–11 | 2 | Coordenada Y del eje de imagen |
| 12–13 | 2 | Número de grupo |
| 14–15 | 2 | Número de imagen dentro del grupo |
| 16–17 | 2 | Índice del sprite previo (solo si está vinculado) |
| 18 | 1 | True si la paleta es igual a la del sprite previo |
| 19–31 | 13 | Espacio reservado |
| 32– | Variable | Datos PCX (últimos 768 bytes = paleta) |

---

## ⚙️ SFF v2 — Sprite File Format (Avanzado, 2009)

### 📄 Header (512 bytes)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–11 | 12 | Firma `"ElecbyteSpr"` |
| 12–15 | 4 | Versión (Lo3, Lo2, Lo1, Hi) |
| 16–25 | 10 | Reservado (cero) |
| 26–29 | 4 | Offset del Palette Map |
| 30–35 | 6 | Reservado |
| 36–39 | 4 | Offset de SpriteList |
| 40–43 | 4 | Número de sprites |
| 44–47 | 4 | Valor fijo 0x200 |
| 48–51 | 4 | Número de paletas |
| 52–55 | 4 | Offset del Palette Bank |
| 56–59 | 4 | OnDemand Data Size |
| 60–63 | 4 | OnDemand Total Size |
| 64–67 | 4 | OnLoad Data Size |
| 68–511 | 444 | Espacio reservado |

---

### 🧾 SpriteList Node Header (28 bytes)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–01 | 2 | Grupo |
| 02–03 | 2 | Número |
| 04–05 | 2 | Ancho |
| 06–07 | 2 | Alto |
| 08–09 | 2 | Xaxis |
| 0A–0B | 2 | Yaxis |
| 0C–0D | 2 | Índice vinculado |
| 0E | 1 | Método de compresión |
| 0F | 1 | Profundidad de color |
| 10–13 | 4 | Offset de datos |
| 14–17 | 4 | Longitud de datos |
| 18–19 | 2 | Número de paleta |
| 1A–1B | 2 | Modo de carga |

**Métodos de compresión:**  
- `0x00` — Ninguno  
- `0x02` — RLE8  
- `0x03` — RLE5  
- `0x04` — LZ5  

**Modos de carga:**  
- `0x00` — OnDemand  
- `0x01` — OnLoad  

---

### 🧮 Palette Map (16 bytes por paleta)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–01 | 2 | Grupo |
| 02–03 | 2 | Número |
| 04–07 | 4 | Total de colores |
| 08–11 | 4 | Offset a los datos |
| 12–15 | 4 | Longitud de la paleta |

> Para calcular direcciones efectivas:
> - **OnDemand:** (PaletteBank Offset + Offset a datos)  
> - **OnLoad:** (SpriteData Section Start + Offset a datos)

---

## 🔊 SND — Sound File Format

### 📄 Header (512 bytes)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–11 | 12 | Firma `"ElecbyteSnd\0"` |
| 12–15 | 4 | Versión (verhi, verlo) |
| 16–19 | 4 | Número de sonidos |
| 20–23 | 4 | Offset al primer subarchivo |
| 24–511 | 488 | Espacio libre o comentarios |

---

### 🔉 Subfile Header (16 bytes + datos)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–03 | 4 | Offset al siguiente subarchivo |
| 04–07 | 4 | Longitud del subarchivo (sin header) |
| 08–11 | 4 | Grupo |
| 12–15 | 4 | Número de muestra |
| 16– | Variable | Datos WAV crudos (PCM o ADPCM) |

---

## 🔤 FNT — Font File Format

### 📄 Header (64 bytes)

| Offset | Tamaño | Descripción |
|---------|---------|-------------|
| 00–11 | 12 | Firma `"ElecbyteFnt\0"` |
| 12–15 | 4 | Versión (verhi, verlo) |
| 16–19 | 4 | Offset de datos PCX |
| 20–23 | 4 | Longitud de datos PCX |
| 24–27 | 4 | Offset de datos de texto |
| 28–31 | 4 | Longitud de datos de texto |
| 32–63 | 32 | Espacio libre o comentarios |

---

### 🖼️ Estructura

1. **Header (64 bytes)**
2. **PCX (glifos de fuente)**
3. **Texto ASCII (mapa de caracteres y espaciado)**

> Los datos del texto pueden ser optimizados eliminando comentarios antes de concatenarse.

---

## 🧠 Créditos

Basado en documentación de:
- Elecbyte (2000–2009)
- Romhack’s SFFv2 notes (2009)
- Comunidad M.U.G.E.N. Open Dev

---

**© 2025 — Documento técnico adaptado por Miguel (Mike77154)**  
Licencia: MIT / CC0  
