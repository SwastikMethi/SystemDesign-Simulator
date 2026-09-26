import { useLayoutEffect, useRef, type ReactNode, type RefObject } from 'react'

export function Dialog({ label, onClose, className = '', returnFocus, children }: { label: string; onClose: () => void; className?: string; returnFocus?: RefObject<HTMLButtonElement | null>; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useLayoutEffect(() => {
    const dialog = ref.current!
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialog.showModal()
    return () => { dialog.close(); if (opener?.isConnected && opener !== document.body) opener.focus(); else returnFocus?.current?.focus() }
  }, [])
  return <dialog ref={ref} className={`modal ${className}`} aria-label={label} onCancel={event => { event.preventDefault(); onClose() }} onKeyDown={event => {
    if (event.key !== 'Tab') return
    // Keep the boundary inside the dialog; native Tab may otherwise visit browser chrome.
    const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:enabled, input:enabled, select:enabled, textarea:enabled, a[href], summary, [tabindex]')].filter(element => element.tabIndex >= 0 && element.getClientRects().length)
    const first = controls[0], last = controls.at(-1)
    if (event.shiftKey ? document.activeElement === first : document.activeElement === last) {
      event.preventDefault(); (event.shiftKey ? last : first)?.focus()
    }
  }}>{children}</dialog>
}
