interface Props {
  lang: 'en' | 'zh'
  onChange: (lang: 'en' | 'zh') => void
}

export default function LanguageSwitch({ lang, onChange }: Props) {
  return (
    <div>
      <button
        className={lang === 'en' ? 'active' : ''}
        onClick={() => onChange('en')}
      >
        EN
      </button>
      <button
        className={lang === 'zh' ? 'active' : ''}
        onClick={() => onChange('zh')}
      >
        中文
      </button>
    </div>
  )
}
