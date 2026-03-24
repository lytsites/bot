import html2canvas from 'html2canvas'
import JSZip from 'jszip'
import { formatTime } from '../time'

function sanitizeFilePart(value, fallback = 'dialog') {
  const cleaned = String(value || '')
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1f]+/g, '_')
    .replace(/\s+/g, ' ')
    .slice(0, 80)
  return cleaned || fallback
}

function nextFrame() {
  return new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  })
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob)
      else reject(new Error('EXPORT_CANVAS_EMPTY'))
    }, 'image/png')
  })
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function resolveColorValue(value, fallback = '') {
  if (!value) return fallback
  const probe = document.createElement('span')
  probe.style.color = String(value)
  document.body.appendChild(probe)
  const resolved = getComputedStyle(probe).color || fallback
  probe.remove()
  return resolved
}

function createMessageRow(message) {
  const outgoing = String(message?.direction || '').toUpperCase() !== 'IN'

  const row = document.createElement('div')
  row.style.display = 'flex'
  row.style.justifyContent = outgoing ? 'flex-end' : 'flex-start'
  row.style.marginBottom = '10px'
  row.style.width = '100%'
  row.style.boxSizing = 'border-box'
  row.style.pageBreakInside = 'avoid'

  const bubble = document.createElement('div')
  bubble.style.maxWidth = '78%'
  bubble.style.borderRadius = '18px'
  bubble.style.padding = '12px 14px 10px'
  bubble.style.background = outgoing ? 'rgb(56, 86, 170)' : 'rgb(45, 52, 67)'
  bubble.style.color = 'rgb(244, 247, 252)'
  bubble.style.fontSize = '14px'
  bubble.style.lineHeight = '1.4'
  bubble.style.whiteSpace = 'pre-wrap'
  bubble.style.wordBreak = 'break-word'
  bubble.style.boxSizing = 'border-box'
  bubble.style.border = outgoing ? '1px solid rgb(94, 126, 219)' : '1px solid rgb(66, 73, 91)'

  const text = document.createElement('div')
  text.textContent = String(message?.text || '')
  text.style.whiteSpace = 'pre-wrap'
  text.style.wordBreak = 'break-word'

  const meta = document.createElement('div')
  meta.textContent = formatTime(message?.created_at)
  meta.style.marginTop = '8px'
  meta.style.fontSize = '11px'
  meta.style.opacity = '0.82'
  meta.style.textAlign = outgoing ? 'right' : 'left'

  bubble.appendChild(text)
  bubble.appendChild(meta)
  row.appendChild(bubble)
  return row
}

function createPageShell(viewportWidth, viewportHeight, threadStyle) {
  const page = document.createElement('div')
  page.style.width = `${viewportWidth}px`
  page.style.height = `${viewportHeight}px`
  page.style.padding = '16px'
  page.style.boxSizing = 'border-box'
  page.style.overflow = 'hidden'
  page.style.borderRadius = '24px'
  page.style.background = 'rgb(24, 30, 43)'
  page.style.display = 'flex'
  page.style.flexDirection = 'column'
  page.style.gap = '0'

  const thread = document.createElement('div')
  thread.style.flex = '1'
  thread.style.minHeight = '0'
  thread.style.overflow = 'hidden'
  thread.style.borderRadius = threadStyle?.borderRadius || '20px'
  thread.style.padding = '16px'
  thread.style.boxSizing = 'border-box'
  thread.style.backgroundColor = threadStyle?.backgroundColor || 'rgb(32, 39, 54)'
  thread.style.backgroundImage = threadStyle?.backgroundImage || 'none'
  thread.style.backgroundSize = threadStyle?.backgroundSize || 'cover'
  thread.style.backgroundPosition = threadStyle?.backgroundPosition || 'center'
  thread.style.backgroundRepeat = threadStyle?.backgroundRepeat || 'no-repeat'
  thread.style.border = threadStyle?.border || '1px solid rgba(255,255,255,0.08)'
  thread.style.display = 'block'

  page.appendChild(thread)
  return { page, thread }
}

