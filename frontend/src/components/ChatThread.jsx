import React, { useEffect, useMemo, useRef } from 'react'
import { formatTime } from '../time'

function splitTripleBackticks(text) {
  const src = String(text || '').replace(/\r\n/g, '\n')
  const out = []
  let i = 0
  for (;;) {
    const start = src.indexOf('```', i)
    if (start === -1) {
      out.push({ type: 'text', value: src.slice(i) })
      break
    }
    const end = src.indexOf('```', start + 3)
    if (end === -1) {
      out.push({ type: 'text', value: src.slice(i) })
      break
    }
    out.push({ type: 'text', value: src.slice(i, start) })
    let code = src.slice(start + 3, end)
    if (code.startsWith('\n')) code = code.slice(1)
    let lang = null
    const nl = code.indexOf('\n')
    if (nl !== -1) {
      const first = code.slice(0, nl).trim()
      if (first && /^[a-zA-Z0-9+#._-]{1,20}$/.test(first)) {
        lang = first
        code = code.slice(nl + 1)
      }
    }
    out.push({ type: 'codeblock', code, lang })
    i = end + 3
  }
  return out.filter(p => (p.type === 'text' ? p.value !== '' : true))
}

function splitInlineCode(text) {
  const src = String(text || '')
  const out = []
  let i = 0
  for (;;) {
    const start = src.indexOf('`', i)
    if (start === -1) {
      out.push({ type: 'text', value: src.slice(i) })
      break
    }
    const end = src.indexOf('`', start + 1)
    if (end === -1) {
      out.push({ type: 'text', value: src.slice(i) })
      break
    }
    out.push({ type: 'text', value: src.slice(i, start) })
    out.push({ type: 'inlinecode', code: src.slice(start + 1, end) })
    i = end + 1
  }
  return out.filter(p => (p.type === 'text' ? p.value !== '' : true))
}

function splitUrls(text) {
  const src = String(text || '')
  const re = /https?:\/\/[^\s<>()]+/g
  const out = []
  let last = 0
  for (;;) {
    const m = re.exec(src)
    if (!m) break
    if (m.index > last) out.push({ type: 'text', value: src.slice(last, m.index) })
    let url = m[0]
    while (/[),.!?:;]$/.test(url)) url = url.slice(0, -1)
    out.push({ type: 'link', url })
    last = m.index + m[0].length
  }
  if (last < src.length) out.push({ type: 'text', value: src.slice(last) })
  return out.filter(p => (p.type === 'text' ? p.value !== '' : true))
}

function parseSimpleMarkup(text) {
  const src = String(text || '')
  const patterns = [
    { type: 'bold', re: /\*\*([\s\S]+?)\*\*/ },
    { type: 'strike', re: /~~([\s\S]+?)~~/ },
    { type: 'italic', re: /__([\s\S]+?)__/ },
    { type: 'italic', re: /\*([^\n*][\s\S]*?)\*/ },
    { type: 'italic', re: /_([^\n_][\s\S]*?)_/ },
  ]

  const out = []
  let rest = src
  let guard = 0
  while (rest && guard++ < 500) {
    let best = null
    for (const p of patterns) {
      const m = p.re.exec(rest)
      if (!m) continue
      if (best == null || m.index < best.index) {
        best = { type: p.type, index: m.index, raw: m[0], inner: m[1] }
      }
    }
    if (!best) {
      out.push({ type: 'text', value: rest })
      break
    }
    if (best.index > 0) out.push({ type: 'text', value: rest.slice(0, best.index) })
    out.push({ type: best.type, value: best.inner })
    rest = rest.slice(best.index + best.raw.length)
  }
  return out.filter(p => (p.type === 'text' ? p.value !== '' : true))
}

function RichText({ text }) {
  const blocks = useMemo(() => splitTripleBackticks(text), [text])

  return (
    <div className="chat-text">
      {blocks.map((b, bi) => {
        if (b.type === 'codeblock') {
          return (
            <pre className="chat-codeblock" key={`cb:${bi}`}>
              <code>{b.code}</code>
            </pre>
          )
        }

        const inline = splitInlineCode(b.value)
        return (
          <span key={`t:${bi}`}>
            {inline.map((p, pi) => {
              if (p.type === 'inlinecode') {
                return (
                  <code className="chat-inlinecode" key={`ic:${bi}:${pi}`}>
                    {p.code}
                  </code>
                )
              }

              const withUrls = splitUrls(p.value)
              return (
                <React.Fragment key={`u:${bi}:${pi}`}>
                  {withUrls.map((u, ui) => {
                    if (u.type === 'link') {
                      return (
                        <a
                          key={`lnk:${bi}:${pi}:${ui}`}
                          className="chat-link"
                          href={u.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {u.url}
                        </a>
                      )
                    }

                    const styled = parseSimpleMarkup(u.value)
                    return (
                      <React.Fragment key={`mk:${bi}:${pi}:${ui}`}>
                        {styled.map((s, si) => {
                          if (s.type === 'bold') return <strong key={`b:${si}`}>{s.value}</strong>
                          if (s.type === 'italic') return <em key={`i:${si}`}>{s.value}</em>
                          if (s.type === 'strike') return <s key={`s:${si}`}>{s.value}</s>
                          return <React.Fragment key={`t:${si}`}>{s.value}</React.Fragment>
                        })}
                      </React.Fragment>
                    )
                  })}
                </React.Fragment>
              )
            })}
          </span>
        )
      })}
    </div>
  )
}

function assignRef(target, value) {
  if (!target) return
  if (typeof target === 'function') {
    target(value)
    return
  }
  target.current = value
}

export default function ChatThread({ messages, threadRef = null, autoScroll = true }) {
  const listRef = useRef(null)
  const bottomRef = useRef(null)

  const items = useMemo(() => (Array.isArray(messages) ? messages : []), [messages])

  useEffect(() => {
    if (!autoScroll) return
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [autoScroll, items.length])

  useEffect(() => {
    assignRef(threadRef, listRef.current)
    return () => assignRef(threadRef, null)
  }, [threadRef])

  return (
    <div className="chat-thread" ref={listRef}>
      {items.map(m => {
        const outgoing = m?.direction !== 'IN'
        return (
          <div className={`chat-row ${outgoing ? 'out' : 'in'}`} key={m.id}>
            <div className={`chat-bubble ${outgoing ? 'out' : 'in'}`}>
              <RichText text={m?.text || ''} />
              <div className="chat-meta">{formatTime(m?.created_at)}</div>
            </div>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
