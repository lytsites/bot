import JSZip from 'jszip'
import { formatTime } from '../time'

const DEFAULT_VIEWPORT_WIDTH = 420
const DEFAULT_VIEWPORT_HEIGHT = 760
const SIDE_PADDING = 12
const TOP_PADDING = 14
const BOTTOM_PADDING = 14
const MESSAGE_GAP = 10
const BUBBLE_PADDING_X = 12
const BUBBLE_PADDING_TOP = 10
const BUBBLE_PADDING_BOTTOM = 8
const BUBBLE_RADIUS = 18
const MAX_BUBBLE_RATIO = 0.78
const TEXT_FONT_SIZE = 14
const META_FONT_SIZE = 11
const TEXT_LINE_HEIGHT = 19
const META_LINE_HEIGHT = 14
const BUBBLE_BORDER_WIDTH = 1
const SCREENSHOT_SCALE = 2

function sanitizeFilePart(value) {
  return String(value || 'dialog')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 80) || 'dialog'
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1500)
}

function extractUrl(backgroundImage) {
  if (!backgroundImage || backgroundImage === 'none') return ''
  const match = backgroundImage.match(/url\((['"]?)(.*?)\1\)/i)
  return match?.[2] || ''
}

function resolveColor(value, fallback) {
  if (!value || value === 'transparent') return fallback
  const probe = document.createElement('div')
  probe.style.color = value
  probe.style.position = 'fixed'
  probe.style.opacity = '0'
  probe.style.pointerEvents = 'none'
  document.body.appendChild(probe)
  const resolved = window.getComputedStyle(probe).color || fallback
  probe.remove()
  return resolved || fallback
}

function colorWithAlpha(color, alpha) {
  const match = String(color || '').match(/rgba?\(([^)]+)\)/i)
  if (!match) return color
  const parts = match[1]
    .split(',')
    .map(part => part.trim())
    .slice(0, 3)
  return `rgba(${parts.join(', ')}, ${alpha})`
}

function parsePx(value, fallback = 0) {
  const n = Number.parseFloat(value)
  return Number.isFinite(n) ? n : fallback
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    if (!url) {
      resolve(null)
      return
    }
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`IMAGE_LOAD_FAILED:${url}`))
    img.src = url
  })
}

function drawRoundedRect(ctx, x, y, width, height, radius, fillStyle, strokeStyle, strokeWidth = 0) {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2))
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + width, y, x + width, y + height, r)
  ctx.arcTo(x + width, y + height, x, y + height, r)
  ctx.arcTo(x, y + height, x, y, r)
  ctx.arcTo(x, y, x + width, y, r)
  ctx.closePath()
  if (fillStyle) {
    ctx.fillStyle = fillStyle
    ctx.fill()
  }
  if (strokeStyle && strokeWidth > 0) {
    ctx.lineWidth = strokeWidth
    ctx.strokeStyle = strokeStyle
    ctx.stroke()
  }
}

function drawCoverImage(ctx, image, x, y, width, height) {
  if (!image) return
  const scale = Math.max(width / image.width, height / image.height)
  const drawWidth = image.width * scale
  const drawHeight = image.height * scale
  const dx = x + (width - drawWidth) / 2
  const dy = y + (height - drawHeight) / 2
  ctx.drawImage(image, dx, dy, drawWidth, drawHeight)
}

function wrapText(ctx, text, maxWidth) {
  const source = String(text || '').replace(/\r\n/g, '\n')
  const paragraphs = source.split('\n')
  const lines = []

  paragraphs.forEach((paragraph, index) => {
    const words = paragraph.split(/\s+/).filter(Boolean)
    if (!words.length) {
      lines.push('')
      return
    }
    let current = words[0]
    for (let i = 1; i < words.length; i += 1) {
      const candidate = `${current} ${words[i]}`
      if (ctx.measureText(candidate).width <= maxWidth) {
        current = candidate
        continue
      }
      if (ctx.measureText(words[i]).width > maxWidth) {
        let chunk = ''
        for (const char of words[i]) {
          const nextChunk = chunk + char
          if (chunk && ctx.measureText(nextChunk).width > maxWidth) {
            lines.push(current)
            current = chunk
            chunk = char
          } else {
            chunk = nextChunk
          }
        }
        if (chunk) {
          lines.push(current)
          current = chunk
        }
      } else {
        lines.push(current)
        current = words[i]
      }
    }
    lines.push(current)
    if (index < paragraphs.length - 1) lines.push('')
  })

  return lines.length ? lines : ['']
}

