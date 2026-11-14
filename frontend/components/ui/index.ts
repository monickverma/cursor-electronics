/**
 * Circuit OS UI primitives (spec §4). Import from '@/components/ui'.
 * Read the comment at the top of each file for usage. CSS classes live in app/globals.css
 * (`@layer components`): .btn*, .chip*, .grade, .sheet-*, .section*, .callout*, .kv*, .dt (tables),
 * .input/.textarea/.select, .kbd, .cursor-blink, .empty*, .rule-grid, .prose, and the type classes
 * .t-label / .t-ui / .t-small / .t-data / .t-title / .t-display.
 */
export { Button, buttonClass, ICON } from './Button'
export type { ButtonProps, ButtonVariant, ButtonSize } from './Button'
export { VerdictBadge, GradeChip } from './VerdictBadge'
export { Chip } from './Chip'
export { SheetFrame, SheetHeader, SheetContext, useSheet } from './SheetFrame'
export type { SheetInfo, SheetFrameProps } from './SheetFrame'
export { Section } from './Section'
export { Callout } from './Callout'
export type { CalloutTone } from './Callout'
export { KeyValue, KeyValueList, Qty } from './KeyValue'
export { Field, Input, Textarea } from './Field'
export { EmptyState, Kbd, Cursor, CopyButton } from './Small'
export { Prose, parseBlocks, renderInline } from './Prose'
export { VERDICTS, TONE_GLYPH, verdictMeta, propertyTone, firmwareTone } from './verdict'
export type { Tone, ToneOrNeutral, VerdictMeta } from './verdict'
