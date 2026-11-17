"""Native KiCad 10 schematic authoring helper for the Kenwood TM-V71A proxy board.

KiCad owns rendering, ERC, netlist and BOM export. Re-running regenerates the
schematic and overwrites GUI edits; preserve manual KiCad work first.
Connectivity is expressed with short pin stubs and global labels so the netlist
can be checked mechanically (see check_design.py).
"""
from pathlib import Path
import copy, json, re, uuid, math

HERE = Path(__file__).resolve().parent
LIBROOT = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols')
PROJECT = 'kenwood_proxy'
LIBNICK = 'Kenwood_Proxy'
ROOT_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, 'kenwood-proxy-root'))
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'kenwood-proxy/' + s))

# ---------------------------------------------------------------- s-expr helpers
class Atom(str): pass
def parse(s):
    toks = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', s)
    stack=[]; root=None
    for t in toks:
        if t=='(':
            a=[]
            if stack: stack[-1].append(a)
            else: root=a
            stack.append(a)
        elif t==')': stack.pop()
        else: stack[-1].append(json.loads(t) if t.startswith('"') else Atom(t))
    assert not stack
    return root
def dump(x):
    if isinstance(x,list): return '('+' '.join(dump(y) for y in x)+')'
    if isinstance(x,Atom): return str(x)
    if isinstance(x,str): return json.dumps(x, ensure_ascii=False)
    return str(x)
def node(tag,*args): return [Atom(tag),*args]
def first(x,k): return next((z for z in x if isinstance(z,list) and z and z[0]==k),None)
def allof(x,k): return [z for z in x if isinstance(z,list) and z and z[0]==k]
def fx(size=1.27,justify=None,hide=False):
    r=node('effects',node('font',node('size',size,size)))
    if justify:r.append(node('justify',*[Atom(i) for i in justify.split()]))
    if hide:r.append(node('hide',Atom('yes')))
    return r
def prop(k,v,x=0,y=0,hidden=True): return node('property',k,v,node('at',x,y,0),fx(hide=hidden))

LIBS={}; SYMBOLS={}
def standard(lib,name):
    if lib not in LIBS:
        LIBS[lib]={s[1]:s for s in allof(parse((LIBROOT/(lib+'.kicad_sym')).read_text()),'symbol')}
    def expand(n):
        c=copy.deepcopy(LIBS[lib][n]); e=first(c,'extends')
        if e:
            p=expand(e[1]); old=p[1]; p[1]=n
            for z in allof(p,'symbol'): z[1]=z[1].replace(old+'_',n+'_',1)
            for z in c[2:]:
                if not isinstance(z,list) or z[0]=='extends': continue
                if z[0]=='property': p=[a for a in p if not (isinstance(a,list) and a[:2]==z[:2])]
                elif z[0] not in ('symbol',): p=[a for a in p if not(isinstance(a,list) and a[0]==z[0])]
                p.append(z)
            return p
        return c
    s=expand(name); new=lib+'_'+name; old=s[1]; s[1]=new
    for z in allof(s,'symbol'): z[1]=z[1].replace(old+'_',new+'_',1)
    SYMBOLS[new]=s
    return new
def custom(name,ref,pins,w=15.24,h=12.7,desc='',footprint=''):
    s=node('symbol',name,node('pin_names',node('offset',0.508)),node('in_bom',Atom('yes')),node('on_board',Atom('yes')),
           prop('Reference',ref,0,h+3,False),prop('Value',name,0,h+1,False),prop('Footprint',footprint),prop('Datasheet',''),prop('Description',desc))
    art=node('symbol',name+'_0_1',node('rectangle',node('start',-w,h),node('end',w,-h),node('stroke',node('width',0.254),node('type',Atom('default'))),node('fill',node('type',Atom('background')))))
    body=node('symbol',name+'_1_1')
    for num,pn,ty,x,y,a in pins:
        body.append(node('pin',Atom(ty),Atom('line'),node('at',x,y,a),node('length',2.54),node('name',pn,fx(1.016)),node('number',str(num),fx(1.016))))
    s += [art,body]; SYMBOLS[name]=s
    return name
