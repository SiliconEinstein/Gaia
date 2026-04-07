import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('GitHub Actions pages workflow', () => {
  const workflowPath = resolve(__dirname, '../../.github/workflows/pages.yml')
  const content = readFileSync(workflowPath, 'utf-8')

  it('contains deploy-pages action', () => {
    expect(content).toContain('deploy-pages')
  })

  it('contains npm ci step', () => {
    expect(content).toContain('npm ci')
  })

  it('contains npm run build step', () => {
    expect(content).toContain('npm run build')
  })

  it('triggers on push to main', () => {
    expect(content).toContain('branches: [main]')
  })

  it('uploads pages artifact from docs/dist', () => {
    expect(content).toContain('docs/dist')
  })
})