function buildPages({ messages, viewportWidth, viewportHeight, threadStyle }) {
  const host = document.createElement('div')
  host.style.position = 'fixed'
  host.style.left = '-100000px'
  host.style.top = '0'
  host.style.pointerEvents = 'none'
  host.style.opacity = '1'
  host.style.zIndex = '-1'
  document.body.appendChild(host)

  try {
    const pages = []
    let current = createPageShell(viewportWidth, viewportHeight, threadStyle)
    host.appendChild(current.page)
    pages.push(current.page)

    for (const message of messages) {
      const row = createMessageRow(message)
      current.thread.appendChild(row)
      if (current.thread.scrollHeight > current.thread.clientHeight && current.thread.childElementCount > 1) {
        current.thread.removeChild(row)
        current = createPageShell(viewportWidth, viewportHeight, threadStyle)
        host.appendChild(current.page)
        pages.push(current.page)
        current.thread.appendChild(row)
      }
    }

    return { host, pages }
  } catch (error) {
    host.remove()
    throw error
  }
}

export async function exportChatThreadAsZip({ messages, title, dialogId, viewportWidth, viewportHeight, threadEl }) {
  const items = Array.isArray(messages) ? messages : []
  if (!items.length) throw new Error('EXPORT_NO_MESSAGES')

  const safeWidth = Math.max(320, Math.round(viewportWidth || 360))
  const safeHeight = Math.max(420, Math.round(viewportHeight || 640))
  const scale = Math.min(window.devicePixelRatio || 1, 2)

  const computed = threadEl ? getComputedStyle(threadEl) : null
  const threadStyle = {
    backgroundColor: resolveColorValue(computed?.backgroundColor, 'rgb(32, 39, 54)'),
    backgroundImage: computed?.backgroundImage && computed.backgroundImage !== 'none' ? computed.backgroundImage : 'none',
    backgroundSize: computed?.backgroundSize || 'cover',
    backgroundPosition: computed?.backgroundPosition || 'center',
    backgroundRepeat: computed?.backgroundRepeat || 'no-repeat',
    borderRadius: computed?.borderRadius || '20px',
    border: computed
      ? `${computed.borderTopWidth || '1px'} ${computed.borderTopStyle || 'solid'} ${resolveColorValue(computed.borderTopColor, 'rgba(255,255,255,0.08)')}`
      : '1px solid rgba(255,255,255,0.08)',
  }

  const { host, pages } = buildPages({
    messages: items,
    viewportWidth: safeWidth,
    viewportHeight: safeHeight,
    threadStyle,
  })

  try {
    await nextFrame()

    const zip = new JSZip()
    const dialogPart = sanitizeFilePart(title, `dialog_${dialogId || 'export'}`)
    const baseName = `dialog_${String(dialogId || 'export')}_${dialogPart}`

    zip.file(
      `${baseName}/info.txt`,
      [
        `dialog_id=${dialogId ?? ''}`,
        `title=${title || ''}`,
        `screens=${pages.length}`,
        `viewport=${safeWidth}x${safeHeight}`,
      ].join('\n')
    )

    for (let pageIndex = 0; pageIndex < pages.length; pageIndex += 1) {
      const canvas = await html2canvas(pages[pageIndex], {
        backgroundColor: null,
        scale,
        useCORS: true,
        logging: false,
      })
      const blob = await canvasToBlob(canvas)
      zip.file(`${baseName}/screen_${String(pageIndex + 1).padStart(3, '0')}.png`, blob)
    }

    const archiveBlob = await zip.generateAsync({ type: 'blob' })
    triggerDownload(archiveBlob, `${baseName}.zip`)
    return { pageCount: pages.length }
  } finally {
    host.remove()
  }
}
