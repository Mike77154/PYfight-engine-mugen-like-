# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
"""
air_parser.py — lector/Parser de archivos .AIR de M.U.G.E.N (Python 2.7)
- Aplica Clsn1:/Clsn2: (one-shot) al PRIMER frame posterior al bloque.
- Clsn1Default:/Clsn2Default: quedan en animation.defaults.
- Limpia pendings al iniciar cada [Begin Action].
"""

import re, os, sys

# --------------------------------------------------------------------------
class HitBox(object):
    __slots__ = ('kind','x1','y1','x2','y2')
    def __init__(self, kind, x1,y1,x2,y2):
        self.kind = int(kind)
        self.x1,self.y1,self.x2,self.y2 = int(x1),int(y1),int(x2),int(y2)
    def __repr__(self):
        return u"HitBox(%d,%d,%d,%d,%d)" % (self.kind,self.x1,self.y1,self.x2,self.y2)

class CollisionSet(object):
    __slots__=('clsn1','clsn2')
    def __init__(self,clsn1=None,clsn2=None):
        self.clsn1=list(clsn1) if clsn1 else []
        self.clsn2=list(clsn2) if clsn2 else []
    def copy(self):
        return CollisionSet(self.clsn1[:],self.clsn2[:])
    def __repr__(self):
        return u"CollisionSet(clsn1=%d,clsn2=%d)"%(len(self.clsn1),len(self.clsn2))

class AnimFrame(object):
    __slots__=('group','image','xoff','yoff','time','flip','trans','boxes','tags')
    def __init__(self,g,i,xo,yo,t,flip='',trans='',boxes=None,tags=None):
        self.group=int(g);self.image=int(i)
        self.xoff=int(xo);self.yoff=int(yo)
        self.time=int(t)
        self.flip=(flip or '').upper()
        self.trans=(trans or '').upper()
        self.boxes=boxes if boxes else CollisionSet()
        self.tags=list(tags) if tags else []
    def __repr__(self):
        return u"AnimFrame(g=%d,i=%d,off=(%d,%d),t=%d,flip=%s,trans=%s)"%(
            self.group,self.image,self.xoff,self.yoff,self.time,self.flip,self.trans)

class Animation(object):
    __slots__=('number','frames','loopstart_idx','defaults')
    def __init__(self,n,frames=None,loopstart_idx=None,defaults=None):
        self.number=int(n)
        self.frames=list(frames) if frames else []
        self.loopstart_idx=loopstart_idx
        self.defaults=defaults if defaults else CollisionSet()
    def frame_count(self): return len(self.frames)
    def resolve_boxes_for(self,idx):
        f=self.frames[idx]
        if not f.boxes.clsn1 and not f.boxes.clsn2: return self.defaults.copy()
        return f.boxes
    def total_ticks(self):
        return sum([f.time for f in self.frames if f.time>0])
    def __repr__(self):
        return u"Animation(%d,frames=%d,loop=%r)"%(self.number,len(self.frames),self.loopstart_idx)

class AirFile(object):
    def __init__(self):
        self.actions={};self.warnings=[]
    def __repr__(self):
        return u"AirFile(actions=%d,warnings=%d)"%(len(self.actions),len(self.warnings))

# --------------------------------------------------------------------------
# >>>>>>>>> NUEVO: opción para invertir Y de cajas al parsear <<<<<<<<<
# Activa/desactiva inversión vertical por defecto de TODAS las cajas
# (defaults y one-shot) en el momento del parseo.
DEFAULT_BOX_VFLIP = True  # <- cambia a False si no quieres invertir

def _invert_y_list(lst):
    """Invierte y1/y2 in-place en una lista de HitBox (si existe)."""
    if not lst: return
    for b in lst:
        b.y1, b.y2 = -b.y1, -b.y2
# --------------------------------------------------------------------------

def ticks_to_ms(t): return -1 if t<0 else int(round(1000.0*(t/60.0)))
def iter_actions(a):
    for k in sorted(a.actions.keys()): yield a.actions[k]
def iter_frames(an):
    for i,f in enumerate(an.frames): yield i,f

HEADER_RE=re.compile(r'^\s*\[Begin\s+Action\s+(-?\d+)\]\s*$',re.I)
LOOPSTART_RE=re.compile(r'^\s*Loopstart\s*$',re.I)
CLSN_DEF_RE=re.compile(r'^\s*Clsn([12])Default\s*:\s*(\d+)\s*$',re.I)
CLSN_ONESHOT_RE=re.compile(r'^\s*Clsn([12])\s*:\s*(\d+)\s*$',re.I)
CLSN_BOX_RE=re.compile(r'^\s*Clsn([12])\s*\[\s*(\d+)\s*\]\s*=\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*$',re.I)

def _parse_element_fields(line):
    p=[x.strip() for x in line.split(',')]
    if len(p)<5: return None
    g,i,xo,yo,t=p[:5]
    flip=p[5] if len(p)>=6 and p[5] else ''
    trans=p[6] if len(p)>=7 and p[6] else ''
    return g,i,xo,yo,t,flip,trans

