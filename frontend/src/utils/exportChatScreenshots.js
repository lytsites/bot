import html2canvas from 'html2canvas'
import JSZip from 'jszip'

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

export async function exportChatThreadAsZip({ threadEl, title, dialogId }) {
  if (!threadEl) throw new Error('EXPORT_THREAD_NOT_FOUND')

  const rect = threadEl.getBoundingClientRect()
  const viewportWidth = Math.max(320, Math.round(rect.width || threadEl.clientWidth || 360))
  const viewportHeight = Math.max(420, Math.round(rect.height || threadEl.clientHeight || 640))
  const contentHeight = Math.max(threadEl.scrollHeight || 0, threadEl.clientHeight || 0)
  const pageCount = Math.max(1, Math.ceil(contentHeight / viewportHeight))
  const scale = Math.min(window.devicePixelRatio || 1, 2)

  const host = document.createElement('div')
  host.style.position = 'fixed'
  host.style.left = '-100000px'
  host.style.top = '0'
  host.style.pointerEvents = 'none'
  host.style.opacity = '1'
  host.style.zIndex = '-1'

  const viewport = document.createElement('div')
  viewport.style.width = `${viewportWidth}px`
  viewport.style.height = `${viewportHeight}px`
  viewport.style.overflow = 'hidden'
  viewport.style.borderRadius = '24px'
  viewport.style.background = getComputedStyle(document.body).backgroundColor || '#0f1720'

  const clone = threadEl.cloneNode(true)
  clone.style.width = `${viewportWidth}px`
  clone.style.height = 'auto'
  clone.style.maxHeight = 'none'
  clone.style.minHeight = `${contentHeight}px`
  clone.style.overflow = 'visible'
  clone.style.transform = 'translateY(0)'

  viewport.appendChild(clone)
  host.appendChild(viewport)
  document.body.appendChild(host)

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
        `screens=${pageCount}`,
        `viewport=${viewportWidth}x${viewportHeight}`,
      ].join('\n')
    )

    for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) {
      const offset = pageIndex * viewportHeight
      clone.style.transform = `translateY(-${offset}px)`
      await nextFrame()
      const canvas = await html2canvas(viewport, {
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
    return { pageCount }
  } finally {
    host.remove()
  }
}