def pins_for(sym,unit=1):
    out={}
    for u in allof(SYMBOLS[sym],'symbol'):
        m=re.search(r'_(\d+)_(\d+)$',u[1]); un,style=map(int,m.groups())
        if un not in (0,unit) or style not in (0,1): continue
        for p in allof(u,'pin'):
            a=first(p,'at'); no=first(p,'number')[1]
            out[no]={'name':first(p,'name')[1],'type':p[1],'x':float(a[1]),'y':float(a[2]),'a':float(a[3])}
    return out

# ---------------------------------------------------------------- symbols
R=standard('Device','R'); C=standard('Device','C'); CP=standard('Device','C_Polarized')
XTAL=standard('Device','Crystal'); DIODE=standard('Diode','1N4148')
LDO=standard('Regulator_Linear','LM2936-5.0_TO92')
OPTO=standard('Isolator','SFH617A-3'); MCU=standard('MCU_Microchip_AVR_Dx','AVR128DB28x-xSP')
CON2=standard('Connector_Generic','Conn_01x02'); CON3=standard('Connector_Generic','Conn_01x03'); CON4=standard('Connector_Generic','Conn_01x04')
TP=standard('Connector','TestPoint')
HOLE=standard('Mechanical','MountingHole'); FLAG=standard('power','PWR_FLAG')
JACK=custom('WR-MJ_4P4C_TabUp','J',[
    ('1','PB','passive',-17.78,3.81,0),('2','GND','passive',-17.78,1.27,0),
    ('3','DATA_body-to-head','passive',-17.78,-1.27,0),('4','DATA_head-to-body','passive',-17.78,-3.81,0)],
    w=15.24,h=6.35,desc='Wurth 615004143821 4P4C. Manufacturer numbering: looking into mating face, tab up, contacts 4,3,2,1 left to right.',
    footprint=LIBNICK+':Wurth_615004143821_4P4C_TabUp')

# ---------------------------------------------------------------- parts
FP = {
 'R':     'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal',
 'R762':  'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal',
 'R05W':  'Resistor_THT:R_Axial_DIN0309_L9.0mm_D3.2mm_P12.70mm_Horizontal',
 'R1W':   'Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal',
 'C':     'Capacitor_THT:C_Disc_D3.8mm_W2.6mm_P2.50mm',
 'CTANT': 'Capacitor_THT:CP_Radial_Tantal_D6.0mm_P2.50mm',
 'CELEC': 'Capacitor_THT:CP_Radial_D5.0mm_P2.00mm',
 'TO92':  'Package_TO_SOT_THT:TO-92_Inline_Wide',
 'DIP4':  'Package_DIP:DIP-4_W7.62mm',
 'DIP28S':'Package_DIP:DIP-28_W7.62mm_Socket',
 'XTAL':  'Crystal:Crystal_DS26_D2.0mm_L6.0mm_Horizontal',
 'DO35':  'Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal',
 'H2':    'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
 'H3':    'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',
 'H4':    'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
 'MF2':   'Connector_Molex:Molex_Micro-Fit_3.0_43045-0200_2x01_P3.00mm_Horizontal',
 'TP':    'TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm',
 'HOLE':  'MountingHole:MountingHole_3.2mm_M3',
}
MF='YAGEO'; MFR='MFR-25FBF52-'   # 1%, 0.25 W metal film, 52 mm tape
def mfr(v):
    v=v.split()[0]
    if v.endswith('k'):
        a,_,b=v[:-1].partition('.'); return MFR+a+'K'+b
    return MFR+v

