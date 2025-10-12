# Elecbyte File Formats

Este documento detalla la estructura de archivos usada por el motor **M.U.G.E.N.**,
específicamente los formatos `.SFF`, `.SND` y `.FNT`, tanto en su versión clásica como moderna.

```c
/*--| SFF file structure |--------------------------------------------------*  Version 1.01
HEADER (512 bytes)
...
\*--------------------------------------------------------------------------*/
```

Incluye además las especificaciones del **SFFv2 Header**, **SpriteList Node Header**, y **Palette Map**,
así como los métodos de compresión RLE8, RLE5 y LZ5.

También contiene la estructura de los archivos **SND** (ElecbyteSnd) y **FNT** (ElecbyteFnt),
ambos descritos en su formato binario original.

---

> Documento técnico basado en el formato original de Elecbyte (2000–2009).
> Adaptado para desarrolladores que deseen implementar parsers binarios compatibles con M.U.G.E.N.