function sampleTheme(threadEl) {
  const threadStyle = window.getComputedStyle(threadEl)
  const inBubble = threadEl.querySelector('.chat-bubble.in')
  const outBubble = threadEl.querySelector('.chat-bubble.out')
  const textEl = threadEl.querySelector('.chat-text')
  const metaEl = threadEl.querySelector('.chat-meta')
  const inStyle = inBubble ? window.getComputedStyle(inBubble) : null
  const outStyle = outBubble ? window.getComputedStyle(outBubble) : null
  const textStyle = textEl ? window.getComputedStyle(textEl) : null
  const metaStyle = metaEl ? window.getComputedStyle(metaEl) : null

  return {
    threadBackgroundColor: resolveColor(threadStyle.backgroundColor, 'rgb(23, 27, 36)'),
    threadBorderColor: resolveColor(threadStyle.borderColor, 'rgba(43, 52, 69, 0.7)'),
    threadRadius: parsePx(threadStyle.borderRadius, 18),
    threadPaddingLeft: parsePx(threadStyle.paddingLeft, SIDE_PADDING),
    threadPaddingRight: parsePx(threadStyle.paddingRight, SIDE_PADDING),
    threadPaddingTop: parsePx(threadStyle.paddingTop, TOP_PADDING),
    threadPaddingBottom: parsePx(threadStyle.paddingBottom, BOTTOM_PADDING),
    threadBackgroundImage: extractUrl(threadStyle.backgroundImage),
    inBubbleColor: resolveColor(inStyle?.backgroundColor, 'rgba(23, 27, 36, 0.78)'),
    outBubbleColor: resolveColor(outStyle?.backgroundColor, 'rgba(106, 139, 255, 0.26)'),
    bubbleBorderColor: resolveColor(inStyle?.borderColor || outStyle?.borderColor, 'rgba(43, 52, 69, 0.7)'),
    textColor: resolveColor(textStyle?.color, 'rgb(238, 242, 255)'),
    metaColor: resolveColor(metaStyle?.color, 'rgba(166, 176, 195, 0.9)'),
    fontFamily: textStyle?.fontFamily || "'Manrope', sans-serif",
    metaFontFamily: metaStyle?.fontFamily || textStyle?.fontFamily || "'Manrope', sans-serif",
  }
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return []
  return messages.map((message, index) => ({
    id: message?.id ?? index + 1,
    direction: message?.direction === 'IN' ? 'IN' : 'OUT',
    text: String(message?.text || ''),
    time: formatTime(message?.created_at),
  }))
}

function buildLayout(messages, viewportWidth, theme) {
  const maxBubbleWidth = Math.max(180, (viewportWidth - theme.threadPaddingLeft - theme.threadPaddingRight) * MAX_BUBBLE_RATIO)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const items = []
  let currentY = theme.threadPaddingTop

  for (const message of messages) {
    ctx.font = `${TEXT_FONT_SIZE}px ${theme.fontFamily}`
    const textLines = wrapText(ctx, message.text, maxBubbleWidth - BUBBLE_PADDING_X * 2)
    const textWidth = textLines.reduce((max, line) => Math.max(max, ctx.measureText(line || ' ').width), 0)
    ctx.font = `${META_FONT_SIZE}px ${theme.metaFontFamily}`
    const timeWidth = ctx.measureText(message.time || '').width

    const bubbleWidth = Math.min(
      maxBubbleWidth,
      Math.max(textWidth + BUBBLE_PADDING_X * 2, timeWidth + BUBBLE_PADDING_X * 2, 96),
    )
    const textHeight = textLines.length * TEXT_LINE_HEIGHT
    const bubbleHeight = BUBBLE_PADDING_TOP + textHeight + 6 + META_LINE_HEIGHT + BUBBLE_PADDING_BOTTOM
    const x = message.direction === 'IN'
      ? theme.threadPaddingLeft
      : viewportWidth - theme.threadPaddingRight - bubbleWidth

    items.push({
      ...message,
      x,
      y: currentY,
      width: bubbleWidth,
      height: bubbleHeight,
      textLines,
    })

    currentY += bubbleHeight + MESSAGE_GAP
  }

  return {
    items,
    contentHeight: Math.max(currentY - MESSAGE_GAP + theme.threadPaddingBottom, theme.threadPaddingTop + theme.threadPaddingBottom),
  }
}

