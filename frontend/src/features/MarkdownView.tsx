// Markdown 笔记渲染：marked → 消毒 → 标题锚点 → KaTeX 公式。
// markdown-v2 起笔记源真值就是 Markdown；全部本地打包，运行时零 CDN。
import { useMemo } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import katex from 'katex'
import 'katex/dist/katex.min.css'

/** 从 Markdown 提取 ## / ### 标题（跳过代码块），id 与渲染层的锚点编号一致。 */
export function extractHeadings(markdown: string): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = []
  let inFence = false
  let idx = 0
  for (const line of (markdown || '').split('\n')) {
    const s = line.trim()
    if (s.startsWith('```')) {
      inFence = !inFence
      continue
    }
    if (inFence) continue
    const m = /^(#{2,3})\s+(.*)$/.exec(s)
    if (m) {
      const label = m[2]
        .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
        .replace(/[*_`]/g, '')
        .trim()
      out.push({ id: `h-${idx}`, label })
      idx++
    }
  }
  return out
}

/** HTML 文本层补标题锚点：按出现顺序给 h2/h3 编号，与 extractHeadings 对齐。 */
function injectHeadingIds(html: string): string {
  let idx = 0
  return html.replace(/<h([23])([^>]*)>/g, (_m, level: string, rest: string) => {
    const id = `h-${idx}`
    idx++
    return `<h${level}${rest} id="${id}">`
  })
}

/** 公式渲染：$$...$$ 独立公式 → $...$ 行内公式；解析失败保留原文。 */
function renderMathHtml(html: string): string {
  let out = html.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex: string) => {
    try {
      return katex.renderToString(tex.trim(), { throwOnError: false, displayMode: true })
    } catch {
      return `$$${tex}$$`
    }
  })
  out = out.replace(/\$([^$\n]+?)\$/g, (_m, tex: string) => {
    try {
      return katex.renderToString(tex.trim(), { throwOnError: false, displayMode: false })
    } catch {
      return `$${tex}$`
    }
  })
  return out
}

export default function MarkdownView(props: { markdown: string }) {
  const html = useMemo(() => {
    const raw = marked.parse(props.markdown || '', { gfm: true, breaks: false }) as string
    const clean = DOMPurify.sanitize(raw)
    return renderMathHtml(injectHeadingIds(clean))
  }, [props.markdown])

  return <article className="article md-view" dangerouslySetInnerHTML={{ __html: html }} />
}
