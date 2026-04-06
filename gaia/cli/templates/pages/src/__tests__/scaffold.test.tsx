import { describe, it, expect } from 'vitest'
import pkg from '../../package.json'

describe('scaffold', () => {
  it('has required dependencies', () => {
    expect(pkg.dependencies).toHaveProperty('react')
    expect(pkg.dependencies).toHaveProperty('cytoscape')
    expect(pkg.dependencies).toHaveProperty('react-markdown')
  })
})
