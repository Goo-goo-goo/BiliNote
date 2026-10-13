// 结构化笔记渲染器：note_json 直接渲染（KaTeX 本地渲染公式，零 CDN）
import katex from 'katex'
import 'katex/dist/katex.min.css'
import type { NoteBlock, NoteChapter, NoteJson, NoteSection } from '../lib/api'
import { Timecode } from '../components/ui'

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 常见损坏修复：转义层把 \n \t \r \f \v \b 当成控制字符解掉，
 *  于是 \nabla → 换行+abla、\theta → 制表符+heta。这里做逆向还原。 */
function repairEscapes(latex: string): string {
  return latex
    .replace(/\n/g, '\\n')
    .replace(/\t/g, '\\t')
    .replace(/\r/g, '\\r')
    .replace(/\f/g, '\\f')
    .replace(/\v/g, '\\v')
    .replace(/\x08/g, '\\b')
}

function renderMathHtml(latex: string, displayMode: boolean): string {
  const tryRender = (src: string): string | null => {
    try {
      return katex.renderToString(src, { throwOnError: true, displayMode })
    } catch {
      return null
    }
  }
  // 含控制字符（换行/制表等）的公式多半是转义损坏，优先试修复版：
  // KaTeX 对「abla f( heta_t)」这种损坏会容忍渲染，先试修复才拦得住；
  // 合法的多行公式修复后会报错，自动落回原文渲染，不会误伤。
  if (/[\n\t\r\f\v\x08]/.test(latex)) {
    return tryRender(repairEscapes(latex)) ?? tryRender(latex) ?? ''
  }
  return tryRender(latex) ?? ''
}

/** 行内片段：**加粗**、`代码`、$公式$ / \(公式\) → HTML */
function inlineHtml(text: string): string {
  const escaped = escapeHtml(text)

  const parts: string[] = []
  // 注：$...$ 允许跨行——转义损坏的公式里 \n 会变成真换行
  const pattern =
    /\$\$([\s\S]+?)\$\$|\$([^$]+)\$|\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]|`([^`]+)`|\*\*([^*]+)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = pattern.exec(escaped))) {
    parts.push(escaped.slice(last, m.index))
    const tex = m[1] ?? m[2] ?? m[3] ?? m[4]
    if (tex != null) {
      const display = m[1] != null || m[4] != null
      const html = renderMathHtml(tex, display)
      // 渲染不出来就按原文回显（已转义，不吞内容）
      parts.push(html || `<code>${tex}</code>`)
    } else if (m[5] != null) {
      parts.push(`<code>${m[5]}</code>`)
    } else if (m[6] != null) {
      parts.push(`<strong>${m[6]}</strong>`)
    }
    last = m.index + m[0].length
  }
  parts.push(escaped.slice(last))
  return parts.join('')
}

function Inline({ text }: { text: string }) {
  return <span dangerouslySetInnerHTML={{ __html: inlineHtml(text || '') }} />
}

function displayMath(latex: string): string {
  return renderMathHtml(latex, true) || `<code>${escapeHtml(latex)}</code>`
}

function BlockView({ block, imageBase }: { block: NoteBlock; imageBase: string }) {
  switch (block.type) {
    case 'text':
      return <p><Inline text={block.content || ''} /></p>
    case 'formula':
      return <div className="math-display" dangerouslySetInnerHTML={{ __html: displayMath(block.content || '') }} />
    case 'quote':
      return <blockquote><Inline text={block.content || ''} /></blockquote>
    case 'steps':
      return (
        <ol>
          {(block.items || []).map((item, i) => (
            <li key={i}><Inline text={item} /></li>
          ))}
        </ol>
      )
    case 'list':
      return block.ordered ? (
        <ol>
          {(block.items || []).map((item, i) => (
            <li key={i}><Inline text={item} /></li>
          ))}
        </ol>
      ) : (
        <ul>
          {(block.items || []).map((item, i) => (
            <li key={i}><Inline text={item} /></li>
          ))}
        </ul>
      )
    case 'code':
      return (
        <pre>
          <code>{block.content || ''}</code>
        </pre>
      )
    case 'table': {
      const headers = block.headers || []
      const rows = block.rows || []
      return (
        <table>
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i}><Inline text={h} /></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}><Inline text={cell} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )
    }
    case 'screenshot': {
      const src = block.image_url
        ? block.image_url.startsWith('http')
          ? block.image_url
          : `${imageBase}${block.image_url}`
        : ''
      return (
        <figure>
          {src ? <img src={src} alt={block.content || '截图'} /> : null}
          {block.content && <figcaption>{block.content}</figcaption>}
        </figure>
      )
    }
    default:
      return block.content ? <p><Inline text={block.content} /></p> : null
  }
}

export function sectionId(chapterIndex: number, sectionIndex: number): string {
  return `sec-${chapterIndex}-${sectionIndex}`
}

/** 章节锚点：时间轨刻度跳转的落点 */
export function chapterId(chapterIndex: number): string {
  return `chap-${chapterIndex}`
}

export default function NoteRenderer(props: {
  note: NoteJson
  imageBase: string
  timeLink?: (hms: string) => string | null
}) {
  const { note, imageBase, timeLink } = props

  const jump = (hms?: string) => {
    const url = hms && timeLink ? timeLink(hms) : null
    if (url) window.open(url, '_blank')
  }

  return (
    <article className="article">
      {note.summary && (
        <div className="lead">
          <Inline text={note.summary} />
        </div>
      )}
      {note.tags && note.tags.length > 0 && (
        <div className="rowflex" style={{ flexWrap: 'wrap', marginBottom: 8 }}>
          {note.tags.map((t) => (
            <span className="tag" key={t}>
              {t}
            </span>
          ))}
        </div>
      )}

      {note.chapters.map((chapter: NoteChapter, ci) => (
        <section key={ci}>
          <h2 id={chapterId(ci)}>
            {ci + 1}. {chapter.title}
            {chapter.time_stamp && (
              <>
                {' '}
                <Timecode value={chapter.time_stamp} onClick={() => jump(chapter.time_stamp)} hot />
              </>
            )}
          </h2>
          {chapter.intro && (
            <p className="soft">
              <Inline text={chapter.intro} />
            </p>
          )}

          {chapter.sections.map((section: NoteSection, si) => (
            <div key={si} id={sectionId(ci, si)}>
              <h3>
                {section.important && <span className="important-mark">重点</span>}
                {ci + 1}.{si + 1} {section.heading}
                {section.time_stamp && (
                  <>
                    {' '}
                    <Timecode value={section.time_stamp} onClick={() => jump(section.time_stamp)} />
                  </>
                )}
              </h3>
              {section.blocks.map((block, bi) => (
                <BlockView key={bi} block={block} imageBase={imageBase} />
              ))}
            </div>
          ))}

          {chapter.summary && (
            <blockquote>
              <strong>本章小结：</strong>
              <Inline text={chapter.summary} />
            </blockquote>
          )}
          {chapter.key_points && chapter.key_points.length > 0 && (
            <div>
              <strong>本章要点</strong>
              <ul>
                {chapter.key_points.map((p, i) => (
                  <li key={i}><Inline text={p} /></li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ))}

      {note.key_takeaways && note.key_takeaways.length > 0 && (
        <section>
          <h2>核心要点</h2>
          <ul>
            {note.key_takeaways.map((p, i) => (
              <li key={i}><Inline text={p} /></li>
            ))}
          </ul>
        </section>
      )}
    </article>
  )
}