SHEETS=[]; COMPONENTS={}; EXPECTED={}
class Sheet:
    def __init__(self,name,title,summary):
        self.name=name; self.uuid=uid(name); self.title=title; self.items=[]; self.used=set(); self.counter=0
        self.text(15.24,15.24,title,2.54); self.text(15.24,22.86,summary,1.27)
        SHEETS.append(self)
    def newid(self): self.counter+=1; return uid(self.name+'/'+str(self.counter))
    def text(self,x,y,t,size=1.27):
        self.items.append(node('text',t,node('at',x,y,0),fx(size,'left top'),node('uuid',self.newid())))
    def wire(self,a,b):
        if a==b:return
        self.items.append(node('wire',node('pts',node('xy',*a),node('xy',*b)),node('stroke',node('width',0),node('type',Atom('default'))),node('uuid',self.newid())))
    def label(self,p,net,angle=0):
        self.items.append(node('global_label',net,node('shape',Atom('bidirectional')),node('at',*p,angle),fx(1.016,'left' if angle==0 else 'right'),node('uuid',self.newid()),prop('Intersheetrefs','${INTERSHEET_REFS}',p[0],p[1])))
    def nc(self,p): self.items.append(node('no_connect',node('at',*p),node('uuid',self.newid())))
    def comp(self,ref,sym,x,y,nets,value,footprint,mpn='',mfg='',note='',angle=0,fit=True,assembly='HAND_THT',fields=None):
        self.used.add(sym); defs=SYMBOLS[sym]; pinmap=pins_for(sym)
        assert set(nets)==set(pinmap),(ref,sorted(nets),sorted(pinmap))
        assert ref not in COMPONENTS, ref
        dsheet=next((p[2] for p in allof(defs,'property') if p[1]=='Datasheet'),'')
        COMPONENTS[ref]={'symbol':sym,'value':value,'footprint':footprint,'mpn':mpn,'manufacturer':mfg,'fit':fit,'note':note,
                         'assembly':assembly,'sheet':self.name,'pins':{}}
        sid=self.newid()
        bom='no' if ref.startswith(('#','H','TP')) else 'yes'; brd='no' if ref.startswith('#') else 'yes'
        inst=node('symbol',node('lib_id',LIBNICK+':'+sym),node('at',x,y,angle),node('unit',1),node('in_bom',Atom(bom)),node('on_board',Atom(brd)),node('dnp',Atom('no' if fit else 'yes')),node('uuid',sid))
        if fields is None: fields=[(x+3.81,y-6.35),(x+3.81,y-3.81)]
        inst += [prop('Reference',ref,*fields[0],False),prop('Value',value,*fields[1],False),prop('Footprint',footprint),prop('Datasheet',dsheet),
                 prop('MPN',mpn),prop('Manufacturer',mfg),prop('Assembly',assembly if fit else 'DNP'),prop('DesignNote',note)]
        rad=math.radians(angle); pos={}
        for no,p in pinmap.items():
            px=round(x+p['x']*math.cos(rad)-p['y']*math.sin(rad),4)
            py=round(y-p['x']*math.sin(rad)-p['y']*math.cos(rad),4)
            pos[no]=(px,py)
            inst.append(node('pin',no,node('uuid',uid(sid+'/'+no))))
            net=nets[no]; COMPONENTS[ref]['pins'][no]={'name':p['name'],'net':net}
            EXPECTED[(ref,no)]=net
            if net is None: self.nc((px,py)); continue
            a=(p['a']+angle)%360
            vx=-math.cos(math.radians(a)); vy=math.sin(math.radians(a))
            end=(round(px+vx*5.08,4),round(py+vy*5.08,4))
            self.wire((px,py),end)
            if abs(vy)>0.5:
                elbow=(round(end[0]+2.54,4),end[1]); self.wire(end,elbow); end=elbow; la=0
            else: la=0 if vx>0 else 180
            self.label(end,net,la)
        inst.append(node('instances',node('project',PROJECT,node('path','/'+ROOT_ID+'/'+self.uuid,node('reference',ref),node('unit',1)))))
        self.items.append(inst)
        return pos
    def save(self):
        libs=[]
        for k in sorted(self.used):
            a=copy.deepcopy(SYMBOLS[k]); a[1]=LIBNICK+':'+k; libs.append(a)
        root=node('kicad_sch',node('version',20250114),node('generator',Atom('eeschema')),node('generator_version','10.0'),node('uuid',self.uuid),node('paper','A3'),
                  node('title_block',node('title',self.title),node('date','2026-11-15'),node('rev','B'),node('comment',1,'Electrical draft - not released for fabrication')),
                  node('lib_symbols',*libs),*self.items,node('embedded_fonts',Atom('no')))
        (HERE/(self.name+'.kicad_sch')).write_text(dump(root)+'\n')

