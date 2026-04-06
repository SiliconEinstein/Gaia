/// <reference types="vite/client" />

declare module 'cytoscape-dagre' {
  const ext: cytoscape.Ext
  export default ext
}

declare module '*.module.css' {
  const classes: Record<string, string>
  export default classes
}
