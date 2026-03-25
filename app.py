"""
PVE TAILOR — Backend Flask v9
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, traceback

"""
PVE TAILOR v9 — Layout corrigé, coordonnées vérifiées
Page 1 : PVE (4 colonnes, tout dans les bounds)
Page 2 : MÉTÉO (gauche) + EZFW (droite), sans chevauchement
"""
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white
from textwrap import wrap as tw
import io, base64

PW, PH = landscape(A4)  # 841.9 x 595.3 pts

BLACK=black; WHITE=white
DBLUE=HexColor('#0044BB'); BLUE=HexColor('#003399')
LGRAY=HexColor('#BBBBBB'); MGRAY=HexColor('#777777'); DGRAY=HexColor('#111111')
BG1=HexColor('#EEEEEE'); BG2=HexColor('#E0E0E0'); BG3=HexColor('#F5F5F5')
NAVY=HexColor('#1A3A5C'); LBLUE=HexColor('#CCE8FF')

def filled(v):
    return str(v).strip() not in ('','0','None','null','undefined')

def build_pdf(data):
    f=data; fuel=f.get('fuel',{}); crew=f.get('crew',{})
    corr=f.get('corr',{}); ez=f.get('ezfw',{})
    dep=f.get('dep',''); arr=f.get('arr','')

    out=io.BytesIO()
    cv=canvas.Canvas(out, pagesize=(PW,PH))

    def Y(top): return PH-top

    def R(x0,t,x1,b,fill=None,stroke=LGRAY,lw=0.5):
        cv.setLineWidth(lw)
        if fill: cv.setFillColor(fill)
        if stroke: cv.setStrokeColor(stroke)
        if fill and stroke: cv.rect(x0,Y(b),x1-x0,b-t,fill=1,stroke=1)
        elif fill: cv.rect(x0,Y(b),x1-x0,b-t,fill=1,stroke=0)
        else: cv.rect(x0,Y(b),x1-x0,b-t,fill=0,stroke=1)

    def H(x0,top,x1,col=LGRAY,lw=0.5):
        cv.setStrokeColor(col); cv.setLineWidth(lw)
        cv.line(x0,Y(top),x1,Y(top))

    def V(x,t0,t1,col=LGRAY,lw=0.5):
        cv.setStrokeColor(col); cv.setLineWidth(lw)
        cv.line(x,Y(t0),x,Y(t1))

    def T(text,x,top,sz=7,bold=False,color=DGRAY,al='l',bif=False):
        s=str(text).strip()
        if not s: return
        col=DBLUE if bif and filled(s) else color
        cv.setFillColor(col)
        cv.setFont('Helvetica-Bold' if bold else 'Helvetica',sz)
        if al=='c': cv.drawCentredString(x,Y(top),s)
        elif al=='r': cv.drawRightString(x,Y(top),s)
        else: cv.drawString(x,Y(top),s)

    # ── Colonnes (pts) ──
    C1=3; C2=195; C3=500; C4=670; CR=838
    TOP=3; BOT=592

    # ════════════════════════════════════════════════════
    # PAGE 1
    # ════════════════════════════════════════════════════
    R(C1,TOP,CR,BOT,stroke=DGRAY,lw=1.2)
    H(C1,52,CR,DGRAY,1)
    V(C2,52,BOT,DGRAY,0.8)
    V(C3,52,BOT,DGRAY,0.8)
    V(C4,52,BOT,DGRAY,0.8)

    # ── HEADER ──
    T(f"{dep}  =>  {arr}",8,22,sz=13,bold=True)
    T(f"({f.get('duration','')})",145,22,sz=10)
    T(f.get('vol_nums',''),430,22,sz=11,bold=True)
    # TWINJET bloc
    R(555,TOP+2,670,50,stroke=LGRAY,lw=0.5)
    T('TWINJET',560,17,sz=8,bold=True)
    T('iNTAIRLINE',560,28,sz=8,bold=True)
    T('AIR QUALIFICATIONS',560,39,sz=8,bold=True)
    # B1900D bloc
    R(670,TOP+2,785,50,stroke=LGRAY,lw=0.5)
    T('B1900D PVE1(Logiciel V3.8)',674,15,sz=6.5)
    T('Craft Data Source: MANEX TJT B4',674,25,sz=6,color=MGRAY)
    T('Nav Data Source: EURO FPL',674,35,sz=6,color=MGRAY)
    # N° étape
    R(785,TOP+2,CR,50,stroke=LGRAY,lw=0.5)
    R(787,36,CR-2,49,stroke=LGRAY)
    T("N° étape",789,45,sz=5.5)
    T(f.get('num_etape',''),810,47,sz=7,bold=True,bif=True,al='c')
    # Routing
    T(f"{f.get('fl','')} ROUTING: {f.get('route','')}",8,38,sz=6.5)
    # PVE TAILOR dans header
    T('PVE "TAILOR"',285,18,sz=11,bold=True)
    T('VER 4.0',285,31,sz=8)

    # ══════════════════════════════════
    # COL 1 — FUEL (x=3..195)
    # ══════════════════════════════════
    R(C1,52,C2,68,fill=BG2,stroke=LGRAY)
    T('Fuel Calculation',C1+4,64,sz=6.5,bold=True)
    T('Time',115,64,sz=5.5,color=MGRAY,al='c')
    T('Fuel (lbs)',C2-4,64,sz=5.5,color=MGRAY,al='r')
    V(105,52,435,LGRAY,0.4); V(140,52,435,LGRAY,0.4)

    FUEL_ROWS=[
        ('Climb+T/O',         fuel.get('t_climb',''),  fuel.get('f_climb','')),
        ('Cruise',            fuel.get('t_cruise',''), fuel.get('f_cruise','')),
        ('Descent',           fuel.get('t_desc',''),   fuel.get('f_desc','')),
        ('Approach',          '00:12',                 '150'),
        ('Total',             fuel.get('t_trip',''),   fuel.get('f_total','')),
        ('+ Correction',      '',                      fuel.get('f_corr','')),
        ('= Trip Fuel',       '',                      fuel.get('f_trip','')),
        ('RR (5% > 60 LBs)',  '',                      fuel.get('f_rr','')),
        ('ALtn Fuel',         fuel.get('t_altn',''),   fuel.get('f_altn','')),
        ('Final reserve',     '00:30',                 '380'),
        ('Taxi (110 Lbs Mini)','',                     fuel.get('f_taxi','110')),
        ('Extra / add Fuel',  '',                      fuel.get('f_extra','')),
        ('CDB Fuel',          '',                      fuel.get('f_cdb','')),
        ('Required Fuel',     '',                      fuel.get('f_required','')),
        ('Block Fuel',        '',                      fuel.get('f_block','')),
    ]
    FIXED={'Approach','Final reserve'}; BOLDF={'= Trip Fuel','Required Fuel','Block Fuel'}
    FRH=15.5; YFS=68
    for i,(lbl,ti,fv) in enumerate(FUEL_ROWS):
        yt=YFS+i*FRH; yb=yt+FRH
        if lbl in ('= Trip Fuel','Block Fuel'):
            R(105,yt+1,140,yb-1,fill=WHITE,stroke=LGRAY)
            R(140,yt+1,C2-2,yb-1,fill=WHITE,stroke=LGRAY)
        ib=lbl in BOLDF; fx=lbl in FIXED
        T(lbl,C1+4,yt+10,sz=6,bold=ib)
        if ti: T(ti,122,yt+10,sz=6,al='c',color=DGRAY if fx else (DBLUE if filled(ti) else LGRAY))
        if fv: T(fv,C2-4,yt+10,sz=6,bold=ib,al='r',color=DGRAY if fx else (DBLUE if filled(fv) else LGRAY))
        H(C1,yb,C2,LGRAY,0.3)

    Y_AF=YFS+len(FUEL_ROWS)*FRH

    # DOW/DOI/cf
    R(C1,Y_AF,C2,Y_AF+16,fill=WHITE,stroke=LGRAY)
    T('DOW/DOI/cf',C1+4,Y_AF+11,sz=6.5,bold=True)
    for j,cx in enumerate([80,110,140]):
        R(cx,Y_AF+2,cx+26,Y_AF+14,stroke=LGRAY)
    T(f.get('avion',''),82,Y_AF+11,sz=5.5,bif=True)
    T(f.get('version',''),123,Y_AF+11,sz=6,bif=True,al='c')
    T(f.get('doi',''),C2-4,Y_AF+11,sz=6,bif=True,al='r')
    H(C1,Y_AF+16,C2,LGRAY,0.5)
    T(f"DOW: {f.get('dow','')} lbs",C1+4,Y_AF+26,sz=6,
      color=DBLUE if filled(f.get('dow','')) else LGRAY)
    H(C1,Y_AF+30,C2,LGRAY,0.5)

    # Gestion carburant
    YGS=Y_AF+30
    R(C1,YGS,C2,YGS+13,fill=BG2,stroke=LGRAY)
    T('GESTION CARBURANT',C1+4,YGS+9,sz=6.5,bold=True)
    T('CONSO',150,YGS+9,sz=6,bold=True)
    V(144,YGS,BOT,LGRAY,0.4)
    GEST=['JAUGEURS EN VOL','CONSO RESTANTE ESTIMEE','JAUGEUR ARRIVEE ESTIMEE',
          'DELESTAGE DEGAGEMENT','CORRECTION','RESERVE FINALE      380',
          'JAUGEUR AVANT DEGAG.','FUEL DISPO ATTENTE','TPS ATTENTE (min)']
    for i,lbl in enumerate(GEST):
        gy=YGS+13+i*14
        R(C1,gy,C2,gy+14,fill=BG3 if i%2==0 else WHITE,stroke=LGRAY,lw=0.3)
        T(lbl,C1+4,gy+10,sz=5.8)

    # ══════════════════════════════════
    # COL 2 — ROUTE (x=195..500)
    # ══════════════════════════════════
    # Colonnes internes route
    WC=[195,234,272,298,322,346,372,408,452,500]
    # SECU | NOM | RM° | D | Tsv' | HE | HR | Fuel | F.Est | Reel

    R(C2,52,C3,68,fill=BG2,stroke=LGRAY)
    T('RM° D',(WC[2]+WC[4])/2,58,sz=5.5,al='c',color=MGRAY)
    hdrs=[('SECU(¹)',0),('ROUTE',1),("Tsv'",4),('HE',5),('HR',6),('Fuel',7),('F.Est',8)]
    for nm,i in hdrs:
        mx=(WC[i]+WC[i+1])/2
        T(nm,mx,63 if nm in ('HE','HR','F.Est','ROUTE') else 58,sz=5.5,al='c',
          color=DGRAY if nm in ('HE','HR','F.Est','ROUTE') else MGRAY,
          bold=nm in ('HE','HR','F.Est','ROUTE'))
    T('Reel',(WC[8]+WC[9])/2,63,sz=5.5,al='c',color=DGRAY,bold=True)
    for cx in WC: V(cx,52,BOT,LGRAY,0.3)

    WP=f.get('waypoints',[]); WPH=14.5; WPY0=68
    for i,wp in enumerate(WP):
        yt=WPY0+i*WPH; yb=yt+WPH
        R(C2,yt,C3,yb,fill=BG1 if i%2==0 else BG3)
        R(WC[0],yt+0.5,WC[1]-0.5,yb-0.5,fill=BG2)
        R(WC[3],yt+0.5,WC[4]-0.5,yb-0.5,fill=BG2)
        R(WC[7],yt+0.5,WC[8]-0.5,yb-0.5,fill=BG2)
        H(C2,yb,C3,LGRAY,0.3)
        n=wp['n']; ie=i==0 or i==len(WP)-1; it=n in ('TOC','TOD')
        nc=BLUE if ie else (HexColor('#664400') if it else DGRAY)
        T(wp.get('alt',''),(WC[0]+WC[1])/2,yt+10,sz=6.5,bold=ie or it,color=nc,al='c')
        T(n,(WC[1]+WC[2])/2,yt+10,sz=7,bold=ie or it,color=nc,al='c')
        if wp.get('drm'): T(wp['drm']+'°',(WC[2]+WC[3])/2,yt+10,sz=6.5,al='c')
        if wp.get('dist'): T(wp['dist'],(WC[3]+WC[4])/2,yt+10,sz=6.5,al='c')
        if wp.get('tsv'): T(wp['tsv']+"'",(WC[4]+WC[5])/2,yt+10,sz=6,color=MGRAY,al='c')
        if wp.get('fuel_est'): T(wp['fuel_est'],(WC[7]+WC[8])/2,yt+10,sz=6,color=DGRAY,al='c')
        if filled(wp.get('he','')): T(wp['he'],(WC[5]+WC[6])/2,yt+10,sz=6,color=DBLUE,al='c')
        if filled(wp.get('f_est','')): T(wp['f_est'],(WC[8]+WC[9])/2,yt+10,sz=6,color=DBLUE,al='c')

    yTot=WPY0+len(WP)*WPH
    R(C2,yTot,C3,yTot+13,fill=BG2); H(C2,yTot,C3,DGRAY,0.8)
    T('Totaux :',(WC[0]+WC[2])/2,yTot+9,sz=6.5,bold=True,al='c')
    if filled(fuel.get('t_trip','')): T(fuel['t_trip'],(WC[5]+WC[6])/2,yTot+9,sz=6.5,bold=True,color=DBLUE,al='c')
    if filled(fuel.get('f_trip','')): T(fuel['f_trip'],(WC[8]+WC[9])/2,yTot+9,sz=6.5,bold=True,color=DBLUE,al='c')

    # ALTERNATES
    yA0=yTot+13; alts=f.get('alternates',[])
    R(C2,yA0,C3,yA0+13,fill=BG2); H(C2,yA0,C3,DGRAY,0.8)
    T('ALTERNATES (³)',(C2+C3)/2,yA0+9,sz=6.5,bold=True,al='c')
    for ia,a in enumerate(alts[:2]):
        ya=yA0+13+ia*44
        R(C2,ya,C3,ya+14,fill=BG2)
        T(f"{a.get('from_alt','')} FL{a.get('alt','')}",WC[0]+2,ya+10,sz=6.5,bold=True)
        T(a.get('via',''),WC[1]+2,ya+10,sz=5.5,color=MGRAY)
        T(a.get('altn',''),WC[8]+2,ya+10,sz=8,bold=True,color=BLUE)
        H(C2,ya+14,C3,LGRAY,0.3)
        R(C2,ya+14,C3,ya+30,fill=BG3)
        T(a.get('drm','')+'°',(WC[2]+WC[3])/2,ya+25,sz=6.5,al='c')
        T(str(a.get('dist','')),(WC[3]+WC[4])/2,ya+25,sz=6.5,al='c')
        T(a.get('he',''),(WC[5]+WC[6])/2,ya+25,sz=6.5,al='c',
          color=DBLUE if filled(a.get('he','')) else LGRAY)
        T(a.get('f',''),(WC[7]+WC[8])/2,ya+25,sz=6.5,al='c',
          color=DBLUE if filled(a.get('f','')) else LGRAY)
        H(C2,ya+30,C3,LGRAY,0.3)
        T("12'",(WC[5]+WC[6])/2,ya+39,sz=6.5,al='c')
        T('150',(WC[7]+WC[8])/2,ya+39,sz=6.5,al='c')
        T(f"Totaux : {a.get('he_tot','')}",WC[0]+2,ya+39,sz=6)
        T(str(a.get('tot','')),(WC[8]+WC[9])/2,ya+39,sz=6.5,bold=True,color=DBLUE,al='c')
        H(C2,ya+44,C3,LGRAY,0.4)

    # ══════════════════════════════════
    # COL 3 — PANNE + NOTES + DEP/ARR + CORRECTION (x=500..670)
    # ══════════════════════════════════
    yC3=52
    # Panne moteur
    R(C3,yC3,C4,yC3+13,fill=BG3,stroke=LGRAY)
    T('Panne moteur sur SID à la préparation',C3+3,yC3+9,sz=6,bold=True)
    H(C3,yC3+13,C4,LGRAY,0.5)
    T('VMC',C3+4,yC3+24,sz=6); T('IMC',C3+32,yC3+24,sz=6)
    T('Pente SID:',C3+55,yC3+22,sz=5.5); T('Pente N-1 QRH:',C3+110,yC3+22,sz=5.5)
    T('Pente Equiv:',C3+55,yC3+32,sz=5.5)
    T('Stratégie:',C3+3,yC3+44,sz=5.5)
    R(C3+45,yC3+36,C4-3,yC3+48,stroke=LGRAY)
    T('Ralliement IAF à la MSA secteur N-1 à Vyse',C3+47,yC3+45,sz=5,color=MGRAY)
    T('Altitude de sécurité:',C3+3,yC3+56,sz=5.5)
    T('Ref:',C3+110,yC3+56,sz=5.5)
    H(C3,yC3+60,C4,LGRAY,0.5)
    # Corrections T/QNH
    T('(ð T°) 71 x ........... =',C3+3,yC3+71,sz=6)
    T('(ð QNH) 28 x ........... =',C3+3,yC3+81,sz=6)
    H(C3+3,yC3+84,C4-3,LGRAY,0.3)
    T('Correction de MEA =',C3+5,yC3+93,sz=6)
    H(C3,yC3+97,C4,LGRAY,0.3)
    T('TSV MAX =>',C3+5,yC3+108,sz=6,bold=True)
    H(C3,yC3+112,C4,LGRAY,0.5)
    # Contacts
    T(f"Contacts : {f.get('freq_dep','')} / {f.get('freq_arr','')}",
      C3+3,yC3+122,sz=6,bold=True)
    H(C3,yC3+125,C4,LGRAY,0.4)
    # Notes
    notes=['Croisière High Speed 1550 RPM à Masse Max en ISA',
           '(¹) Z SECU: Buffer ±10 Nm. Source Eurofpl / SRTM Topographic data',
           f"(²) {f.get('tod_note','')}",
           '(³) Trajectoire ALTN la plus probable au vu des cartes']
    for i,n in enumerate(notes):
        T(n,C3+3,yC3+135+i*11,sz=5.5,color=MGRAY)
    H(C3,yC3+180,C4,LGRAY,0.5)
    # DEP / ARR
    R(C3,yC3+180,C4,yC3+215,fill=BG3,stroke=LGRAY)
    V((C3+C4)//2,yC3+180,yC3+215,LGRAY,0.4)
    H(C3,yC3+195,C4,LGRAY,0.3)
    T(dep,C3+4,yC3+193,sz=9,bold=True)
    T(f"ETD : {f.get('etds','')}",C3+4,yC3+206,sz=6,
      color=DBLUE if filled(f.get('etds','')) else LGRAY)
    T(f.get('freq_dep',''),C3+4,yC3+214,sz=5.5,color=MGRAY)
    mx2=(C3+C4)//2
    T(arr,mx2+4,yC3+193,sz=9,bold=True)
    T(f"ETA : {f.get('etas','')}",mx2+4,yC3+206,sz=6,
      color=DBLUE if filled(f.get('etas','')) else LGRAY)
    T(f.get('freq_arr',''),mx2+4,yC3+214,sz=5.5,color=MGRAY)
    H(C3,yC3+215,C4,LGRAY,0.5)
    # GRANDEUR CORRECTION
    yGC=yC3+215
    R(C3,yGC,C4,yGC+13,fill=BG2,stroke=LGRAY)
    T('GRANDEUR',C3+4,yGC+9,sz=6.5,bold=True)
    T('CORRECTION',(C3+C4)/2,yGC+9,sz=6.5,bold=True,al='c')
    V((C3+C4)/2,yGC,BOT,LGRAY,0.4)
    H(C3,yGC+13,C4,LGRAY,0.5)
    CORR_ROWS=[('C/D de ref',corr.get('cd','')),
               ('Vw: ± 10 KTS',f"± {corr.get('vw','')} %"),
               ('T: - 10°C',f"+ {corr.get('t','')} %"),
               ('FL: - 1000 fts',f"+ {corr.get('fl_up','')} %"),
               ('FL: + 1000 fts',f"- {corr.get('fl_dn','')} %"),
               ('M: - 1000 LBS',f"- {corr.get('m','')} %")]
    for i,(k,v) in enumerate(CORR_ROWS):
        cy=yGC+13+i*16
        T(k,C3+4,cy+11,sz=6.5); T(v,C4-4,cy+11,sz=6.5,bold=True,al='r')
        if i<5: H(C3,cy+16,C4,LGRAY,0.3)

    # ══════════════════════════════════
    # COL 4 — SURETE + TIMES + CREW (x=670..838)
    # ══════════════════════════════════
    yC4=52
    # PVE TAILOR
    T('PVE "TAILOR"',C4+4,yC4+15,sz=10,bold=True)
    T('VER 4.0',C4+4,yC4+27,sz=8)
    H(C4,yC4+33,CR,LGRAY,0.5)
    # SURETE header
    R(C4,yC4+33,CR,yC4+46,fill=BG2,stroke=LGRAY)
    T('SURETE:',C4+4,yC4+42,sz=7,bold=True)
    H(C4,yC4+46,CR,LGRAY,0.5)
    # Champs surete
    SUR_ROWS=[('Avion:',f.get('avion','')),('Date:',f.get('date','')),
              ('N° VOL:',f.get('vol_nums','')),('Prov:','')]
    for i,(lb,vl) in enumerate(SUR_ROWS):
        sy=yC4+46+i*15
        T(lb,C4+4,sy+10,sz=5.5,color=MGRAY)
        T(vl,CR-3,sy+10,sz=6.5,bold=True,
          color=DBLUE if filled(vl) else LGRAY,al='r')
        H(C4,sy+15,CR,LGRAY,0.3)
    # Fouille
    yFo=yC4+46+len(SUR_ROWS)*15
    R(C4,yFo,CR,yFo+15,fill=BG3)
    T('Fouille',C4+4,yFo+10,sz=5.5,color=MGRAY)
    fo=f.get('fouille','')
    for j,opt in enumerate(['OUI','NON']):
        bx=C4+42+j*28; R(bx,yFo+3,bx+9,yFo+12,stroke=MGRAY)
        if fo==opt: T('X',bx+1,yFo+11,sz=6.5,bold=True,color=DBLUE)
    T('OUI',C4+52,yFo+10,sz=5.5); T('NON',C4+80,yFo+10,sz=5.5)
    H(C4,yFo+15,CR,LGRAY,0.3)
    yHL=yFo+15
    T('Heure LT:',C4+4,yHL+10,sz=5.5,color=MGRAY)
    T(f.get('heure_fouille',''),CR-3,yHL+10,sz=6.5,
      color=DBLUE if filled(f.get('heure_fouille','')) else LGRAY,al='r')
    H(C4,yHL+15,CR,LGRAY,0.3)
    yCDB=yHL+15
    T('CDB:',C4+4,yCDB+10,sz=5.5,color=MGRAY)
    T(crew.get('cdb_tri',''),CR-3,yCDB+10,sz=7,bold=True,
      color=DBLUE if filled(crew.get('cdb_tri','')) else LGRAY,al='r')
    H(C4,yCDB+15,CR,LGRAY,0.3)
    ySg=yCDB+15
    T('Signature:',C4+4,ySg+10,sz=5.5,color=MGRAY)
    H(C4,ySg+15,CR,LGRAY,0.5)
    # TIMES
    yTM=ySg+15
    R(C4,yTM,CR,yTM+13,fill=BG2,stroke=LGRAY)
    T('TIMES',C4+4,yTM+9,sz=6,bold=True)
    T('BLOCK',C4+62,yTM+9,sz=5.5,color=MGRAY,al='c')
    T('FLIGHT',C4+110,yTM+9,sz=5.5,color=MGRAY,al='c')
    V(C4+36,yTM,yTM+58,LGRAY,0.4); V(C4+80,yTM,yTM+58,LGRAY,0.4)
    H(C4,yTM+13,CR,LGRAY,0.5)
    for i,lbl in enumerate(['ARR','DEP','TPS']):
        ty=yTM+13+i*15
        T(lbl,C4+4,ty+10,sz=6,bold=True)
        H(C4+37,ty+7,C4+79,HexColor('#BBBBBB'),0.4)
        H(C4+81,ty+7,CR-3,HexColor('#BBBBBB'),0.4)
        if i<2: H(C4,ty+15,CR,LGRAY,0.3)
    # CREW
    yCW=yTM+58
    R(C4,yCW,CR,yCW+13,fill=BG2,stroke=LGRAY)
    T('CREW',C4+4,yCW+9,sz=6,bold=True)
    T('Trigram',C4+40,yCW+9,sz=5,color=MGRAY)
    T('PF/PM',C4+80,yCW+9,sz=5,color=MGRAY)
    V(C4+34,yCW,BOT,LGRAY,0.4); V(C4+72,yCW,BOT,LGRAY,0.4)
    H(C4,yCW+13,CR,LGRAY,0.5)
    for i,(role,tri,pf) in enumerate([
        ('CDB',crew.get('cdb_tri',''),crew.get('cdb_pf','')),
        ('OPL',crew.get('opl_tri',''),crew.get('opl_pf','')),
        ('PCB',crew.get('pcb_quad',''),''),
    ]):
        cy=yCW+13+i*18
        R(C4,cy,CR,cy+18,fill=BG3 if i%2 else WHITE,stroke=LGRAY,lw=0.2)
        T(role,C4+4,cy+12,sz=6.5,bold=True)
        T(tri,C4+38,cy+12,sz=7,bold=True,
          color=DBLUE if filled(tri) else LGRAY)
        if pf: T(pf,C4+76,cy+12,sz=7,color=DBLUE)
        if role=='PCB': R(C4+72,cy+2,CR-2,cy+16,fill=BG2)
        if i<2: H(C4,cy+18,CR,LGRAY,0.3)

    # ════════════════════════════════════════════════════
    # PAGE 2 — MÉTÉO (gauche x=3..500) + EZFW (droite x=500..838)
    # ════════════════════════════════════════════════════
    cv.showPage()
    cv.setPageSize((PW,PH))
    R(C1,TOP,CR,BOT,stroke=DGRAY,lw=1.2)
    V(500,TOP,BOT,DGRAY,0.8)

    # ── Header page 2 ──
    R(C1,TOP,CR,38,fill=BLACK,stroke=BLACK)
    T('MÉTÉO & MASSE',10,26,sz=12,bold=True,color=WHITE)
    T(f"{dep} → {arr}  ·  {f.get('vol_nums','')}  ·  {f.get('date','')}",
      185,26,sz=9,color=HexColor('#AACCFF'))
    T(f"Généré le {f.get('generated','')}",CR-6,26,sz=8,
      color=HexColor('#AAAAAA'),al='r')
    H(C1,38,CR,DGRAY,1)

    # ── MÉTÉO gauche (x=3..500) ──
    R(C1,38,500,52,fill=NAVY,stroke=NAVY)
    T('MÉTÉO — METAR / TAF',C1+6,49,sz=8,bold=True,color=WHITE)

    yMR=52
    for icao,md in f.get('metars',{}).items():
        ms=str(md.get('metar','')).strip() or 'Aucune donnée'
        ts=str(md.get('taf','')).strip()
        ml=tw(ms,82) or [ms]; tl=tw(ts,82) if ts else []
        bh=14+(len(ml)+(len(tl)+1 if tl else 0))*10+4
        if yMR+bh>BOT-2: break
        R(C1,yMR,500,yMR+bh,fill=BG3,stroke=LGRAY,lw=0.4)
        R(C1,yMR,C1+46,yMR+bh,fill=BG2,stroke=LGRAY,lw=0.4)
        T(icao,(C1+C1+46)/2,yMR+bh/2+5,sz=12,bold=True,color=BLUE,al='c')
        T('METAR',C1+50,yMR+12,sz=6.5,bold=True,color=MGRAY)
        for j,line in enumerate(ml):
            T(line,C1+50,yMR+22+j*10,sz=8,color=HexColor('#882200'))
        if tl:
            ytf=yMR+22+len(ml)*10+4
            T('TAF',C1+50,ytf,sz=6.5,bold=True,color=MGRAY)
            for j,line in enumerate(tl):
                T(line,C1+50,ytf+10+j*10,sz=8,color=HexColor('#004411'))
        H(C1,yMR+bh,500,LGRAY,0.4)
        yMR+=bh

    # ── EZFW droite (x=500..838) ──
    R(500,38,CR,52,fill=NAVY,stroke=NAVY)
    T('EZFW — MASSE ESTIMÉE',505,49,sz=8,bold=True,color=WHITE)

    # Tableau pax
    yEZ=52
    R(500,yEZ,CR,yEZ+16,fill=BG2,stroke=LGRAY)
    T('Catégorie',508,yEZ+11,sz=7,bold=True)
    T('Nb',632,yEZ+11,sz=7,bold=True,al='c')
    T('Masse std',700,yEZ+11,sz=7,bold=True,al='c')
    T('Total',CR-6,yEZ+11,sz=7,bold=True,al='r')
    V(622,yEZ,yEZ+110,LGRAY,0.4)
    V(672,yEZ,yEZ+110,LGRAY,0.4)
    H(500,yEZ+16,CR,LGRAY,0.5)

    PAX=[('Hommes',str(ez.get('h',0)),'203 lbs',f"{ez.get('h_mass',0):,} lbs"),
         ('Femmes',str(ez.get('f',0)),'160 lbs',f"{ez.get('f_mass',0):,} lbs"),
         ('Enfants',str(ez.get('e',0)),'77 lbs',f"{ez.get('e_mass',0):,} lbs"),
         ('Bagages',str(ez.get('total_pax',0)),'10 lbs/pax',f"{ez.get('bag_mass',0):,} lbs")]
    for i,(cat,nb,std,tot) in enumerate(PAX):
        ey=yEZ+16+i*22
        R(500,ey,CR,ey+22,fill=BG3 if i%2==0 else WHITE,stroke=LGRAY,lw=0.3)
        T(cat,508,ey+15,sz=8)
        T(nb,632,ey+15,sz=10,bold=True,color=DBLUE,al='c')
        T(std,700,ey+15,sz=7,color=MGRAY,al='c')
        T(tot,CR-6,ey+15,sz=8,bold=True,al='r')
        H(500,ey+22,CR,LGRAY,0.3)

    # Payload total
    yPL=yEZ+16+len(PAX)*22
    R(500,yPL,CR,yPL+22,fill=BG2,stroke=LGRAY)
    T('Payload total',508,yPL+15,sz=8,bold=True)
    T(f"{ez.get('payload',0):,} lbs",CR-6,yPL+15,sz=9,bold=True,color=DBLUE,al='r')
    H(500,yPL+22,CR,DGRAY,0.8)

    # DOW
    yDW=yPL+22
    R(500,yDW,CR,yDW+22,fill=BG3,stroke=LGRAY)
    T('DOW',508,yDW+15,sz=8)
    T(f.get('avion',''),575,yDW+15,sz=8,color=DBLUE)
    T(f"ver. {f.get('version','')}",632,yDW+15,sz=7,color=MGRAY)
    T(f"{f.get('dow','')} lbs",CR-6,yDW+15,sz=9,bold=True,al='r')
    H(500,yDW+22,CR,DGRAY,1)

    # EZFW résultat
    yEZR=yDW+22
    R(500,yEZR,CR,yEZR+40,fill=LBLUE,stroke=HexColor('#0044BB'),lw=1)
    T('EZFW  (DOW + Payload)',508,yEZR+16,sz=9,bold=True,color=HexColor('#003399'))
    T(f"{ez.get('ezfw',0):,} lbs",CR-6,yEZR+30,sz=18,bold=True,
      color=HexColor('#003399'),al='r')

    # Marge MTOW
    yMT=yEZR+40
    mtow=17120; ezfw_val=ez.get('ezfw',0); margin=mtow-ezfw_val
    mc=HexColor('#006600') if margin>500 else (HexColor('#CC6600') if margin>0 else HexColor('#CC0000'))
    R(500,yMT,CR,yMT+22,fill=WHITE,stroke=LGRAY)
    T('MTOW  17 120 lbs',508,yMT+15,sz=8,color=MGRAY)
    T(f"Marge MTOW : {margin:+,} lbs",CR-6,yMT+15,sz=9,bold=True,color=mc,al='r')

    cv.save(); out.seek(0)
    return base64.b64encode(out.read()).decode()

app = Flask(__name__)
CORS(app)

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
    icao = request.args.get('icao', '').upper().strip()
    if len(icao) != 4:
        return jsonify({'error': 'ICAO invalide'}), 400
    try:
        BASE = 'https://aviationweather.gov/api/data'
        mr = requests.get(f"{BASE}/metar?ids={icao}&format=raw&hours=2", timeout=8)
        tr = requests.get(f"{BASE}/taf?ids={icao}&format=raw&hoursBeforeNow=4", timeout=8)
        metar = mr.text.strip() if mr.ok else ''
        taf   = tr.text.strip() if tr.ok else ''
        return jsonify({'icao': icao, 'metar': metar or 'Aucune observation disponible', 'taf': taf})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
