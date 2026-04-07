import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import LanguageSwitch from '../components/LanguageSwitch'

describe('LanguageSwitch', () => {
  it('renders EN and chinese buttons', () => {
    render(<LanguageSwitch lang="en" onChange={() => {}} />)
    expect(screen.getByText('EN')).toBeInTheDocument()
    expect(screen.getByText('中文')).toBeInTheDocument()
  })

  it('marks the active language button', () => {
    const { rerender } = render(<LanguageSwitch lang="en" onChange={() => {}} />)
    expect(screen.getByText('EN').className).toMatch(/active/)
    expect(screen.getByText('中文').className).not.toMatch(/active/)

    rerender(<LanguageSwitch lang="zh" onChange={() => {}} />)
    expect(screen.getByText('中文').className).toMatch(/active/)
    expect(screen.getByText('EN').className).not.toMatch(/active/)
  })

  it('calls onChange with zh when clicking chinese button', () => {
    const onChange = vi.fn()
    render(<LanguageSwitch lang="en" onChange={onChange} />)
    fireEvent.click(screen.getByText('中文'))
    expect(onChange).toHaveBeenCalledWith('zh')
  })

  it('calls onChange with en when clicking EN button', () => {
    const onChange = vi.fn()
    render(<LanguageSwitch lang="zh" onChange={onChange} />)
    fireEvent.click(screen.getByText('EN'))
    expect(onChange).toHaveBeenCalledWith('en')
  })
})