def res(s,ref,x,y,value,a,b,mpn=None,fp=None,note='1%, 0.25 W metal film',angle=0):
    return s.comp(ref,R,x,y,{'1':a,'2':b},value,fp or FP['R'],mpn if mpn is not None else mfr(value),MF,note,angle)
def cap(s,ref,x,y,value,a,b='GND',mpn='',mfg='',fp=None,note=''):
    return s.comp(ref,C,x,y,{'1':a,'2':b},value,fp or FP['C'],mpn,mfg,note)
def tp(s,ref,x,y,net):
    return s.comp(ref,TP,x,y,{'1':net},net,FP['TP'],'','','Bare plated test pad (2.0 mm, 1.0 mm hole): probe, hook or solder a wire. No purchased part',assembly='PCB_FEATURE')
def flag(s,n,x,y,net):
    return s.comp('#FLG'+str(n),FLAG,x,y,{'1':net},'PWR_FLAG','',assembly='NONE')

# ================================================================ sheet 1
s=Sheet('01_radio_link','01  Kenwood radio link','Body and head 4P4C jacks, PB/GND pass-through, full-proxy body-to-head path, MCU receive taps.')
# Rev B: data directions MEASURED on the radio 2026-11-15 (FT232 sniff in the truck): the body transmits on
# cable pin 3 and the head on pin 4. Rev A had these reversed. Body->head data lands on J1.3 and leaves on J2.3.
jn=lambda side:{'1':'PB','2':'GND','3':'BODY_TXD' if side=='BODY' else 'HEAD_RXD','4':'HEAD_TXD'}
s.comp('J1',JACK,63.5,63.5,jn('BODY'),'KENWOOD BODY',LIBNICK+':Wurth_615004143821_4P4C_TabUp','615004143821','Wurth Elektronik',
       'Cable from radio body (already 4P4C). Pin 3 = body TX (measured), pin 4 = body RX, 2 = GND, 1 = PB',fields=[(63.5,52.07),(63.5,54.61)])
s.comp('J2',JACK,63.5,101.6,jn('HEAD'),'KENWOOD HEAD',LIBNICK+':Wurth_615004143821_4P4C_TabUp','615004143821','Wurth Elektronik',
       'Straight-through cable to control head. Identical pinout to J1',fields=[(63.5,90.17),(63.5,92.71)])
s.text(15.24,121.92,'Data directions MEASURED on the radio (2026-11-15, Rev A sniff): pin 3 carries body -> head\n(display data), pin 4 carries head -> body (keys). Rev A had these swapped. PB = pin 1, GND = pin 2 (confirmed).\nCables are straight-through; never cross pins between J1 and J2.')
s.text(139.7,58.42,'PB and GND pass straight through in copper (J1 pin 1/2 = J2 pin 1/2). The board supply taps PB.')
# body -> head data path: FULL PROXY only. The MCU receives every body byte on TAP_BODY and retransmits it to the head.
res(s,'R2',203.2,88.9,'470R','HEAD_TX_MCU','HEAD_RXD',note='MCU USART1 TX -> head RX series resistor: limits current into head input clamps and into the body driver if JP1 is fitted with U1 present (<=3.5 mA)')
s.comp('JP1',CON2,88.9,170.18,{'1':'BODY_TXD','2':'HEAD_RXD'},'HARD BYPASS',FP['H2'],'TSW-102-07-G-S','Samtec',
       'Leave OPEN normally. Recovery only: remove U1 AND fit shunt -> direct copper body->head. Shunt is separate accessory SNT-100-BK-G',fields=[(78.74,160.02),(78.74,162.56)])
res(s,'R6',152.4,160.02,'10k','BODY_TXD','TAP_BODY',note='MCU USART0 RX tap on the body stream; limits clamp current when U1 is unpowered')
res(s,'R7',152.4,182.88,'10k','HEAD_TXD','TAP_HEAD',note='MCU USART1 RX tap on the head stream (logging); limits clamp current when U1 is unpowered')
s.comp('J5',CON4,203.2,170.18,{'1':'GND','2':'TAP_BODY','3':'TAP_HEAD','4':'HEAD_RXD'},'DATA TAPS',FP['H4'],'PRPC040SAAN-RC','Sullins',
       'Bench/test taps for a logic analyzer or USB-serial RX: 1 GND, 2 body->head (via R6 10k), 3 head->body (via R7 10k), 4 what the head receives (after R2 470R). Snapped from the 40-pin strip. Listen only: never connect an adapter TX or power',fields=[(203.2,157.48),(203.2,160.02)])
