import React, { useMemo } from 'react'

function escapeRegex(s) {
  return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function parseKeywordsCsv(raw) {
  const s = String(raw || '')
  const parts = s
    .split(',')
    .map(x => x.trim())
    .filter(Boolean)
  // De-dupe case-insensitively, keep order.
  const seen = new Set()
  const out = []
  for (const p of parts) {
    const k = p.toLowerCase()
    if (seen.has(k)) continue
    seen.add(k)
    out.push(p)
  }
  return out
}

export default function KeywordHighlight({ text, keywords }) {
  const content = String(text ?? '')

  const kwList = useMemo(() => {
    return Array.isArray(keywords) ? keywords.filter(Boolean) : parseKeywordsCsv(keywords)
  }, [keywords])

  const nodes = useMemo(() => {
    if (!content) return ['']
    if (!kwList.length) return [content]

    const sorted = [...kwList].sort((a, b) => String(b).length - String(a).length)
    const pattern = sorted.map(escapeRegex).filter(Boolean).join('|')
    if (!pattern) return [content]

    let re
    try {
      // Whole word/phrase only (Unicode-aware): keyword 'сон' matches 'сон.' but NOT 'персонаж'
      // \b does not work well with Cyrillic in JS (it uses ASCII word chars), so we use Unicode property checks.
      re = new RegExp(`(?<![\\p{L}\\p{N}_])(${pattern})(?![\\p{L}\\p{N}_])`, 'giu')
    } catch {
      return [content]
    }

    const kwSet = new Set(sorted.map(k => String(k).toLowerCase()))
    const parts = content.split(re)
    const out = []
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      if (!part) continue
      const isHit = kwSet.has(part.toLowerCase())
      if (isHit) {
        out.push(
          <mark className="kw-hit" key={`kw-${i}`}>
            {part}
          </mark>
        )
      } else {
        out.push(<React.Fragment key={`tx-${i}`}>{part}</React.Fragment>)
      }
    }
    return out.length ? out : [content]
  }, [content, kwList])

  return <span className="msg-text">{nodes}</span>
}
