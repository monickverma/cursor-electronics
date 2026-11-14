/**
 * The drawing set: seven numbered sheets. Numbers are fixed — when the PCB sheet is hidden
 * (the engine is off), the set reads 00, 01, 03 … as a real drawing set would.
 * `label` is the sheet tab's accessible name; e2e tests click tabs by exactly these names.
 */
export type SheetId = 'overview' | 'schematic' | 'pcb' | 'firmware' | 'simulation' | 'bom' | 'validation'

export interface SheetDef {
  id: SheetId
  number: string
  /** Exact accessible name of the tab. Do not reword. */
  label: string
  /** Title shown in the sheet header. */
  title: string
  /** One line on what the sheet will contain (the empty workbench's index). */
  about: string
}

export const SHEETS: SheetDef[] = [
  {
    id: 'overview', number: '00', label: 'Overview', title: 'Overview',
    about: 'The compile report: claims counted by verdict, the grade floor, each stage of the pipeline, and why each part was chosen.',
  },
  {
    id: 'schematic', number: '01', label: 'Schematic', title: 'Schematic',
    about: 'The KiCad schematic the compiler wrote from the IR, connected by net labels, with its source.',
  },
  {
    id: 'pcb', number: '02', label: 'PCB (experimental)', title: 'PCB — experimental',
    about: 'An experimental placement and route in 2D and 3D, with the board verifier’s findings. Outside the v0.1.0 gate.',
  },
  {
    id: 'firmware', number: '03', label: 'Firmware', title: 'Firmware',
    about: 'The sketch and PlatformIO project for the design’s board — shown only once it compiles.',
  },
  {
    id: 'simulation', number: '04', label: 'Simulation', title: 'Simulation',
    about: 'The ngspice run, graded against the requirement: operating point, sweeps and transients.',
  },
  {
    id: 'bom', number: '05', label: 'BOM', title: 'Bill of materials',
    about: 'Every part with a dated price and its source, totals per currency, and substitutes re-checked before they are offered.',
  },
  {
    id: 'validation', number: '06', label: 'Validation', title: 'Validation',
    about: 'Rule results, every claim with its verdict and grade — a check that was not run is printed as not assessed — and proved properties to sign.',
  },
]

export const SHEET_BY_ID: Record<SheetId, SheetDef> =
  Object.fromEntries(SHEETS.map(s => [s.id, s])) as Record<SheetId, SheetDef>