s.text(139.7,213.36,'HEAD_TXD -> BODY RX is direct copper (J2 pin 4 = J1 pin 4); the MCU only listens.\nBODY_TXD -> HEAD RX goes only through the MCU (full proxy): body bytes are received on TAP_BODY,\nbrightness packets rewritten, everything else forwarded byte-for-byte via R2. Head input has its own 47k pull-up,\nso it idles high while the MCU is in reset or being programmed. Recovery if U1 fails: pull U1 and fit JP1.')

# ================================================================ sheet 2
s=Sheet('02_power_mcu','02  PB supply and AVR128DB28','PB (body side) -> R1 -> filter -> LM2936 5 V -> AVR128DB28 (socketed). 32.768 kHz crystal for OSCHF auto-tune.')
res(s,'R1',63.5,50.8,'150R 1W','PB','PB_FILT',mpn='FMP100JR-52-150R',fp=FP['R1W'],note='5%, 1 W flameproof. Limits PB fault current (~67 mA into a short), RC-isolates MCU noise from PB, and doubles as board-current sense (V/150)')
s.comp('C6',CP,101.6,63.5,{'1':'PB_FILT','2':'GND'},'10uF 25V 105C',FP['CELEC'],'EEA-FC1E100','Panasonic','Radial aluminium, 105 C (behind the dash). EEA-FC1E100 is 4x7 mm with 1.5 mm lead pitch: spread the leads slightly into this 5 mm / 2.0 mm footprint. Any 10 uF >=25 V 105 C radial, 4-5 mm dia. 150R x 10uF ~ 106 Hz corner')
cap(s,'C5',127.0,63.5,'100nF 50V X7R','PB_FILT',mpn='C320C104K5R5TA',mfg='KEMET')
s.comp('U2',LDO,165.1,50.8,{'1':'+5V','2':'GND','3':'PB_FILT'},'LM2936Z-5.0',FP['TO92'],'LM2936Z-5.0/NOPB','Texas Instruments','TO-92 1=OUT 2=GND 3=IN. 40 V operating, 15 uA Iq. COUT >= 10 uF with 0.3-8 ohm ESR. Drop-in alt (same pinout): Diodes AP7381-50V-A',fields=[(165.1,40.64),(165.1,43.18)])
s.comp('C4',CP,203.2,63.5,{'1':'+5V','2':'GND'},'22uF 16V tantalum',FP['CTANT'],'T350F226K016AT','KEMET','Dipped tantalum, 6.0 mm dia, 2.54 mm pitch; ESR within LM2936 0.3-8 ohm stability window (also fine for alt U2 AP7381-50V-A)')
tp(s,'TP2',254.0,88.9,'GND')
flag(s,1,127.0,88.9,'PB_FILT'); flag(s,2,279.4,88.9,'GND')
mcu={'1':None,'2':'HEAD_TX_MCU','3':'TAP_HEAD','4':None,'5':None,'6':'+5V','7':'ILL_SENSE','8':None,'9':None,'10':None,
     '11':None,'12':None,'13':None,'14':'+5V','15':'GND','16':'XTAL32K1','17':'XTAL32K2','18':None,'19':'UPDI','20':'+5V','21':'GND',
     '22':'DBG_TX_MCU','23':'TAP_BODY','24':None,'25':None,'26':None,'27':None,'28':None}
s.comp('U1',MCU,101.6,170.18,mcu,'AVR128DB28-I/SP',FP['DIP28S'],'AVR128DB28-I/SP','Microchip','Socketed SPDIP-28. 5 V, internal OSCHF auto-tuned to XOSC32K',fields=[(119.38,134.62),(119.38,137.16)])
for r,(x,net) in zip(['C1','C2','C3'],[(203.2,'VDD pin 20'),(228.6,'AVDD pin 14'),(254.0,'VDDIO2 pin 6')]):
    cap(s,r,x,152.4,'100nF 50V X7R','+5V',mpn='C320C104K5R5TA',mfg='KEMET',note='Decoupling at U1 '+net)