def _strip_comment(l):
    s=l.find(';')
    return l[:s] if s>=0 else l

class _FillState(object):
    __slots__=('kind','remaining','is_default','target')
    def __init__(self,k,c,isdef):
        self.kind=int(k);self.remaining=int(c)
        self.is_default=bool(isdef);self.target=[]

def parse_air(path,encoding='utf-8'):
    if not os.path.exists(path): raise IOError("No existe: %s"%path)
    af=AirFile();cur=None;fill=None
    # Pendientes para aplicar al PRÓXIMO frame leído
    pending1=None; pending2=None

    def warn(n,msg):
        af.warnings.append(u"L%d: %s"%(n,unicode(msg)))

    with open(path,'rb') as f:
        for n,raw in enumerate(f,1):
            try: line=raw.decode(encoding,'replace')
            except: line=raw.decode('utf-8','replace')
            base=_strip_comment(line).strip()
            if not base: continue

            # Nueva sección
            m=HEADER_RE.match(base)
            if m:
                num=int(m.group(1))
                cur=Animation(num)
                af.actions[num]=cur
                fill=None
                # Limpiar pendientes al cambiar de sección
                pending1=None; pending2=None
                continue

            if cur is None:
                warn(n,u"Línea fuera de sección [Begin Action]: '%s'"%base[:60]);continue

            # loopstart
            if LOOPSTART_RE.match(base):
                cur.loopstart_idx=len(cur.frames);continue

            # Clsn defaults
            m=CLSN_DEF_RE.match(base)
            if m:
                fill=_FillState(m.group(1),m.group(2),True)
                continue

            # Clsn one-shot (para el siguiente frame)
            m=CLSN_ONESHOT_RE.match(base)
            if m:
                fill=_FillState(m.group(1),m.group(2),False)
                continue

            # Líneas de cajas
            m=CLSN_BOX_RE.match(base)
            if m:
                if not fill:
                    warn(n,u"Clsn box sin conteo previo"); continue
                k=int(m.group(1))
                x1,y1,x2,y2=m.group(3),m.group(4),m.group(5),m.group(6)
                fill.target.append(HitBox(k,x1,y1,x2,y2))
                fill.remaining-=1
                if fill.remaining<0:
                    warn(n,u"Más Clsn boxes que las declaradas")
                if fill.remaining<=0:
                    # Finaliza bloque
                    if fill.is_default:
                        # Default → a defaults de la animación
                        if DEFAULT_BOX_VFLIP:
                            _invert_y_list(fill.target)
                        if k==1: cur.defaults.clsn1=list(fill.target)
                        else:    cur.defaults.clsn2=list(fill.target)
                    else:
                        # One-shot → queda pendiente para el PRIMER frame posterior
                        if DEFAULT_BOX_VFLIP:
                            _invert_y_list(fill.target)
                        if fill.kind==1: pending1=list(fill.target)
                        else:            pending2=list(fill.target)
                    fill=None
                continue

            # Línea de frame (g,i,x,y,t[,flip,trans])
            elem=_parse_element_fields(base)
            if elem:
                g,i,xo,yo,t,flip,trans=elem
                try:
                    fr=AnimFrame(g,i,xo,yo,t,flip or '',trans or '')
                except Exception as e:
                    warn(n,u"Campos inválidos: %s"%unicode(e)); continue

                # Si hay cajas pendientes (one-shot), aplicarlas y limpiar
                if pending1 or pending2:
                    fr.boxes = CollisionSet(pending1 or [], pending2 or [])
                    pending1=None; pending2=None

                cur.frames.append(fr)
                continue

            # Nada calzó
            warn(n,u"Línea no reconocida: '%s'"%base[:120])

    return af

# --------------------------------------------------------------------------
if __name__=='__main__':
    if len(sys.argv)<2:
        print("Uso: python air_parser.py <archivo.air> [encoding]");sys.exit(1)
    path=sys.argv[1];enc=sys.argv[2] if len(sys.argv)>2 else 'utf-8'
    air=parse_air(path,encoding=enc)
    print("== AIR cargado ==")
    print("Acciones:",len(air.actions))
    print("Warnings:",len(air.warnings))
    if air.warnings:
        for w in air.warnings[:20]:
            try: print("  -",w)
            except UnicodeEncodeError:
                sys.stdout.write((u"  - "+w+u"\n").encode('utf-8'))
        if len(air.warnings)>20:
            print("  ... (%d más)"%(len(air.warnings)-20))
    for num in sorted(air.actions.keys())[:5]:
        a=air.actions[num]
        print("[Action %d] frames=%d loopstart=%r defaults: c1=%d c2=%d ticks=%d"%(
            a.number,a.frame_count(),a.loopstart_idx,
            len(a.defaults.clsn1),len(a.defaults.clsn2),a.total_ticks()))
