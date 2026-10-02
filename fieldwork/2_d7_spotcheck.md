# Step 2 — D7 spot-check: 20 figures, by you, against the PDF

Drawn at random from the **126 figures confirmed in bulk** with `--confirm-agreeing` (method "confirmed the agent's cited evidence").
Reproduce the draw: `random.Random("circuit-os-d7-spotcheck-2026-10-02").sample(sorted(pool), 20)`, where `pool` is every figure in `backend/data/figure_verifications.json` with that method. The draw was fixed before anyone looked at the figures, so no one picked the easy ones.

**Rules.** Open the document yourself and find the figure on the page. Do not read `figure_evidence.json` first: this sheet leaves out the agent's own reading on purpose. Mark each figure ✅ (the document says exactly this), ❌ (wrong value, wrong condition, wrong part, or a typical recorded as a guaranteed limit) or ❓ (can't find it). A ❓ counts against the confirmation, not for it.

**Decision rule, written before the check.** 0 ❌ and at most 1 ❓: the bulk confirmation stands, and you record the error rate (0/20, so the 95% upper bound is about 14%). Any ❌: the bulk confirmation is withdrawn, every figure it covered returns to unverified, and the D7 doubt returns to those claims. The fix is `--verify` figure by figure.

Record the result in `brain/decisions.md` with the counts, even if they're all ✅.

