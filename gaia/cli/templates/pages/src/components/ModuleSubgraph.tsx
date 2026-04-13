import { useMemo, useRef, useCallback, useState, useEffect } from 'react'
import { useElkLayout, type ElkEdge, type ElkNode } from '../hooks/useElkLayout'
import { useZoomPan } from '../hooks/useZoomPan'
import {
  filterNodesByModule,
  filterEdgesForModule,
  getExternalRefs,
  type ExternalRef,
} from '../hooks/useGraphData'
import { useChainHighlight } from '../hooks/useChainHighlight'
import NodeRenderer from './NodeRenderer'
import EdgeRenderer from './EdgeRenderer'
import DetailPanel from './DetailPanel'
import type { GraphNode, GraphEdge } from '../types'

const MODULE_GROUP_PADDING = 20
const EXTERNAL_STACK_GAP = 20
const EXTERNAL_LANE_GAP = 48
const EXTERNAL_GROUP_GAP = 24
const VIEWPORT_PADDING = 80

export interface ExternalModuleGroup {
  groupKey: string
  sourceModule: string
  nodeIds: string[]
}

export interface ModuleGroupBounds {
  groupKey: string
  sourceModule: string
  x: number
  y: number
  width: number
  height: number
}

interface LayoutBounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

interface RenderViewport {
  offsetX: number
  offsetY: number
  width: number
  height: number
}

const UNNAMED_EXTERNAL_GROUP_KEY = '__gaia_unnamed_external__'

function getExternalModuleGroupKey(sourceModule: string): string {
  return sourceModule || UNNAMED_EXTERNAL_GROUP_KEY
}

function normalizeExternalSourceModule(sourceModule: string): string {
  return sourceModule || 'External'
}

function computeBoundsFromNodes(nodes: ElkNode[], padding: number): ModuleGroupBounds {
  const minX = Math.min(...nodes.map(node => node.x))
  const maxX = Math.max(...nodes.map(node => node.x + node.width))
  const minY = Math.min(...nodes.map(node => node.y))
  const maxY = Math.max(...nodes.map(node => node.y + node.height))

  return {
    groupKey: '',
    sourceModule: '',
    x: minX - padding,
    y: minY - padding,
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
  }
}

function collectSectionPoints(section: NonNullable<ElkEdge['sections']>[number]): Array<{ x: number; y: number }> {
  return [
    section.startPoint,
    ...(section.bendPoints ?? []),
    section.endPoint,
  ]
}

