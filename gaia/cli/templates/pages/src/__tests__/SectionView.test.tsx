import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import SectionView from '../components/SectionView'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('SectionView', () => {
  it('fetches markdown and renders content', async () => {
    const md = '# Motivation\n\nThis section explains the motivation.'

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(md, { status: 200 }),
    )

    render(<SectionView sections={['motivation']} lang="en" />)

    await waitFor(() => {
      expect(screen.getByText('This section explains the motivation.')).toBeInTheDocument()
    })
  })

  it('falls back to default md when zh fetch fails', async () => {
    const fallbackMd = '# Motivation\n\nFallback content here.'

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (url.includes('-zh.md')) {
        return new Response('', { status: 404 })
      }
      return new Response(fallbackMd, { status: 200 })
    })

    render(<SectionView sections={['motivation']} lang="zh" />)

    await waitFor(() => {
      expect(screen.getByText('Fallback content here.')).toBeInTheDocument()
    })
  })

  it('rewrites relative image paths', async () => {
    const md = '![diagram](foo.png)'

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(md, { status: 200 }),
    )

    render(<SectionView sections={['intro']} lang="en" />)

    await waitFor(() => {
      const img = screen.getByRole('img') as HTMLImageElement
      expect(img.src).toContain('data/assets/foo.png')
    })
  })
})