### 1. `STM32F411CEU6/gpio_recommended_current_ma`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 20 mA — inside the ±25 mA per-pin absolute maximum, where V_OH is specified
- **Value used:** `20   (from the table that owns it)` · kind: policy
- **Where to look:** p. 62, 101 — Table 12 Current characteristics; Output voltage characteristics
- **Document:** [STM32F411xC STM32F411xE datasheet (DS10314 Rev 8, January 2024 (downloaded 2026-10-02 through the user's Chrome))](https://www.st.com/resource/en/datasheet/stm32f411ce.pdf)
- **Your note:** 

### 2. `board:esp32_devkitc/GPIO2`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** GPIO2: output, input, PWM, ADC; strapping — boot mode — must be low or floating at reset for serial download; weak pull-down from reset until firmware sets the pin
- **Value used:** `{'name': 'GPIO2', 'firmware': '2', 'output': True, 'input': True, 'pwm': True, 'adc': True, 'uart': (), 'reserved': None, 'strapping': 'boot mode — must be low or floating at reset for serial download', 'note': None, 'reset_pull': 'down', 'reset_note': None}   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 69 (IO_MUX); 22–25 (strapping); 39 (LED PWM); 61–62 (pin-list notes); module 11–12; guide; schematic — series datasheet Appendix A.4 IO_MUX, §3 Boot Configurations, §4.8.8; module Table 3 notes; DevKitC V4 header J2/J3 and schematic
- **Document:** [ESP32 Series Datasheet (v5.3)](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- **Document:** [ESP32-WROOM-32E & ESP32-WROOM-32UE Datasheet (v2.1)](https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf)
- **Document:** [ESP32-DevKitC V4 User Guide (web page) (read 2026-09-25)](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)
- **Document:** [ESP32-DevKitC V4 schematic (downloaded 2026-09-30)](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_sch.pdf)
- **Your note:** 

### 3. `board:arduino_uno/A3`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** A3: output, input, ADC; high-impedance, no pull, from reset until firmware sets the pin
- **Value used:** `{'name': 'A3', 'firmware': 'A3', 'output': True, 'input': True, 'pwm': False, 'adc': True, 'uart': (), 'reserved': None, 'strapping': None, 'note': None, 'reset_pull': None, 'reset_note': None}   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 12, 85, 100–101 — Figure 1-1 pinout; §14.2.1 Configuring the Pin; §14.4 port registers; ArduinoCore-avr pin map; UNO Rev3 schematic
- **Document:** [ATmega48A/PA/88A/PA/168A/PA/328/P megaAVR Data Sheet (DS40002061B (2020))](https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf)
- **Document:** [ArduinoCore-avr variants/standard/pins_arduino.h (the Uno's pin map) (read 2026-09-30 by the recheck)](https://github.com/arduino/ArduinoCore-avr/blob/master/variants/standard/pins_arduino.h)
- **Document:** [UNO Rev3 schematic (A000066) and board pages (read 2026-09-30 by the recheck)](https://docs.arduino.cc/resources/schematics/A000066-schematics.pdf)
- **Your note:** 

### 4. `150080RS75000/max_continuous_current_ma`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 30 mA continuous forward current, absolute maximum
- **Value used:** `30   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 1 — Absolute Maximum Ratings
- **Document:** [150080RS75000 WL-SMCW SMT Mono-color Chip LED datasheet (003.000, 2022-05-20 (downloaded 2026-10-02))](https://www.we-online.com/components/products/datasheet/150080RS75000.pdf)
- **Your note:** 

### 5. `MAX485ECSA/current_draw_ma`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** no-load supply current with the driver disabled (DE = 0 V): 0.3 mA typical, 0.5 mA maximum
- **Value used:** `0.3   (from the table that owns it)` · kind: typical  — never trusted, even verified
- **Where to look:** p. 3 — DC Electrical Characteristics, supply current
- **Document:** [MAX481/MAX483/MAX485/MAX487–MAX491/MAX1487 datasheet (19-0122; Rev 10; 9/14 (downloaded 2026-10-02 through the user's Chrome))](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX1487-MAX491.pdf)
- **Your note:** 

### 6. `STM32F411CEU6/supply_model_ohm`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 132 Ω on 3.3 V is 25 mA — above the 24.4 mA maximum run current at 100 MHz from flash with all peripherals enabled (Table 23, V_DD = 3.6 V, 125 °C); 11.6 mA typical with them disabled
- **Value used:** `132.0   (from the table that owns it)` · kind: stated_assumption  — never trusted, even verified
- **Where to look:** p. 72 — Table 23 run mode from flash, ART accelerator enabled except prefetch, V_DD = 3.6 V
- **Document:** [STM32F411xC STM32F411xE datasheet (DS10314 Rev 8, January 2024 (downloaded 2026-10-02 through the user's Chrome))](https://www.st.com/resource/en/datasheet/stm32f411ce.pdf)
- **Your note:** 

### 7. `board:esp32_devkitc/GPIO8`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** GPIO8: output, input, PWM; reserved — the module's SPI flash inside the WROOM-32E, not led out: the DevKitC header positions for it reach unconnected pads; weak pull-up from reset until firmware sets the pin
- **Value used:** `{'name': 'GPIO8', 'firmware': '8', 'output': True, 'input': True, 'pwm': True, 'adc': False, 'uart': (), 'reserved': "the module's SPI flash inside the WROOM-32E, not led out: the DevKitC header positions for it reach unconnected pads", 'strapping': None, 'note': None, 'reset_pull': 'up', 'reset_note': None}   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 69 (IO_MUX); 22–25 (strapping); 39 (LED PWM); 61–62 (pin-list notes); module 11–12; guide; schematic — series datasheet Appendix A.4 IO_MUX, §3 Boot Configurations, §4.8.8; module Table 3 notes; DevKitC V4 header J2/J3 and schematic
- **Document:** [ESP32 Series Datasheet (v5.3)](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- **Document:** [ESP32-WROOM-32E & ESP32-WROOM-32UE Datasheet (v2.1)](https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf)
- **Document:** [ESP32-DevKitC V4 User Guide (web page) (read 2026-09-25)](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)
- **Document:** [ESP32-DevKitC V4 schematic (downloaded 2026-09-30)](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_sch.pdf)
- **Your note:** 

### 8. `board:arduino_uno/console_uart`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** the USB console occupies USART0
- **Value used:** `'USART0'   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 12; schematic — Figure 1-1 pinout; UNO Rev3 schematic and pages
- **Document:** [ATmega48A/PA/88A/PA/168A/PA/328/P megaAVR Data Sheet (DS40002061B (2020))](https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf)
- **Document:** [UNO Rev3 schematic (A000066) and board pages (read 2026-09-30 by the recheck)](https://docs.arduino.cc/resources/schematics/A000066-schematics.pdf)
- **Your note:** 

### 9. `board:arduino_uno/D10`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** D10: output, input, PWM; high-impedance, no pull, from reset until firmware sets the pin
- **Value used:** `{'name': 'D10', 'firmware': '10', 'output': True, 'input': True, 'pwm': True, 'adc': False, 'uart': (), 'reserved': None, 'strapping': None, 'note': None, 'reset_pull': None, 'reset_note': None}   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 12, 85, 100–101 — Figure 1-1 pinout; §14.2.1 Configuring the Pin; §14.4 port registers; ArduinoCore-avr pin map; UNO Rev3 schematic
- **Document:** [ATmega48A/PA/88A/PA/168A/PA/328/P megaAVR Data Sheet (DS40002061B (2020))](https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/ATmega48A-PA-88A-PA-168A-PA-328-P-DS-DS40002061B.pdf)
- **Document:** [ArduinoCore-avr variants/standard/pins_arduino.h (the Uno's pin map) (read 2026-09-30 by the recheck)](https://github.com/arduino/ArduinoCore-avr/blob/master/variants/standard/pins_arduino.h)
- **Document:** [UNO Rev3 schematic (A000066) and board pages (read 2026-09-30 by the recheck)](https://docs.arduino.cc/resources/schematics/A000066-schematics.pdf)
- **Your note:** 

### 10. `board:esp32_devkitc/console_uart`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** the USB console occupies UART0
- **Value used:** `'UART0'   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. schematic; guide; 69 — DevKitC V4 schematic, USB-UART section; IO_MUX
- **Document:** [ESP32-DevKitC V4 schematic (downloaded 2026-09-30)](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_sch.pdf)
- **Document:** [ESP32-DevKitC V4 User Guide (web page) (read 2026-09-25)](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)
- **Document:** [ESP32 Series Datasheet (v5.3)](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- **Your note:** 

### 11. `CL05B472KB5NNNC/tolerance`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 0402 X7R 4.7 nF, B = 50 V: tolerance letter K = ±10%
- **Value used:** `0.1   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. — — specification: capacitance, tolerance, rated voltage, TCC, size
- **Document:** [component library data sheet, CL05B472KB5NNN (web page) (read 2026-09-25)](https://weblib.samsungsem.com/mlcc/mlcc-ec-data-sheet.do?partNumber=CL05B472KB5NNN)
- **Your note:** 

### 12. `CL05B223KO5NNNC/voltage_max`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 0402 X7R 22 nF, O = 16 V: rated-voltage letter in the part number
- **Value used:** `16.0   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. — — specification: capacitance, tolerance, rated voltage, TCC, size
- **Document:** [component library data sheet, CL05B223KO5NNN (web page) (read 2026-09-25)](https://weblib.samsungsem.com/mlcc/mlcc-ec-data-sheet.do?partNumber=CL05B223KO5NNN)
- **Your note:** 

### 13. `MAX485ECSA/supply_voltage_min`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 4.75–5.25 V supply
- **Value used:** `4.75   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 2 — DC Electrical Characteristics, conditions
- **Document:** [MAX481/MAX483/MAX485/MAX487–MAX491/MAX1487 datasheet (19-0122; Rev 10; 9/14 (downloaded 2026-10-02 through the user's Chrome))](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX1487-MAX491.pdf)
- **Your note:** 

### 14. `CL05B472KB5NNNC/voltage_max`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 0402 X7R 4.7 nF, B = 50 V: rated-voltage letter in the part number
- **Value used:** `50.0   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. — — specification: capacitance, tolerance, rated voltage, TCC, size
- **Document:** [component library data sheet, CL05B472KB5NNN (web page) (read 2026-09-25)](https://weblib.samsungsem.com/mlcc/mlcc-ec-data-sheet.do?partNumber=CL05B472KB5NNN)
- **Your note:** 

### 15. `ESP32-WROOM-32E/gpio_recommended_current_ma`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 20 mA — the nominal (~20 mA) label of the default drive strength, not a guaranteed current
- **Value used:** `20   (from the table that owns it)` · kind: policy
- **Where to look:** p. 62 — notes on the ESP32 pin lists
- **Document:** [ESP32 Series Datasheet (v5.3)](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- **Your note:** 

### 16. `CL05B102KB5NNNC/voltage_max`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** 0402 X7R 1 nF, B = 50 V: rated-voltage letter in the part number
- **Value used:** `50.0   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. — — specification: capacitance, tolerance, rated voltage, TCC, size
- **Document:** [component library data sheet, CL05B102KB5NNN (web page) (read 2026-09-25)](https://weblib.samsungsem.com/mlcc/mlcc-ec-data-sheet.do?partNumber=CL05B102KB5NNN)
- **Your note:** 

### 17. `RC0603FR/tolerance`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** tolerance letter in the part number: F = ±1%
- **Value used:** `0.01   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 2 — ordering information — (2) tolerance
- **Document:** [General purpose chip resistors RC_L series, product specification (V.14, 2025-11-14)](https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L)
- **Your note:** 

### 18. `MAX3485ECSA/current_draw_ma`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** no-load supply current with the driver disabled (DE = 0 V, RE = 0 V): 0.95 mA typical, 1.9 mA maximum
- **Value used:** `0.95   (from the table that owns it)` · kind: typical  — never trusted, even verified
- **Where to look:** p. 3 — DC Electrical Characteristics, supply current
- **Document:** [MAX3483/MAX3485/MAX3486/MAX3488/MAX3490/MAX3491 datasheet (19-0333; Rev 2; 5/24 (downloaded 2026-10-02 through the user's Chrome))](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX3483-MAX3491.pdf)
- **Your note:** 

### 19. `board:esp32_devkitc/GPIO11`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** GPIO11: output, input, PWM; reserved — the module's SPI flash inside the WROOM-32E, not led out: the DevKitC header positions for it reach unconnected pads; weak pull-up from reset until firmware sets the pin
- **Value used:** `{'name': 'GPIO11', 'firmware': '11', 'output': True, 'input': True, 'pwm': True, 'adc': False, 'uart': (), 'reserved': "the module's SPI flash inside the WROOM-32E, not led out: the DevKitC header positions for it reach unconnected pads", 'strapping': None, 'note': None, 'reset_pull': 'up', 'reset_note': None}   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 69 (IO_MUX); 22–25 (strapping); 39 (LED PWM); 61–62 (pin-list notes); module 11–12; guide; schematic — series datasheet Appendix A.4 IO_MUX, §3 Boot Configurations, §4.8.8; module Table 3 notes; DevKitC V4 header J2/J3 and schematic
- **Document:** [ESP32 Series Datasheet (v5.3)](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- **Document:** [ESP32-WROOM-32E & ESP32-WROOM-32UE Datasheet (v2.1)](https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf)
- **Document:** [ESP32-DevKitC V4 User Guide (web page) (read 2026-09-25)](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html)
- **Document:** [ESP32-DevKitC V4 schematic (downloaded 2026-09-30)](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_sch.pdf)
- **Your note:** 

### 20. `RC0402FR/tolerance`  — ☐ ✅ ☐ ❌ ☐ ❓

- **Record says:** tolerance letter in the part number: F = ±1%
- **Value used:** `0.01   (from the table that owns it)` · kind: guaranteed_limit
- **Where to look:** p. 2 — ordering information — (2) tolerance
- **Document:** [General purpose chip resistors RC_L series, product specification (V.14, 2025-11-14)](https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L)
- **Your note:** 

---

**Tally:** ✅ ___ ❌ ___ ❓ ___ · checked by ______ on ______
