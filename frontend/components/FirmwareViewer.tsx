'use client'

interface Props {
  firmware: string | null
}

export default function FirmwareViewer({ firmware }: Props) {
  if (!firmware) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        No firmware for this circuit type (passive circuits have no MCU code).
      </div>
    )
  }

  function handleDownload() {
    const blob = new Blob([firmware!], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'circuit_os_generated.ino'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <span className="text-xs text-muted font-mono">circuit_os_generated.ino</span>
        <button
          onClick={handleDownload}
          className="text-xs text-lavender hover:text-lavender-dim transition-colors"
        >
          Download .ino
        </button>
      </div>
      <pre className="flex-1 p-4 text-sm font-mono text-cream-dim overflow-auto leading-relaxed">
        {firmware}
      </pre>
    </div>
  )
}