function average(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

interface BoxBounds {
  x: number
  y: number
  width: number
  height: number
}

function boxesOverlap(a: BoxBounds, b: BoxBounds): boolean {
  return a.x < b.x + b.width
    && a.x + a.width > b.x
    && a.y < b.y + b.height
    && a.y + a.height > b.y
}

function hasMovement(delta: { dx: number; dy: number } | undefined): boolean {
  return !!delta && (delta.dx !== 0 || delta.dy !== 0)
}

function movePoint(
  point: { x: number; y: number },
  delta: { dx: number; dy: number } | undefined,
): { x: number; y: number } {
  if (!hasMovement(delta)) {
    return point
  }

  return {
    x: point.x + delta!.dx,
    y: point.y + delta!.dy,
  }
}

function buildOrthogonalSection(
  startPoint: { x: number; y: number },
  endPoint: { x: number; y: number },
) {
  const horizontalOffset = 24
  const entryOffset = 18
  const exitX = startPoint.x < endPoint.x
    ? startPoint.x + horizontalOffset
    : startPoint.x - horizontalOffset
  const entryX = startPoint.x < endPoint.x
    ? endPoint.x - entryOffset
    : endPoint.x + entryOffset

  return {
    startPoint,
    bendPoints: [
      { x: exitX, y: startPoint.y },
      { x: exitX, y: endPoint.y },
      { x: entryX, y: endPoint.y },
    ],
    endPoint,
  }
}

function moduleGroupBoxesOverlap(a: ModuleGroupBounds, b: ModuleGroupBounds): boolean {
  return boxesOverlap(a, b)
}

function groupOverlapsAnyNode(groupBounds: ModuleGroupBounds, nodes: ElkNode[]): boolean {
  return nodes.some(node => boxesOverlap(groupBounds, node))
}

export function buildExternalModuleGroups(
  externalRefs: Array<{ id: string; sourceModule: string }>,
): ExternalModuleGroup[] {
  const groups = new Map<string, ExternalModuleGroup>()
  const orderedGroups: ExternalModuleGroup[] = []

  for (const ref of externalRefs) {
    const groupKey = getExternalModuleGroupKey(ref.sourceModule)
    let group = groups.get(groupKey)
    if (!group) {
      group = {
        groupKey,
        sourceModule: normalizeExternalSourceModule(ref.sourceModule),
        nodeIds: [],
      }
      groups.set(groupKey, group)
      orderedGroups.push(group)
    }
    group.nodeIds.push(ref.id)
  }

  return orderedGroups
}

export function computeModuleGroups(
  layoutNodes: ElkNode[],
  externalRefs: Array<{ id: string; sourceModule: string }>,
  padding: number,
): ModuleGroupBounds[] {
  const groups = buildExternalModuleGroups(externalRefs)
  const nodeMap = new Map(layoutNodes.map(node => [node.id, node]))
  const laneLeft = Math.min(
    ...groups.flatMap(group => group.nodeIds
      .map(nodeId => nodeMap.get(nodeId))
      .filter((node): node is ElkNode => node != null)
      .map(node => node.x - padding)),
  )
  const laneRight = Math.max(
    ...groups.flatMap(group => group.nodeIds
      .map(nodeId => nodeMap.get(nodeId))
      .filter((node): node is ElkNode => node != null)
      .map(node => node.x + node.width + padding)),
  )

  return groups
    .map(group => {
      const nodes = group.nodeIds
        .map(nodeId => nodeMap.get(nodeId))
        .filter((node): node is ElkNode => node != null)

      if (nodes.length === 0) {
        return null
      }

      const minY = Math.min(...nodes.map(node => node.y))
      const maxY = Math.max(...nodes.map(node => node.y + node.height))

      return {
        groupKey: group.groupKey,
        sourceModule: group.sourceModule,
        x: laneLeft,
        y: minY - padding,
        width: laneRight - laneLeft,
        height: maxY - minY + padding * 2,
      }
    })
    .filter((group): group is ModuleGroupBounds => group != null)
}

export function adjustExternalLayout(
  layoutNodes: ElkNode[],
  layoutEdges: ElkEdge[],
  externalRefs: Array<{ id: string; sourceModule: string }>,
): { nodes: ElkNode[]; edges: ElkEdge[] } {
  const externalIds = new Set(externalRefs.map(ref => ref.id))
  const originalNodeMap = new Map(layoutNodes.map(node => [node.id, node]))
  const adjustedExternalNodes = new Map<string, ElkNode>()
  const internalNodes = layoutNodes.filter(node => !externalIds.has(node.id))
  const internalOnlyEdges = layoutEdges.filter(
    edge => !externalIds.has(edge.source) && !externalIds.has(edge.target),
  )
  const internalBounds = computeLayoutBounds(internalNodes, internalOnlyEdges, [])
  const laneNodeRight = internalBounds.minX - EXTERNAL_LANE_GAP - MODULE_GROUP_PADDING
  const laneGroupX = laneNodeRight - Math.max(...layoutNodes
    .filter(node => externalIds.has(node.id))
    .map(node => node.width)) - MODULE_GROUP_PADDING
  let nextAvailableY = Number.NEGATIVE_INFINITY

  for (const group of buildExternalModuleGroups(externalRefs)) {
    const originalNodes = group.nodeIds
      .map(nodeId => originalNodeMap.get(nodeId))
      .filter((node): node is ElkNode => node != null)

    if (originalNodes.length === 0) {
      continue
    }

    const connectedInternalNodeIds = new Set<string>()
    for (const edge of layoutEdges) {
      const touchesGroup = group.nodeIds.includes(edge.source) || group.nodeIds.includes(edge.target)
      if (!touchesGroup) {
        continue
      }
      if (!externalIds.has(edge.source)) {
        connectedInternalNodeIds.add(edge.source)
      }
      if (!externalIds.has(edge.target)) {
        connectedInternalNodeIds.add(edge.target)
      }
    }

    const connectedCenters = [...connectedInternalNodeIds]
      .map(nodeId => originalNodeMap.get(nodeId))
      .filter((node): node is ElkNode => node != null)
      .map(node => node.y + node.height / 2)

    const groupNodeWidth = Math.max(...originalNodes.map(node => node.width))
    const laneX = laneGroupX + MODULE_GROUP_PADDING
    const totalStackHeight = originalNodes.reduce(
      (sum, node, index) => sum + node.height + (index === 0 ? 0 : EXTERNAL_STACK_GAP),
      0,
    )
    const preferredCenterY = connectedCenters.length > 0
      ? average(connectedCenters)
      : average(originalNodes.map(node => node.y + node.height / 2))
    const preferredTopY = preferredCenterY - totalStackHeight / 2
    const stackedTopY = Math.max(preferredTopY, nextAvailableY)

    let nextNodeY = stackedTopY
    const stackedNodes = originalNodes.map(node => {
      const positionedNode = { ...node, x: laneX, y: nextNodeY }
      nextNodeY += node.height + EXTERNAL_STACK_GAP
      return positionedNode
    })

    const groupBounds = computeBoundsFromNodes(stackedNodes, MODULE_GROUP_PADDING)
    nextAvailableY = groupBounds.y + groupBounds.height + EXTERNAL_GROUP_GAP + MODULE_GROUP_PADDING

    for (const node of stackedNodes) {
      adjustedExternalNodes.set(node.id, node)
    }
  }

  const adjustedNodes = layoutNodes.map(node => adjustedExternalNodes.get(node.id) ?? node)
  const movementByNodeId = new Map<string, { dx: number; dy: number }>()

  for (const node of adjustedNodes) {
    if (!externalIds.has(node.id)) {
      continue
    }
    const originalNode = originalNodeMap.get(node.id)
    if (!originalNode) {
      continue
    }
    movementByNodeId.set(node.id, {
      dx: node.x - originalNode.x,
      dy: node.y - originalNode.y,
    })
  }

  const adjustedEdges = layoutEdges.map(edge => {
    const sourceDelta = movementByNodeId.get(edge.source)
    const targetDelta = movementByNodeId.get(edge.target)

    if (!hasMovement(sourceDelta) && !hasMovement(targetDelta)) {
      return edge
    }

    if (!edge.sections) {
      return edge
    }

    return {
      ...edge,
      sections: edge.sections.map(section => {
        const startPoint = movePoint(section.startPoint, sourceDelta)
        const endPoint = movePoint(section.endPoint, targetDelta)
        const touchesExternal = externalIds.has(edge.source) || externalIds.has(edge.target)

        if (touchesExternal) {
          return buildOrthogonalSection(startPoint, endPoint)
        }

        return {
          ...section,
          startPoint,
          bendPoints: section.bendPoints?.map(point => {
            if (hasMovement(sourceDelta) && hasMovement(targetDelta)) {
              return {
                x: point.x + (sourceDelta!.dx + targetDelta!.dx) / 2,
                y: point.y + (sourceDelta!.dy + targetDelta!.dy) / 2,
              }
            }
            if (hasMovement(sourceDelta)) {
              return {
                x: point.x + sourceDelta!.dx,
                y: point.y + sourceDelta!.dy,
              }
            }
            if (hasMovement(targetDelta)) {
              return {
                x: point.x + targetDelta!.dx,
                y: point.y + targetDelta!.dy,
              }
            }
            return point
          }),
          endPoint,
        }
      }),
    }
  })

  return {
    nodes: adjustedNodes,
    edges: adjustedEdges,
  }
}

export function computeLayoutBounds(
  layoutNodes: ElkNode[],
  layoutEdges: ElkEdge[],
  moduleGroups: ModuleGroupBounds[],
): LayoutBounds {
  const xs: number[] = []
  const ys: number[] = []

  for (const node of layoutNodes) {
    xs.push(node.x, node.x + node.width)
    ys.push(node.y, node.y + node.height)
  }

  for (const edge of layoutEdges) {
    for (const section of edge.sections ?? []) {
      for (const point of collectSectionPoints(section)) {
        xs.push(point.x)
        ys.push(point.y)
      }
    }
  }

  for (const group of moduleGroups) {
    xs.push(group.x, group.x + group.width)
    ys.push(group.y, group.y + group.height)
  }

  if (xs.length === 0 || ys.length === 0) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0 }
  }

  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  }
}