s.comp('Y1',XTAL,215.9,190.5,{'1':'XTAL32K1','2':'XTAL32K2'},'32.768kHz 12.5pF',FP['XTAL'],'AB26T-32.768KHZ','Abracon','Through-hole long-lead variant (Rev A used AB26TRB, whose short formed leads barely reach). CL 12.5 pF, ESR 50k max (AVR XOSC32K limit 100k). Short traces, ground guard')
cap(s,'C7',203.2,215.9,'15pF C0G','XTAL32K1',mpn='C315C150J1G5TA',mfg='KEMET',note='Crystal load, C0G')
cap(s,'C8',228.6,215.9,'15pF C0G','XTAL32K2',mpn='C315C150J1G5TA',mfg='KEMET',note='Crystal load, C0G')
s.text(15.24,241.3,'Pin plan (AVR128DB28 SPDIP): USART0 PA1 RX <- TAP_BODY, PA0 TX -> DBG_TX (both at radio baud).\nUSART1 PC1 RX <- TAP_HEAD, PC0 TX -> HEAD_TX_MCU (proxy output to head). PD1 ILL_SENSE (low = lights on).\nAll other I/O unconnected (PA2-PA7, PC2-PC3, PD2-PD7); enable their internal pull-ups or disable input buffers. PF0/PF1 crystal.\nOSCHF accuracy is only +/-5% below 0 C without the crystal: enable XOSC32K auto-tune before using UARTs.\nSuggested clock 10 or 20 MHz (harmonics clear of 144-148 MHz). VDDIO2 tied to +5 V. RESET left on internal pull-up.')

# ================================================================ sheet 3
s=Sheet('03_ill_prog','03  ILL input and programming header','Isolated Toyota lights-on sense (ILL+ to chassis ground) and bench UPDI/debug header.')
s.comp('J3',CON2,50.8,63.5,{'1':'ILL_P','2':'ILL_GND'},'ILL+ / GND',FP['MF2'],'43045-0200','Molex',
       'Micro-Fit 3.0 2-circuit dual-row right-angle header, latching. Mates with 2-circuit receptacle 43025-0200 (pre-crimped 22 AWG leads are fine). Pin1 ILL+ (TAIL, R1-10), pin2 chassis GND (e.g. stereo harness ground). Optocoupler keeps truck wiring isolated from radio GND')
res(s,'R9',101.6,58.42,'2.2k','ILL_P','ILL_LED_A',mpn='MFR50SFTE52-2K2',fp=FP['R05W'],note='0.5 W metal film. ~5.4 mA at 13 V; 0.23 W at 24 V continuous; 40 V load-dump pulse 0.26 J/400 ms')
res(s,'R10',152.4,76.2,'680R','ILL_LED_A','ILL_GND',fp=FP['R762'],note='LED shunt: LED needs >~1.7 mA total input current, so leakage cannot half-turn-on the opto. Simulated')
s.comp('D1',DIODE,177.8,76.2,{'1':'ILL_LED_A','2':'ILL_GND'},'1N4148',FP['DO35'],'1N4148','onsemi','Antiparallel LED reverse protection (K=pin1 on ILL_LED_A)')
s.comp('U3',OPTO,228.6,63.5,{'1':'ILL_LED_A','2':'ILL_GND','3':'GND','4':'ILL_SENSE'},'SFH617A-3',FP['DIP4'],'SFH617A-3','Vishay',
       'CTR 100-200% @10 mA, >=34% @1 mA. Isolation: ILL side never touches board GND',fields=[(228.6,50.8),(228.6,53.34)])
