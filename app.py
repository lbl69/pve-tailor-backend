"""
PVE TAILOR — Backend Flask
  POST /api/pdf    → génère le PDF et retourne en base64
  GET  /api/metar  → proxy METAR/TAF aviationweather.gov
  GET  /health     → healthcheck
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, io, base64, traceback

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white

app = Flask(__name__)
CORS(app)  # autorise toutes les origines

# ── Dimensions A4 paysage ──
PAGE = landscape(A4)   # 841.89 x 595.28 pts
PW, PH = PAGE          # largeur=841, hauteur=595

def mm(v): return v * 2.8346

# ════════════════════════════════════════════════════════════════
# Couleurs
# ════════════════════════════════════════════════════════════════
BLACK   = black
WHITE   = white
FILLED  = HexColor('#0055CC')   # bleu — champs remplis
LGRAY   = HexColor('#AAAAAA')
MGRAY   = HexColor('#777777')
DGRAY   = HexColor('#333333')
BGRAY   = HexColor('#F2F2F2')
BGRAY2  = HexColor('#E5E5E5')
LINE    = HexColor('#CCCCCC')

# ════════════════════════════════════════════════════════════════
# Primitives de dessin
# ════════════════════════════════════════════════════════════════
def filled(val):
    return str(val).strip() not in ('', '0', 'None', 'null', 'undefined')

def _box(c, x, y, w, h, fill=None, stroke=LINE, lw=0.3):
    c.setLineWidth(lw)
    if fill:
        c.setFillColor(fill); c.setStrokeColor(stroke)
        c.rect(mm(x), PH-mm(y)-mm(h), mm(w), mm(h), fill=1, stroke=1)
    else:
        c.setStrokeColor(stroke)
        c.rect(mm(x), PH-mm(y)-mm(h), mm(w), mm(h), fill=0, stroke=1)

def _txt(c, text, x, y, size=6.5, bold=False, color=DGRAY, align='left', blue_if_filled=False):
    s = str(text).strip()
    if not s: return
    col = FILLED if (blue_if_filled and filled(s)) else color
    c.setFillColor(col)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    px, py = mm(x), PH-mm(y)
    if align == 'center': c.drawCentredString(px, py, s)
    elif align == 'right': c.drawRightString(px, py, s)
    else: c.drawString(px, py, s)

def _hline(c, x1, y, x2, col=LINE, lw=0.3):
    c.setStrokeColor(col); c.setLineWidth(lw)
    c.line(mm(x1), PH-mm(y), mm(x2), PH-mm(y))

def _vline(c, x, y1, y2, col=LINE, lw=0.3):
    c.setStrokeColor(col); c.setLineWidth(lw)
    c.line(mm(x), PH-mm(y1), mm(x), PH-mm(y2))

# ════════════════════════════════════════════════════════════════
# GÉNÉRATION PDF — A4 PAYSAGE
# Layout : page 297mm × 210mm (paysage)
#
#  ┌─────────────────────────────────────────────────────────────┐
#  │  HEADER (titre + route)                          [5..292]  │
#  ├──────────────────┬──────────────┬───────────────────────────┤
#  │  COL GAUCHE      │  COL CENTRE  │  COL DROITE               │
#  │  [5..100]        │  [102..195]  │  [197..292]               │
#  │  Crew/DOW/Fuel   │  Route/WP    │  Surete/Corr/Times/EZFW   │
#  ├──────────────────┴──────────────┴───────────────────────────┤
#  │  ALTERNATES + METEO + NOTES                                 │
#  └─────────────────────────────────────────────────────────────┘
# ════════════════════════════════════════════════════════════════
def build_pdf(data):
    f    = data
    fuel = f.get('fuel', {})
    crew = f.get('crew', {})
    corr = f.get('corr', {})
    ez   = f.get('ezfw', {})
    dep  = f.get('dep', '')
    arr  = f.get('arr', '')

    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=PAGE)

    def box(x,y,w,h,fill=None,stroke=LINE,lw=0.3): _box(c,x,y,w,h,fill,stroke,lw)
    def txt(text,x,y,**kw): _txt(c,text,x,y,**kw)
    def hline(x1,y,x2,col=LINE,lw=0.3): _hline(c,x1,y,x2,col,lw)
    def vline(x,y1,y2,col=LINE,lw=0.3): _vline(c,x,y1,y2,col,lw)

    # ── Largeurs colonnes (en mm, page 297mm large) ──
    LM = 5      # left margin
    COL1_X = LM;       COL1_W = 93   # Fuel / Crew / DOW
    COL2_X = 100;      COL2_W = 97   # Route / waypoints
    COL3_X = 199;      COL3_W = 93   # Sûreté / Corr / Times / EZFW
    RM = 292            # right edge

    # ════════════════════════════════════
    # HEADER
    # ════════════════════════════════════
    box(LM, 4, RM-LM, 8, fill=BLACK, stroke=BLACK)
    txt('PVE "TAILOR"',    7,  10, size=10, bold=True,  color=WHITE)
    txt('VER 4.0',        52,  10, size=7,  color=HexColor('#AAAAAA'))
    txt('TWINJET',        80,  10, size=9,  bold=True,  color=WHITE)
    txt('iNTAIRLINE',    120,  10, size=8,  color=HexColor('#BBBBBB'))
    txt('AIR QUALIFICATIONS', 158, 10, size=7, color=HexColor('#BBBBBB'))
    txt(f.get('vol_nums',''), 260, 10, size=8, bold=True, color=WHITE)

    box(LM, 12, RM-LM, 4.5, fill=BGRAY, stroke=LINE)
    txt('Craft Data Source: MANEX TJT B4  ·  B1900D PVE1 (V3.8)  ·  Nav Data Source: EURO FPL',
        7, 15.5, size=5.5, color=MGRAY)

    box(LM, 16.5, RM-LM, 6, fill=BLACK, stroke=BLACK)
    txt(f"{dep} ⟹ {arr}  ({f.get('duration','')})", 7, 21.5, size=9, bold=True, color=WHITE)
    txt(f"{f.get('fl','')}  ROUTING: {f.get('route','')[:100]}", 62, 21.5, size=5.5, color=HexColor('#AACCFF'))

    # DEP / ARR
    box(LM,  22.5, 55, 9, fill=BGRAY, stroke=LINE)
    txt(dep, 7, 27.5, size=9, bold=True)
    txt(f"ETD : {f.get('etds','')}", 7, 30.5, size=6)
    txt(f.get('freq_dep',''), 35, 27.5, size=5, color=MGRAY)

    box(62, 22.5, 55, 9, fill=BGRAY, stroke=LINE)
    txt(arr, 64, 27.5, size=9, bold=True)
    txt(f"ETA : {f.get('etas','')}", 64, 30.5, size=6)
    txt(f.get('freq_arr',''), 90, 27.5, size=5, color=MGRAY)

    Y_BODY = 32   # début du corps

    # ════════════════════════════════════
    # COLONNE GAUCHE — CREW + DOW + FUEL
    # ════════════════════════════════════

    # N° étape
    box(COL1_X, Y_BODY, COL1_W, 5, fill=BGRAY, stroke=LINE)
    txt("N° étape :", COL1_X+2, Y_BODY+3.5, size=5.5, color=MGRAY)
    txt(f.get('num_etape',''), COL1_X+22, Y_BODY+3.5, size=6, blue_if_filled=True)

    # CREW
    box(COL1_X, Y_BODY+5, COL1_W, 17, fill=BGRAY, stroke=LINE)
    txt('CREW',   COL1_X+2, Y_BODY+9, size=6.5, bold=True)
    txt('Trigram',COL1_X+28,Y_BODY+9, size=5, color=MGRAY)
    txt('PF/PM',  COL1_X+55,Y_BODY+9, size=5, color=MGRAY)
    hline(COL1_X, Y_BODY+10, COL1_X+COL1_W)
    for i,(role,tri,pf) in enumerate([
        ('CDB', crew.get('cdb_tri',''), crew.get('cdb_pf','')),
        ('OPL', crew.get('opl_tri',''), crew.get('opl_pf','')),
        ('PCB', crew.get('pcb_quad',''), ''),
    ]):
        y = Y_BODY+14+i*4
        txt(role, COL1_X+2, y, size=6.5, bold=True)
        txt(tri,  COL1_X+28, y, size=7, bold=True, color=FILLED if filled(tri) else LGRAY)
        if pf: txt(pf, COL1_X+55, y, size=6.5, color=FILLED)
        if i<2: hline(COL1_X, y+1.5, COL1_X+COL1_W)

    # DOW/DOI
    box(COL1_X, Y_BODY+22, COL1_W, 6, fill=BGRAY2, stroke=LINE)
    txt('DOW/DOI/cf', COL1_X+2, Y_BODY+26, size=6.5, bold=True)
    txt(f.get('avion',''),   COL1_X+28, Y_BODY+26, size=6.5, blue_if_filled=True)
    txt(f"v.{f.get('version','')}", COL1_X+58, Y_BODY+26, size=6, color=FILLED if filled(f.get('version','')) else LGRAY)
    txt(f"DOW:{f.get('dow','')} lbs", COL1_X+2, Y_BODY+30, size=5.8, bold=True, color=FILLED if filled(f.get('dow','')) else LGRAY)
    txt(f"DOI:{f.get('doi','')}", COL1_X+50, Y_BODY+30, size=5.8, bold=True, color=FILLED if filled(f.get('doi','')) else LGRAY)

    # FUEL CALC
    box(COL1_X, Y_BODY+28, COL1_W, 4, fill=BLACK, stroke=BLACK)
    txt('Fuel Calculation', COL1_X+2, Y_BODY+31, size=6.5, bold=True, color=WHITE)
    txt('Time',     COL1_X+66, Y_BODY+31, size=5, color=HexColor('#AAAAAA'), align='center')
    txt('Fuel (lbs)', COL1_X+91, Y_BODY+31, size=5, color=HexColor('#AAAAAA'), align='right')

    FUEL_ROWS = [
        ('Climb+T/O',         fuel.get('t_climb',''),  fuel.get('f_climb','')),
        ('Cruise',            fuel.get('t_cruise',''), fuel.get('f_cruise','')),
        ('Descent',           fuel.get('t_desc',''),   fuel.get('f_desc','')),
        ('Approach',          '00:12',                  '150'),
        ('Total',             '',                       fuel.get('f_total','')),
        ('+ Correction',      '',                       fuel.get('f_corr','')),
        ('= Trip Fuel',       fuel.get('t_trip',''),    fuel.get('f_trip','')),
        ('RR (5% > 60 lbs)',  '',                       fuel.get('f_rr','')),
        ('ALtn Fuel',         fuel.get('t_altn',''),    fuel.get('f_altn','')),
        ('Final reserve',     '00:30',                  '380'),
        ('Taxi (110 lbs min)','',                       fuel.get('f_taxi','110')),
        ('Extra / add Fuel',  '',                       fuel.get('f_extra','')),
        ('CDB Fuel',          '',                       fuel.get('f_cdb','')),
        ('Required Fuel',     '',                       fuel.get('f_required','')),
        ('Block Fuel',        '',                       fuel.get('f_block','')),
    ]
    FIXED = {'Approach','Final reserve'}
    BOLD_F= {'= Trip Fuel','Required Fuel','Block Fuel'}

    for i,(label,t,fv) in enumerate(FUEL_ROWS):
        y = Y_BODY+32+i*4.95
        ib = label in BOLD_F
        if label in ('Required Fuel','Block Fuel'):
            box(COL1_X, y-1.2, COL1_W, 5, fill=BGRAY2, stroke=LINE)
        txt(label, COL1_X+2, y+2.5, size=5.6, bold=ib)
        is_fixed = label in FIXED
        if t:
            txt(t, COL1_X+67, y+2.5, size=5.6, align='center',
                color=DGRAY if is_fixed else (FILLED if filled(t) else LGRAY))
        if fv:
            txt(fv, COL1_X+92, y+2.5, size=5.8, bold=ib, align='right',
                color=DGRAY if is_fixed else (FILLED if filled(fv) else LGRAY))
        if i<len(FUEL_ROWS)-1:
            hline(COL1_X, y+3.8, COL1_X+COL1_W, HexColor('#DDDDDD'))

    Y_AFTER_FUEL = Y_BODY+32+len(FUEL_ROWS)*4.95

    # ════════════════════════════════════
    # COLONNE CENTRE — ROUTE / WAYPOINTS
    # ════════════════════════════════════

    # Route texte
    box(COL2_X, Y_BODY, COL2_W, 5, fill=BGRAY, stroke=LINE)
    txt('Route :', COL2_X+2, Y_BODY+3.5, size=5.5, color=MGRAY)
    txt(f.get('route','')[:70], COL2_X+16, Y_BODY+3.5, size=5.5, color=DGRAY)

    # Waypoints table
    WP_COLS = [
        ('POINT/ROUTE', COL2_X,    28),
        ("ALT'",        COL2_X+28, 11),
        ('DRM°',        COL2_X+39,  9),
        ('DIST',        COL2_X+48,  9),
        ("Tsv'",        COL2_X+57,  8),
        ('HE',          COL2_X+65,  9),
        ('Fuel',        COL2_X+74,  9),
        ('F. Est',      COL2_X+83,  8),
        ('Réel',        COL2_X+91,  8),  # finit à +99 = 199 ✓
    ]

    yWP = Y_BODY+5
    box(COL2_X, yWP, COL2_W, 5.5, fill=BLACK, stroke=BLACK)
    for name, cx, cw in WP_COLS:
        txt(name, cx+cw/2, yWP+4, size=4.5, bold=True, color=WHITE, align='center')
        vline(cx, yWP, yWP+5.5, WHITE, 0.2)

    waypoints = f.get('waypoints', [])
    for i, wp in enumerate(waypoints):
        y = yWP+5.5+i*5.2
        row_bg = BGRAY if i%2==0 else WHITE
        box(COL2_X, y, COL2_W, 5.2, fill=row_bg, stroke=LINE)
        for _, cx, cw in WP_COLS[1:]:
            vline(cx, y, y+5.2, LINE, 0.2)

        n = wp['n']
        is_end  = (i==0 or i==len(waypoints)-1)
        is_tctd = n in ('TOC','TOD')
        nc = (HexColor('#003388') if is_end else
              HexColor('#775500') if is_tctd else DGRAY)

        txt(n,                   WP_COLS[0][1]+1,          y+3.8, size=7, bold=is_end or is_tctd, color=nc)
        txt(wp.get('alt',''),    WP_COLS[1][1]+WP_COLS[1][2]-1, y+3.8, size=5.5, color=MGRAY,  align='right')
        txt(wp.get('drm',''),    WP_COLS[2][1]+WP_COLS[2][2]/2, y+3.8, size=6,   color=DGRAY,  align='center')
        txt(wp.get('dist',''),   WP_COLS[3][1]+WP_COLS[3][2]/2, y+3.8, size=6,   color=DGRAY,  align='center')
        txt(wp.get('tsv',''),    WP_COLS[4][1]+WP_COLS[4][2]/2, y+3.8, size=5.5, color=MGRAY,  align='center')
        if filled(wp.get('he','')): txt(wp['he'], WP_COLS[5][1]+WP_COLS[5][2]/2, y+3.8, size=5.5, color=FILLED, align='center')
        if filled(wp.get('f_est','')): txt(wp['f_est'], WP_COLS[7][1]+WP_COLS[7][2]/2, y+3.8, size=5.5, color=FILLED, align='center')

    # Totaux
    yTot = yWP+5.5+len(waypoints)*5.2
    box(COL2_X, yTot, COL2_W, 5.5, fill=BGRAY2, stroke=LINE)
    for _, cx, _ in WP_COLS[1:]: vline(cx, yTot, yTot+5.5, LINE, 0.2)
    txt('Totaux :', COL2_X+2, yTot+4, size=6, bold=True)
    if filled(fuel.get('t_trip','')): txt(fuel['t_trip'], WP_COLS[5][1]+WP_COLS[5][2]/2, yTot+4, size=6, bold=True, color=FILLED, align='center')
    if filled(fuel.get('f_trip','')): txt(fuel['f_trip'], WP_COLS[7][1]+WP_COLS[7][2]/2, yTot+4, size=6, bold=True, color=FILLED, align='center')

    # ════════════════════════════════════
    # COLONNE DROITE — SURETE + CORR + TIMES + EZFW
    # ════════════════════════════════════

    # SURETE
    box(COL3_X, Y_BODY, COL3_W, 40, fill=BGRAY, stroke=LINE)
    txt('SURETE:', COL3_X+2, Y_BODY+4, size=6.5, bold=True)
    hline(COL3_X, Y_BODY+5, COL3_X+COL3_W)

    surete_labels = ['Avion:', 'Date:', 'N° VOL:', 'Fouille', 'Heure LT:', 'CDB:', 'Signature:']
    surete_vals   = [f.get('avion',''), f.get('date',''), f.get('vol_nums',''),
                     '', f.get('heure_fouille',''), crew.get('cdb_tri',''), '']
    for i,(lbl,val) in enumerate(zip(surete_labels, surete_vals)):
        y = Y_BODY+9+i*4.5
        txt(lbl, COL3_X+2, y, size=5.5, color=MGRAY)
        if lbl == 'Fouille':
            fouille = f.get('fouille','')
            for j, opt in enumerate(['OUI','NON']):
                bx = COL3_X+28+j*18
                box(bx, y-3.2, 7, 4, fill=WHITE, stroke=MGRAY)
                if fouille==opt: txt('✓', bx+1.5, y-0.5, size=6.5, bold=True, color=FILLED)
                txt(opt, bx+8.5, y, size=5.5)
        else:
            txt(val, COL3_X+28, y, size=6, bold=filled(val),
                color=FILLED if filled(val) else LGRAY)
        if i<6: hline(COL3_X, y+1.5, COL3_X+COL3_W, HexColor('#DDDDDD'))

    # CORRECTION
    yC = Y_BODY+40
    box(COL3_X, yC, COL3_W, 5, fill=BLACK, stroke=BLACK)
    txt('GRANDEUR CORRECTION', COL3_X+2, yC+3.5, size=6.5, bold=True, color=WHITE)
    CORR_ROWS = [
        ('C/D de ref',     corr.get('cd','')),
        ('Vw: ±10 KTS',    f"±{corr.get('vw','')} %"),
        ('T: -10°C',       f"+{corr.get('t','')} %"),
        ('FL: -1000 fts',  f"+{corr.get('fl_up','')} %"),
        ('FL: +1000 fts',  f"-{corr.get('fl_dn','')} %"),
        ('M: -1000 LBS',   f"-{corr.get('m','')} %"),
    ]
    box(COL3_X, yC+5, COL3_W, len(CORR_ROWS)*5, fill=BGRAY, stroke=LINE)
    for i,(k,v) in enumerate(CORR_ROWS):
        y = yC+9+i*5
        txt(k, COL3_X+2, y, size=5.8)
        txt(v, COL3_X+COL3_W-2, y, size=5.8, bold=True, color=DGRAY, align='right')
        if i<len(CORR_ROWS)-1: hline(COL3_X, y+1.5, COL3_X+COL3_W, HexColor('#DDDDDD'))

    # TIMES
    yT = yC+5+len(CORR_ROWS)*5
    box(COL3_X, yT, COL3_W, 5, fill=BLACK, stroke=BLACK)
    txt('TIMES', COL3_X+2, yT+3.5, size=6.5, bold=True, color=WHITE)
    txt('BLOCK', COL3_X+38, yT+3.5, size=5, color=HexColor('#AAAAAA'), align='center')
    txt('FLIGHT', COL3_X+65, yT+3.5, size=5, color=HexColor('#AAAAAA'), align='center')

    box(COL3_X, yT+5, COL3_W, 17, fill=BGRAY, stroke=LINE)
    vline(COL3_X+22, yT+5, yT+22, LINE)
    vline(COL3_X+52, yT+5, yT+22, LINE)
    vline(COL3_X+77, yT+5, yT+22, LINE)
    for i, lbl in enumerate(['ARR','DEP','TPS']):
        y = yT+9+i*4.8
        txt(lbl, COL3_X+2, y, size=6, bold=True)
        hline(COL3_X+23, y+0.5, COL3_X+51, HexColor('#BBBBBB'))  # BLOCK
        hline(COL3_X+53, y+0.5, COL3_X+76, HexColor('#BBBBBB'))  # FLIGHT
        if i<2: hline(COL3_X, y+1.5, COL3_X+COL3_W, HexColor('#DDDDDD'))

    # EZFW
    yE = yT+22
    box(COL3_X, yE, COL3_W, 5, fill=HexColor('#1A3A5C'), stroke=HexColor('#1A3A5C'))
    txt('EZFW / MASSE ESTIMÉE', COL3_X+2, yE+3.5, size=6.5, bold=True, color=WHITE)

    box(COL3_X, yE+5, COL3_W, len(CORR_ROWS)*5+4, fill=HexColor('#EEF6FF'), stroke=HexColor('#99BBDD'))
    EZFW_ROWS = [
        (f"Hommes × {ez.get('h',0)}",          f"{ez.get('h_mass',0):,} lbs"),
        (f"Femmes × {ez.get('f',0)}",           f"{ez.get('f_mass',0):,} lbs"),
        (f"Enfants × {ez.get('e',0)}",          f"{ez.get('e_mass',0):,} lbs"),
        (f"Bagages × {ez.get('total_pax',0)}",  f"{ez.get('bag_mass',0):,} lbs"),
        ('Payload total',                        f"{ez.get('payload',0):,} lbs"),
        ('EZFW',                                 f"{ez.get('ezfw',0):,} lbs"),
    ]
    for i,(k,v) in enumerate(EZFW_ROWS):
        y = yE+9+i*5
        is_last = i==5
        if is_last:
            box(COL3_X, y-1.5, COL3_W, 5.5, fill=HexColor('#CCE8FF'), stroke=HexColor('#99BBDD'))
        txt(k, COL3_X+2, y, size=5.8, bold=is_last)
        txt(v, COL3_X+COL3_W-2, y, size=5.8, bold=is_last,
            color=FILLED if is_last else DGRAY, align='right')
        if i<5: hline(COL3_X, y+1.5, COL3_X+COL3_W, HexColor('#CCDDEE'))

    # ════════════════════════════════════
    # BAS DE PAGE — ALTERNATES + METEO + NOTES
    # ════════════════════════════════════
    # Détermine y de départ = max des 3 colonnes
    yBottom = max(
        Y_AFTER_FUEL,
        yWP+5.5+len(waypoints)*5.2+6,
        yE+5+len(CORR_ROWS)*5+4+2
    ) + 4

    # ALTERNATES
    txt('ALTERNATES (³)', LM+2, yBottom+3, size=6, bold=True, color=MGRAY)
    alts = f.get('alternates', [])
    for ia, a in enumerate(alts[:2]):
        xa = LM + ia*146
        ya = yBottom+4
        box(xa, ya, 144, 14, fill=BGRAY, stroke=LINE)
        box(xa, ya, 35, 6, fill=BGRAY2, stroke=LINE)
        txt(f"{a.get('from_alt','')} FL{a.get('alt','')}", xa+2, ya+4.5, size=6.5, bold=True)
        txt(f"via  {a.get('via','')}", xa+37, ya+4.5, size=5.5, color=MGRAY)
        txt(a.get('altn',''), xa+112, ya+4.5, size=7, bold=True, color=DGRAY)
        txt(f"DRM° {a.get('drm','')}  dist {a.get('dist','')} NM", xa+2, ya+11, size=5.5)
        txt(f"HE {a.get('he','')}  F.Est:{a.get('f','')}  FR:{a.get('fin','150')}  Total:{a.get('tot','')} lbs",
            xa+50, ya+11, size=5.8, bold=True, color=DGRAY)

    yAlt = yBottom+19

    # METEO
    metars = f.get('metars', {})
    if metars:
        box(LM, yAlt, RM-LM, 5, fill=BLACK, stroke=BLACK)
        txt('MÉTÉO', LM+2, yAlt+3.5, size=6.5, bold=True, color=WHITE)
        yM = yAlt+5
        items = list(metars.items())[:4]
        col_w = (RM-LM) / len(items)
        for ii, (icao, md) in enumerate(items):
            xM = LM + ii*col_w
            metar_str = str(md.get('metar',''))[:80]
            taf_str   = str(md.get('taf',''))[:80]
            h_box = 9 if not taf_str else 15
            box(xM, yM, col_w-0.5, h_box, fill=BGRAY, stroke=LINE)
            txt(icao, xM+2, yM+4.5, size=7, bold=True, color=HexColor('#003388'))
            txt(metar_str, xM+16, yM+4.5, size=5.5, color=FILLED if filled(metar_str) else MGRAY)
            if taf_str:
                txt('TAF', xM+2, yM+10, size=5, color=MGRAY)
                txt(taf_str, xM+12, yM+10, size=5, color=HexColor('#006633'))
        yAlt = yM + h_box + 2

    # NOTES
    notes = [
        'Croisière High Speed 1550 RPM à Masse Max en ISA',
        '(¹) Z SECU: Buffer ±10 Nm. Source Eurofpl / SRTM Topographic data',
        f"(²) {f.get('tod_note','TOD = 73 NM à 1500ft/min à VMO ou 248 KTS')}",
        '(³) Trajectoire ALTN la plus probable au vu des cartes',
        f"Contacts : {f.get('freq_dep','')}  /  {f.get('freq_arr','')}",
    ]
    for i, note in enumerate(notes):
        txt(note, LM+2, yAlt+i*3.5, size=5, color=MGRAY if i<4 else DGRAY)

    # FOOTER
    c.setFillColor(LGRAY); c.setFont('Helvetica', 5)
    c.drawCentredString(
        PW/2, mm(3.5),
        f"PVE généré le {f.get('generated','')}  |  {f.get('avion','')} ver.{f.get('version','')}  |  DOW: {f.get('dow','')} lbs  |  TAILOR v4"
    )

    c.save()
    output.seek(0)
    return base64.b64encode(output.read()).decode()


# ════════════════════════════════════════════════════════════════
# ROUTES FLASK
# ════════════════════════════════════════════════════════════════
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'pve-tailor-backend'})

@app.route('/api/pdf', methods=['POST'])
def api_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON body'}), 400
        b64 = build_pdf(data)
        return jsonify({'pdf': b64, 'status': 'ok'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/metar', methods=['GET'])
def api_metar():
    """Proxy METAR/TAF — contourne le CORS depuis le browser"""
    icao = request.args.get('icao', '').upper().strip()
    if len(icao) != 4:
        return jsonify({'error': 'ICAO invalide'}), 400
    try:
        BASE = 'https://aviationweather.gov/api/data'
        mr = requests.get(f"{BASE}/metar?ids={icao}&format=raw&hours=2", timeout=8)
        tr = requests.get(f"{BASE}/taf?ids={icao}&format=raw&hoursBeforeNow=4", timeout=8)
        metar = mr.text.strip() if mr.ok else ''
        taf   = tr.text.strip() if tr.ok else ''
        return jsonify({
            'icao':  icao,
            'metar': metar or 'Aucune observation disponible',
            'taf':   taf
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
