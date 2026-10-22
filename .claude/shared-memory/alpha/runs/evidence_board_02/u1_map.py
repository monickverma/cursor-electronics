"""Map the physical ATmega328P-PU pin onto the holes of the board's DIP-28 footprint.

The product's U1 footprint is a Y-MIRROR of KiCad's stock DIP-28_W7.62mm (proved by
dip_check.py). A DIP-28 chip can only be inserted one way up: pin 1 sits in the
corner nearest the notch/dot, at the same end as pin 28. The file's pad 1 and pad 28
are at that end, so the notch end is right -- but the left/right order is reversed,
so the chip's pin N lands in the hole the file labels 15-N (left column) or 43-N
(right column). This script prints the resulting net-to-die-pin map.
"""
import json
import os

EV = r"C:\Users\KIIT\cursor-electronics\.claude\shared-memory\alpha\runs\evidence_board_02"
d = json.load(open(os.path.join(EV, "connectivity_analysis.json"), encoding="utf-8"))
pads = {p["ref"] + "." + p["num"]: p for p in d["pads"]}

U1 = {int(k.split(".")[1]): v for k, v in pads.items() if v["ref"] == "U1"}
print("U1 footprint record:", [f for f in d["footprints"] if f["ref"] == "U1"])

# ATmega328P-PU (DIP-28) pin functions, from the Microchip datasheet:
# 1 PC6/RESET 2 PD1 3 PD2 4 PD3 5 PD4 6 PD5 7 VCC 8 GND 9 PB6/XTAL1 10 PB7/XTAL2
# 11 PD5 12 PD6 13 PD7 14 PB0 15 PB1 16 PB2 17 PB3 18 PB4 19 PB5 20 AVCC
# 21 AREF 22 GND 23 PC0 24 PC1 25 PC2 26 PC3 27 PC4 28 PC5
ATMEGA = {
    1: "PC6/RESET", 2: "PD1", 3: "PD2", 4: "PD3", 5: "PD4", 6: "PD5",
    7: "VCC", 8: "GND", 9: "PB6/XTAL1", 10: "PB7/XTAL2",
    11: "PD5", 12: "PD6", 13: "PD7", 14: "PB0", 15: "PB1", 16: "PB2",
    17: "PB3", 18: "PB4", 19: "PB5", 20: "AVCC", 21: "AREF", 22: "GND",
    23: "PC0", 24: "PC1", 25: "PC2", 26: "PC3", 27: "PC4", 28: "PC5",
}


def chip_pin_in_hole(n):
    """Physical ATmega pin that lands in the board hole the file labels n.

    The footprint is Y-mirrored (dip_check.py). The die's pin 1 sits LEFT of the
    notch in the stock orientation, so with the notch at this board's pad-1/pad-28
    end the die's pin 1 lands in the hole the file labels 28, and the die's pin 28
    lands in the hole the file labels 1.  Hence 29 - n.
    """
    return 29 - n


print("\nU1 holes, sorted by board position (KiCad board y grows downward):")
for num in sorted(U1, key=lambda k: (U1[k]["y"], U1[k]["x"])):
    p = U1[num]
    print("  pad %-2d  x=%6.2f y=%6.2f  net=%s" % (num, p["x"], p["y"], p["net"] or "NONE"))

print("\n=== what the die actually sees if the chip is soldered as drawn ===")
bad = []
for num in sorted(U1):
    p = U1[num]
    c = chip_pin_in_hole(num)
    fn = ATMEGA.get(c, "?")
    flag = ""
    if p["net"] == "VCC_5V" and fn in ("GND",):
        flag = "  <<< 5 V on the die's GND pin"
    if p["net"] == "GND" and fn == "VCC":
        flag = "  <<< 0 V on the die's VCC pin"
    if p["net"] and fn in ("XTAL1", "XTAL2", "PB7/XTAL2", "PB6/XTAL1"):
        flag = "  <<< net on a crystal pin"
    if p["net"] and flag:
        bad.append((num, p["net"], c, fn))
    print("  board pad %-2d (net %-16s) <- ATmega pin %-2d (%s)%s"
          % (num, p["net"] or "NONE", c, fn, flag))

print("\ncritical miswirings:")
for b in bad:
    print("   pad %-2d net %-8s -> die pin %-2d (%s)" % b)
