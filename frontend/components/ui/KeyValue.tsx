/**
 * KeyValue — label left in .t-label, value right in mono, on 28px hairline rows.
 *
 *   <KeyValueList>
 *     <KeyValue label="R1" value="1.59 kΩ" />
 *     <KeyValue label="Duration" value={<Qty value={412} unit="ms" />} />
 *     <KeyValue label="Signed by" value={email} mono={false} />
 *   </KeyValueList>
 *
 *   <Qty value="1.59" unit="kΩ" />   // number in mono, unit separated in --fg-3
 */
import type { ReactNode } from 'react'

export function KeyValueList({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <dl className={`kv ${className}`}>{children}</dl>
}

export function KeyValue({ label, value, mono = true, className = '' }: {
  label: ReactNode
  value: ReactNode
  mono?: boolean
  className?: string
}) {
  return (
    <div className={`kv-row ${className}`}>
      <dt className="t-label">{label}</dt>
      <dd className={mono ? 't-data' : 't-ui'}>{value}</dd>
    </div>
  )
}

/** A quantity: the number in mono (tabular), the unit in --fg-3. */
export function Qty({ value, unit, className = '' }: { value: ReactNode; unit?: string; className?: string }) {
  return (
    <span className={`t-data ${className}`}>
      {value}
      {unit && <span className="unit">{unit}</span>}
    </span>
  )
}
