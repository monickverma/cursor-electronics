"""Q1 (2N2222A) on board_05: the transistor's junction bias as the board is actually wired,
and the coil current the relay needs.

Topology read off board_05.kicad_pcb (nets) and board_ir.json:
  U1 pin5 (PD3) --R2 1k-- RELAY_CTRL -- Q1 pin2 (BASE)
  Q1 pad1 (EMITTER)  -> RELAY_COIL_NEG -> K1 relay coil (70 ohm) -> K1 pin1 -> VCC_5V
  Q1 pad3 (COLLECTOR) -> GND
  D1 1N4007: anode RELAY_COIL_NEG, cathode VCC_5V
  2N2222A TO-92 pinout (KiCad Transistor_BJT.kicad_sym, Q_NPN_EBC): 1 = E, 2 = B, 3 = C
  SRD-05VDC-SL-C coil: 5 V / 70 ohm = 71.4 mA operating current

BJT model: Ebers-Moll (injection) form with the Early effect -- the form that is valid for
reverse-active operation, which is the regime the as-built board is in.
  cbe = IS*(exp(vbe/vt)-1)      cbc = IS*(exp(vbc/vt)-1)
  ic  = cbe/BF - cbc/BR  - cbc*(vbc-vbe)/VAF + cbe*(vbe-vbc)/VAR     (into the collector)
  ib  = cbe/BF + cbc/BR  + cbe*(vbe-vbc)/VAR + cbc*(vbc-vbe)/VAF     (into the base)
  ie  = -(ic + ib)                                                  (into the emitter)
  IS=1e-14 A, BF=250 (hFE), BR=6 (reverse gain), VAF=100 V, VAR=25 V
  Internal series resistances RB=RC=RE=0 (the 10 ohm internal base resistance moves the
  internal base voltage by 10*4.3 mA = 43 mV, which does not affect any conclusion here).
Signs: ib/ic/ie are currents INTO the device terminals.
"""
import math

VT = 0.025852
IS, BF, BR = 1e-14, 250.0, 6.0
RB, RC, RE = 0.0, 0.0, 0.0
VAF, VAR = 100.0, 25.0
R2, RCOIL, V5 = 1000.0, 70.0, 5.0


def expl(x):
    if x > 40.0:
        return math.exp(40.0)
    if x < -40.0:
        return math.exp(-40.0)
    return math.exp(x)


def bjt(vb, vc, ve):
    vbx, vcx, vex = vb, vc, ve
    ib = ic = ie = 0.0
    for _ in range(300):
        vbe, vbc = vbx - vex, vbx - vcx
        cbe = IS * (expl(vbe / VT) - 1.0)
        cbc = IS * (expl(vbc / VT) - 1.0)
        ice = cbe * (vbe - vbc) / VAR
        icc = cbc * (vbc - vbe) / VAF
        ic_n = cbe / BF - cbc / BR - icc + ice
        ib_n = cbe / BF + cbc / BR + ice + icc
        ie_n = -(ic_n + ib_n)
        dv = abs(ic_n - ic) + abs(ib_n - ib) + abs(ie_n - ie)
        ic, ib, ie = ic_n, ib_n, ie_n
        vbx, vcx, vex = vb - ib * RB, vc - ic * RC, ve - ie * RE
        if dv < 1e-13:
            break
    return ib, ic, ie


def bisect(f, lo, hi, iters=200):
    flo = f(lo)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


print("=" * 78)
print("A. AS BUILT ON THE BOARD  (pad1=Emitter->coil, pad3=Collector->GND)")
print("=" * 78)
# The emitter node is fed only by the relay coil from +5 V.  The B-E junction cannot be
# forward biased (that would need V_B > V_E + 0.6 with V_E ~ 5 V, impossible through 1 k),
# so cbe ~ 0 and the Ebers-Moll equations give I_E = -(I_C + I_B) = 0: the emitter, and
# therefore the coil, carries no current.  The base node settles where the B-C junction
# (now the forward-biased one) draws the base current supplied through R2.
def base_f(vb):
    ib, ic, ie = bjt(vb, 0.0, V5)          # collector at GND, emitter at the coil (5 V)
    return (V5 - vb) / R2 - ib


vb = bisect(base_f, 0.40, 1.60)
ib, ic, ie = bjt(vb, 0.0, V5)
icoil = (V5 - V5) / RCOIL + ie            # all emitter current passes through the coil
print("   V(base)            = %+.4f V" % vb)
print("   V(coil low side)   = %+.4f V   (emitter floats to the +5 V rail)" % V5)
print("   V_BE               = %+.4f V   REVERSE biased (2N2222A V_EBO max 5 V)" % (vb - V5))
print("   V_BC               = %+.4f V   forward biased -> base current dumped to GND" % (vb - 0.0))
print("   I(base)            = %+.4f mA   (=(5-Vb)/R2, all of it through B-C into GND)" % (ib * 1e3))
print("   I(collector)       = %+.4f mA" % (ic * 1e3))
print("   I(emitter)         = %+.4f mA   <-- the coil current" % (ie * 1e3))
print("   I(coil)            = %+.4f mA   (SRD-05VDC-SL-C needs 71.4 mA to pick up)" % (icoil * 1e3))
print("   V_EBO stress       = %+.4f V    (2N2222A V_EBO max = 5 V)" % (V5 - vb))
print("   VERDICT            = relay DOES NOT PULL IN")
print()

print("   Bound (model-independent): the base current is capped by R2 at %.1f mA."
      % ((V5 - 0.0) / R2 * 1e3))
print("   In this reversed junction configuration the gain is BR (reverse gain, a few")
print("   to ten for a small-signal NPN), not BF (100-300).  So the coil can see at most")
print("   BR * I_B = %d * %.1f mA = %.1f mA, against the 71.4 mA the coil needs."
      % (BR, ib * 1e3, BR * ib * 1e3))
print("   The design's function depends on a parameter the datasheet does not specify,")
print("   and even at BR = %d the relay still does not pull in." % BR)
print()

print("=" * 78)
print("B. SAME PARTS, CORRECT LOW-SIDE WIRING (pad3=Collector->coil, pad1=Emitter->GND)")
print("=" * 78)
# Analytical: the coil is a 70 ohm resistor across 5 V.  The base gets (5-0.7)/1k.
vbe_on = 0.7
ib_corr = (V5 - vbe_on) / R2
icoil_corr = V5 / RCOIL
print("   I(coil)            = %+.4f mA   (5 V across 70 ohm)" % (icoil_corr * 1e3))
print("   I(base)            = %+.4f mA   ((5 - 0.7)/1k)" % (ib_corr * 1e3))
print("   forced beta        = %.1f       (2N2222A forced beta is typically 50-100)" % (icoil_corr / ib_corr))
print("   VERDICT            = relay PULLS IN (transistor saturates)")
print()
print("=" * 78)
print("SUMMARY: identical parts, identical netlist except which pad carries the coil.")
print("As built, the relay coil carries %.4f mA.  Correctly wired it carries %.1f mA."
      % (icoil * 1e3, icoil_corr * 1e3))
print("=" * 78)