function buildRenderViewport(bounds: LayoutBounds, padding: number): RenderViewport {
  return {
    offsetX: padding - bounds.minX,
    offsetY: padding - bounds.minY,
    width: bounds.maxX - bounds.minX + padding * 2,
    height: bounds.maxY - bounds.minY + padding * 2,
  }
}

interface Props {
  moduleId: string
  allNodes: GraphNode[]
  allEdges: GraphEdge[]
  onBack: () => void
  onNavigateToModule: (moduleId: string, nodeId: string) => void
}

export default function ModuleSubgraph({
  moduleId, allNodes, allEdges, onBack, onNavigateToModule,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 })

  const {
    transform,
    isDragging,
    zoomIn,
    zoomOut,
    reset,
    fitToBounds,
    setTransform,
    getTransformString,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleWheel,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
  } = useZoomPan({ minScale: 0.1, maxScale: 3, zoomStep: 0.2 })

  const { moduleNodes, moduleEdges, externalRefs } = useMemo(() => {
    const mNodes = filterNodesByModule(allNodes, moduleId)
    const mNodeIds = new Set(mNodes.map(n => n.id))
    const mEdges = filterEdgesForModule(allEdges, mNodeIds)
    const refs = getExternalRefs(mEdges, mNodeIds, allNodes)
    const extNodes: GraphNode[] = refs.map(r => ({
      id: r.id,
      label: `↗ ${r.label}`,
      type: 'setting' as const,
      module: r.sourceModule,
      content: '',
      exported: false,
      metadata: { _external: true, _sourceModule: r.sourceModule },
    }))
    return {
      moduleNodes: [...mNodes, ...extNodes],
      moduleEdges: mEdges,
      externalRefs: refs,
    }
  }, [allNodes, allEdges, moduleId])

  const layout = useElkLayout(moduleNodes, moduleEdges)
  const { highlightedIds, selectedNodeId, selectNode, clearSelection } = useChainHighlight(allEdges)

  const [hoverGroupKey, setHoverGroupKey] = useState<string | null>(null)