function drawMessage(ctx, item, pageOffsetY, theme) {
  const drawY = item.y - pageOffsetY
  drawRoundedRect(
    ctx,
    item.x,
    drawY,
    item.width,
    item.height,
    BUBBLE_RADIUS,
    item.direction === 'IN' ? theme.inBubbleColor : theme.outBubbleColor,
    theme.bubbleBorderColor,
    BUBBLE_BORDER_WIDTH,
  )

  ctx.fillStyle = theme.textColor
  ctx.font = `${TEXT_FONT_SIZE}px ${theme.fontFamily}`
  ctx.textBaseline = 'top'
  let textY = drawY + BUBBLE_PADDING_TOP
  for (const line of item.textLines) {
    ctx.fillText(line || ' ', item.x + BUBBLE_PADDING_X, textY)
    textY += TEXT_LINE_HEIGHT
  }

  ctx.fillStyle = theme.metaColor
  ctx.font = `${META_FONT_SIZE}px ${theme.metaFontFamily}`
  ctx.textBaseline = 'alphabetic'
  const timeY = drawY + item.height - BUBBLE_PADDING_BOTTOM
  const timeWidth = ctx.measureText(item.time || '').width
  const timeX = item.direction === 'IN'
    ? item.x + BUBBLE_PADDING_X
    : item.x + item.width - BUBBLE_PADDING_X - timeWidth
  ctx.fillText(item.time || '', timeX, timeY)
}

async function renderPages({ viewportWidth, viewportHeight, layout, theme, backgroundImage }) {
  const pageCount = Math.max(1, Math.ceil(layout.contentHeight / viewportHeight))
  const pages = []

  for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) {
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(viewportWidth * SCREENSHOT_SCALE)
    canvas.height = Math.round(viewportHeight * SCREENSHOT_SCALE)
    const ctx = canvas.getContext('2d')
    ctx.scale(SCREENSHOT_SCALE, SCREENSHOT_SCALE)

    drawRoundedRect(
      ctx,
      0,
      0,
      viewportWidth,
      viewportHeight,
      theme.threadRadius,
      theme.threadBackgroundColor,
      theme.threadBorderColor,
      1,
    )

    ctx.save()
    drawRoundedRect(ctx, 0, 0, viewportWidth, viewportHeight, theme.threadRadius, null, null, 0)
    ctx.clip()
    drawCoverImage(ctx, backgroundImage, 0, 0, viewportWidth, viewportHeight)
    ctx.fillStyle = colorWithAlpha(theme.threadBackgroundColor, 0.55)
    ctx.fillRect(0, 0, viewportWidth, viewportHeight)

    const pageStart = pageIndex * viewportHeight
    const pageEnd = pageStart + viewportHeight
    for (const item of layout.items) {
      if (item.y + item.height < pageStart || item.y > pageEnd) continue
      drawMessage(ctx, item, pageStart, theme)
    }
    ctx.restore()

    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('PNG_EXPORT_FAILED')
    pages.push(blob)
  }

  return pages
}

export async function exportChatThreadAsZip({
  messages,
  title,
  dialogId,
  viewportWidth,
  viewportHeight,
  threadEl,
}) {
  if (!threadEl) throw new Error('CHAT_THREAD_NOT_FOUND')
  const normalizedMessages = normalizeMessages(messages)
  if (!normalizedMessages.length) throw new Error('DIALOG_IS_EMPTY')

  const finalViewportWidth = Math.max(320, Math.round(viewportWidth || threadEl.clientWidth || DEFAULT_VIEWPORT_WIDTH))
  const finalViewportHeight = Math.max(480, Math.round(viewportHeight || threadEl.clientHeight || DEFAULT_VIEWPORT_HEIGHT))
  const theme = sampleTheme(threadEl)
  const backgroundUrl = theme.threadBackgroundImage
    ? new URL(theme.threadBackgroundImage, window.location.href).toString()
    : ''
  const backgroundImage = await loadImage(backgroundUrl).catch(() => null)
  const layout = buildLayout(normalizedMessages, finalViewportWidth, theme)
  const pages = await renderPages({
    viewportWidth: finalViewportWidth,
    viewportHeight: finalViewportHeight,
    layout,
    theme,
    backgroundImage,
  })

  const zip = new JSZip()
  const baseName = sanitizeFilePart(`${title || 'dialog'}_${dialogId || 'export'}`)

  pages.forEach((blob, index) => {
    zip.file(`${baseName}_${String(index + 1).padStart(3, '0')}.png`, blob)
  })

  zip.file(
    'info.txt',
    [
      `dialog_id: ${dialogId ?? ''}`,
      `title: ${title || ''}`,
      `screens: ${pages.length}`,
      `viewport: ${finalViewportWidth}x${finalViewportHeight}`,
      `exported_at: ${new Date().toISOString()}`,
    ].join('\n'),
  )

  const archive = await zip.generateAsync({ type: 'blob' })
  triggerDownload(archive, `${baseName}.zip`)
  return { pageCount: pages.length }
}
