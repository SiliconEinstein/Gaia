import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import styles from './SectionView.module.css'

interface Props {
  sections: string[]
  lang: 'en' | 'zh'
}

/** Rewrite relative image paths so ![](foo.png) becomes ![](data/assets/foo.png). */
function rewriteImagePaths(md: string): string {
  return md.replace(
    /!\[([^\]]*)\]\((?!https?:\/\/|data\/)(.*?)\)/g,
    '![$1](data/assets/$2)',
  )
}

async function fetchSection(name: string, lang: 'en' | 'zh'): Promise<string> {
  if (lang === 'zh') {
    const zhResp = await fetch(`data/sections/${name}-zh.md`)
    if (zhResp.ok) return zhResp.text()
  }
  const resp = await fetch(`data/sections/${name}.md`)
  if (resp.ok) return resp.text()
  return ''
}

export default function SectionView({ sections, lang }: Props) {
  const [contents, setContents] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false
    async function load() {
      const entries: [string, string][] = await Promise.all(
        sections.map(async (s) => {
          const md = await fetchSection(s, lang)
          return [s, md] as [string, string]
        }),
      )
      if (!cancelled) {
        setContents(Object.fromEntries(entries))
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [sections, lang])

  return (
    <div className={styles.container}>
      {sections.map((name) => (
        <div key={name} className={styles.section}>
          <h2>{name}</h2>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {rewriteImagePaths(contents[name] ?? '')}
          </ReactMarkdown>
        </div>
      ))}
    </div>
  )
}