const scrimDraggedRef = useRef(false)

  const nodesById = useMemo(() => {
    const m = new Map<string, GraphNode>()
    for (const n of allNodes) m.set(n.id, n)
    return m
  }, [allNodes])

  const handleNodeSelect = useCallback((id: string) => {
    const ext = externalRefs.find(r => r.id === id)
    if (ext) {
      onNavigateToModule(ext.sourceModule, id)
      return
    }
    selectNode(id)
  }, [externalRefs, onNavigateToModule, selectNode])

  const selectedNode = selectedNodeId ? nodesById.get(selectedNodeId) ?? null : null

  const adjustedLayout = useMemo(() => {
    if (!layout) {
      return null
    }

    const adjusted = adjustExternalLayout(layout.nodes, layout.edges, externalRefs)
    const moduleGroups = computeModuleGroups(adjusted.nodes, externalRefs, MODULE_GROUP_PADDING)
    const bounds = computeLayoutBounds(adjusted.nodes, adjusted.edges, moduleGroups)
    const viewport = buildRenderViewport(bounds, VIEWPORT_PADDING)

    return {
      ...adjusted,
      moduleGroups,
      bounds,
      viewport,
    }
  }, [layout, externalRefs])

  // Update container size on mount and resize
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setContainerSize({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    }

    updateSize()
    window.addEventListener('resize', updateSize)
    return () => window.removeEventListener('resize', updateSize)
  }, [])

  // Auto-fit graph to viewport when layout is ready
  useEffect(() => {
    if (!adjustedLayout || containerSize.width === 0) return

    const { bounds } = adjustedLayout
    fitToBounds(
      {
        width: bounds.maxX - bounds.minX,
        height: bounds.maxY - bounds.minY,
      },
      containerSize,
      VIEWPORT_PADDING
    )
  }, [adjustedLayout, containerSize, fitToBounds])

  if (!layout || !adjustedLayout) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#888' }}>Computing layout...</div>
  }

  const edgeByKey = new Map<string, GraphEdge>()
  for (const e of moduleEdges) {
    edgeByKey.set(`${e.source}->${e.target}`, e)
  }

  // Build layout edge groups by source-target key
  const edgeGroups = new Map<string, ElkEdge[]>()
  for (const le of adjustedLayout.edges) {
    const key = `${le.source}->${le.target}`
    const arr = edgeGroups.get(key)
    if (arr) arr.push(le)
    else edgeGroups.set(key, [le])
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div ref={containerRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        {/* Header with breadcrumbs */}
        <div style={{
          padding: '8px 16px', fontSize: 13, color: '#666',
          borderBottom: '1px solid #eee', background: '#fafafa',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <span onClick={onBack} style={{ cursor: 'pointer', color: '#4488bb' }}>
              ← All Modules
            </span>
            {' / '}
            <strong>{moduleId}</strong>
          </div>
          {/* Zoom controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={zoomOut}
              title="Zoom out"
              style={{
                padding: '4px 12px',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                background: '#fff',
                cursor: 'pointer',
                fontSize: 16,
              }}
            >−</button>
            <span style={{ minWidth: 50, textAlign: 'center', fontSize: 13 }}>
              {Math.round(transform.scale * 100)}%
            </span>
            <button
              onClick={zoomIn}
              title="Zoom in"
              style={{
                padding: '4px 12px',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                background: '#fff',
                cursor: 'pointer',
                fontSize: 16,
              }}
            >+</button>
            <button
              onClick={() => {
                if (adjustedLayout && containerRef.current) {
                  fitToBounds(
                    {
                      width: adjustedLayout.bounds.maxX - adjustedLayout.bounds.minX,
                      height: adjustedLayout.bounds.maxY - adjustedLayout.bounds.minY,
                    },
                    {
                      width: containerRef.current.clientWidth,
                      height: containerRef.current.clientHeight,
                    },
                    VIEWPORT_PADDING
                  )
                }
              }}
              title="Reset view"
              style={{
                padding: '4px 12px',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                background: '#fff',
                cursor: 'pointer',
                fontSize: 13,
              }}
            >⟲</button>
          </div>
        </div>

        {/* Graph container with zoom/pan */}
        <div
          style={{
            flex: 1,
            position: 'relative',
            overflow: 'hidden',
            cursor: isDragging ? 'grabbing' : 'grab',
            background: '#fafafa',
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          <div
            style={{
              position: 'absolute',
              transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
              transformOrigin: '0 0',
              willChange: 'transform',
            }}
          >
            <svg
              ref={svgRef}
              width={adjustedLayout.viewport.width}
              height={adjustedLayout.viewport.height}
              style={{
                display: 'block',
              }}
            >
              <g transform={`translate(${adjustedLayout.viewport.offsetX}, ${adjustedLayout.viewport.offsetY})`}>
              {adjustedLayout.moduleGroups.map(group => (
                <g key={group.groupKey}>
                  <rect
                    x={group.x}
                    y={group.y}
                    width={group.width}
                    height={group.height}
                    rx={8}
                    ry={8}
                    fill="#f8f9fa"
                    stroke="#d9d9d9"
                    strokeWidth={1}
                    strokeDasharray="4,2"
                  />
                  <text
                    x={group.x + 8}
                    y={group.y + 16}
                    fontSize={11}
                    fill="#666"
                    fontFamily="system-ui, sans-serif"
                  >
                    {group.sourceModule}
                  </text>
                </g>
              ))}
              {[...edgeGroups.entries()].map(([groupKey, groupEdges]) => {
                const ge = edgeByKey.get(`${groupEdges[0].source}->${groupEdges[0].target}`)
                const inChainGroup = (id: string) => highlightedIds ? highlightedIds.has(id) : null
                const expanded = hoverGroupKey === groupKey
                return (
                  <g key={groupKey} onMouseEnter={() => setHoverGroupKey(groupKey)} onMouseLeave={() => setHoverGroupKey(null)}>
                    {groupEdges.map((le, idx) => {
                      const inChain = highlightedIds
                        ? highlightedIds.has(le.source) && highlightedIds.has(le.target)
                        : null
                      return (
                        <EdgeRenderer
                          key={le.id}
                          layoutEdge={le}
                          graphEdge={ge}
                          highlighted={inChain}
                          groupIndex={idx}
                          groupCount={groupEdges.length}
                          expanded={expanded}
                        />
                      )
                    })}
                  </g>
                )
              })}
              {adjustedLayout.nodes.map(ln => {
                const gn = moduleNodes.find(n => n.id === ln.id)
                if (!gn) return null
                const inChain = highlightedIds ? highlightedIds.has(ln.id) : null
                return (
                  <NodeRenderer
                    key={ln.id}
                    node={gn}
                    x={ln.x}
                    y={ln.y}
                    width={ln.width}
                    height={ln.height}
                    highlighted={inChain}
                    onSelect={handleNodeSelect}
                  />
                )
              })}
              </g>
            </svg>
          </div>

          {selectedNode && (
            <div
              aria-label="graph-scrim"
              onMouseDown={() => { scrimDraggedRef.current = false }}
              onMouseMove={() => { scrimDraggedRef.current = true }}
              onClick={() => { if (!isDragging && !scrimDraggedRef.current) clearSelection() }}
              style={{ position: 'absolute', inset: 0, background: 'transparent', zIndex: 10 }}
            />
          )}
        </div>
      </div>

      <DetailPanel
        node={selectedNode}
        edges={allEdges}
        nodesById={Object.fromEntries(nodesById)}
        onClose={clearSelection}
      />
    </div>
  )
}