res(s,'R11',279.4,50.8,'10k','+5V','ILL_SENSE',note='Opto pull-up; ILL_SENSE LOW while ILL+ is on (lights on)')
s.text(25.4,101.6,'Wire J3 to ILL+ (TAIL: 11-14 V with parking/head lights on, <1 V off) and a chassis ground.\nILL_SENSE: LOW = lights on (night brightness), HIGH = lights off (day brightness).\nKeep >= 2 mm clearance between ILL nets and all board nets.')
s.comp('J4',CON3,50.8,152.4,{'1':'GND','2':'UPDI','3':'DBG_TX'},'PROG/DEBUG',FP['H3'],'TSW-103-07-G-S','Samtec',
       '0.1 in header for bench programming/logging before the board goes behind the dash. UPDI Friend (or other 5 V SerialUPDI adapter): GND + UPDI. Logging: separate 5 V USB-serial RX on DBG_TX. Never connect adapter power')
res(s,'R13',127.0,154.94,'470R','DBG_TX_MCU','DBG_TX',note='Protects PA0 if a jumper or adapter TX lands on the DBG_TX pin')
s.text(25.4,203.2,'J4: 1 GND, 2 UPDI, 3 DBG_TX (MCU -> logging adapter RX). Board stays powered from the radio (PB) while programming.')
for i,(x,y) in enumerate([(254.0,152.4),(266.7,152.4),(279.4,152.4),(292.1,152.4)],1):
    s.comp('H'+str(i),HOLE,x,y,{},'M3',FP['HOLE'],assembly='PCB_FEATURE')


# ---------------------------------------------------------------- persist
for sh in SHEETS:
    sh.save()
used={k for sh in SHEETS for k in sh.used}
lib=node('kicad_symbol_lib',node('version',20250114),node('generator',Atom('kicad_symbol_editor')),*[SYMBOLS[k] for k in sorted(used)])
(HERE/(LIBNICK+'.kicad_sym')).write_text(dump(lib)+'\n')
(HERE/'sym-lib-table').write_text(f'(sym_lib_table (version 7) (lib (name "{LIBNICK}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIBNICK}.kicad_sym")(options "")(descr "Project-local symbols")))\n')
(HERE/'fp-lib-table').write_text(f'(fp_lib_table (version 7) (lib (name "{LIBNICK}")(type "KiCad")(uri "${{KIPRJMOD}}/footprints/{LIBNICK}.pretty")(options "")(descr "Project-local footprints")))\n')
root=node('kicad_sch',node('version',20250114),node('generator',Atom('eeschema')),node('generator_version','10.0'),node('uuid',ROOT_ID),node('paper','A3'),node('lib_symbols'),
          node('title_block',node('title','Kenwood TM-V71A proxy'),node('date','2026-11-15'),node('rev','B')))
root.append(node('text','KENWOOD TM-V71A PROXY - ELECTRICAL DRAFT\nFull-proxy day/night brightness proxy, PB powered, hand-assembled THT.\nOpen the three circuit sheets below.',node('at',25.4,20.32,0),fx(2.0,'left top'),node('uuid',uid('rootnote'))))
for i,sh in enumerate(SHEETS):
    x=25.4+i*127; y=68.58
    shn=node('sheet',node('at',x,y),node('size',104.14,30.48),node('stroke',node('width',0.1524),node('type',Atom('default'))),node('fill',node('color',0,0,0,0)),node('uuid',sh.uuid),
             prop('Sheetname',sh.title,x,y-2.54,False),prop('Sheetfile',sh.name+'.kicad_sch',x,y+33.02,False),
             node('instances',node('project',PROJECT,node('path','/'+ROOT_ID,node('page',str(i+2))))))
    for f in allof(shn,'property'):first(f,'effects').append(node('justify',Atom('left')))
    root.append(shn)
root.append(node('sheet_instances',node('path','/',node('page','1')))); root.append(node('embedded_fonts',Atom('no')))
(HERE/(PROJECT+'.kicad_sch')).write_text(dump(root)+'\n')
if not (HERE/(PROJECT+'.kicad_pro')).exists():
    (HERE/(PROJECT+'.kicad_pro')).write_text(json.dumps({'meta':{'filename':PROJECT+'.kicad_pro','version':1},'schematic':{'meta':{'version':1}},'text_variables':{'REVISION':'B'}},indent=2)+'\n')
(HERE/'design_intent.json').write_text(json.dumps(COMPONENTS,indent=2)+'\n')
print(f'Created {len(SHEETS)+1} native sheets, {len(COMPONENTS)} references (including power flags).')
