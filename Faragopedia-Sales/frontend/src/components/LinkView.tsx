import React, { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback } from 'react';
import { Loader2, Network, X, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { API_BASE } from '../config';

interface GraphNode {
  id: string;
  title: string;
  group: string;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface GraphGroup {
  id: string;
  name: string;
  description: string;
}

interface LinkGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  groups: GraphGroup[];
}

interface CurveLine {
  path: string;
  key: string;
}

// Cycled per group index. Hex values feed inline styles (SVG strokes, chip
// borders) because Tailwind cannot generate per-group classes dynamically.
const GROUP_PALETTE = [
  { dot: 'bg-blue-500', title: 'text-blue-600 dark:text-blue-400', stroke: '#2563eb', strokeDark: '#60a5fa' },
  { dot: 'bg-purple-500', title: 'text-purple-600 dark:text-purple-400', stroke: '#9333ea', strokeDark: '#c084fc' },
  { dot: 'bg-emerald-500', title: 'text-emerald-600 dark:text-emerald-400', stroke: '#059669', strokeDark: '#34d399' },
  { dot: 'bg-amber-500', title: 'text-amber-600 dark:text-amber-400', stroke: '#d97706', strokeDark: '#fbbf24' },
  { dot: 'bg-pink-500', title: 'text-pink-600 dark:text-pink-400', stroke: '#db2777', strokeDark: '#f472b6' },
  { dot: 'bg-cyan-500', title: 'text-cyan-600 dark:text-cyan-400', stroke: '#0891b2', strokeDark: '#22d3ee' },
];

const splitFrontmatter = (raw: string): { fields: [string, string][]; body: string } => {
  const match = raw.replace(/\r\n/g, '\n').match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) return { fields: [], body: raw };
  const fields: [string, string][] = [];
  for (const line of match[1].split('\n')) {
    const kv = line.match(/^(\w[\w-]*):\s*(.+)$/);
    if (!kv) continue;
    const value = kv[2].trim().replace(/^["']|["']$/g, '');
    if (value) fields.push([kv[1], value]);
  }
  return { fields, body: match[2] };
};

const LinkView: React.FC = () => {
  const [graph, setGraph] = useState<LinkGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [lines, setLines] = useState<CurveLine[]>([]);
  const [measureTick, setMeasureTick] = useState(0);
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));
  const [pageContent, setPageContent] = useState<string | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const chipRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const panelBodyRef = useRef<HTMLDivElement>(null);

  // Hover takes display priority so hovering always responds, even while a
  // page is focused — a lingering focus must never make hover look dead.
  const activeId = hoverId ?? focusId;
  const mode: 'rest' | 'hover' | 'focus' = hoverId ? 'hover' : focusId ? 'focus' : 'rest';

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const res = await fetch(`${API_BASE}/pages/graph`);
        if (!res.ok) throw new Error('Failed to load link graph');
        const data: LinkGraph = await res.json();
        setGraph(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchGraph();
  }, []);

  // Escape resets hover + focus (and thereby closes the reading panel)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setFocusId(null);
        setHoverId(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Chip positions shift when the window or sidebar resizes — remeasure curves
  useEffect(() => {
    const bump = () => setMeasureTick(t => t + 1);
    window.addEventListener('resize', bump);
    const observer = new ResizeObserver(bump);
    if (wrapperRef.current) observer.observe(wrapperRef.current);
    return () => {
      window.removeEventListener('resize', bump);
      observer.disconnect();
    };
  }, []);

  // Track theme changes so SVG stroke hexes follow light/dark
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setIsDark(document.documentElement.classList.contains('dark'))
    );
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  // Load the focused page's content into the reading panel
  useEffect(() => {
    if (!focusId) {
      setPageContent(null);
      setPageError(null);
      return;
    }
    let cancelled = false;
    setPageLoading(true);
    setPageError(null);
    fetch(`${API_BASE}/pages/${focusId}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load page');
        return res.json();
      })
      .then((data: { content: string }) => {
        if (cancelled) return;
        setPageContent(data.content);
        panelBodyRef.current?.scrollTo({ top: 0 });
      })
      .catch((err: any) => {
        if (!cancelled) setPageError(err.message);
      })
      .finally(() => {
        if (!cancelled) setPageLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [focusId]);

  // Undirected adjacency: hover/focus highlights pages this page links to
  // AND pages that link to it, matching how backlinks read in the wiki.
  const neighbors = useMemo(() => {
    const map = new Map<string, Set<string>>();
    if (!graph) return map;
    for (const node of graph.nodes) map.set(node.id, new Set());
    for (const edge of graph.edges) {
      map.get(edge.source)?.add(edge.target);
      map.get(edge.target)?.add(edge.source);
    }
    return map;
  }, [graph]);

  const groupIndex = useMemo(() => {
    const map = new Map<string, number>();
    graph?.groups.forEach((g, i) => map.set(g.id, i % GROUP_PALETTE.length));
    return map;
  }, [graph]);

  const paletteFor = (groupId: string) => GROUP_PALETTE[groupIndex.get(groupId) ?? 0];
  const strokeFor = (groupId: string) => {
    const p = paletteFor(groupId);
    return isDark ? p.strokeDark : p.stroke;
  };

  const nodesByGroup = useMemo(() => {
    const map = new Map<string, GraphNode[]>();
    if (!graph) return map;
    for (const group of graph.groups) map.set(group.id, []);
    for (const node of graph.nodes) {
      if (!map.has(node.group)) map.set(node.group, []);
      map.get(node.group)!.push(node);
    }
    for (const list of map.values()) list.sort((a, b) => a.title.localeCompare(b.title));
    return map;
  }, [graph]);

  const nodeById = useMemo(() => {
    const map = new Map<string, GraphNode>();
    graph?.nodes.forEach(n => map.set(n.id, n));
    return map;
  }, [graph]);

  // Measure chip centers relative to the wrapper and build one curve per
  // connection of the active node. Curves attach to the top/bottom edge of
  // each chip so they read as leaving the pill, not crossing through it.
  useLayoutEffect(() => {
    if (!activeId || !wrapperRef.current) {
      setLines([]);
      return;
    }
    const wrapperRect = wrapperRef.current.getBoundingClientRect();
    const sourceEl = chipRefs.current.get(activeId);
    if (!sourceEl) {
      setLines([]);
      return;
    }
    const anchor = (el: HTMLElement, towardY: number) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2 - wrapperRect.left;
      const cy = r.top + r.height / 2 - wrapperRect.top;
      const edgeY = towardY > cy ? r.bottom - wrapperRect.top : r.top - wrapperRect.top;
      return { x: cx, y: edgeY, cy };
    };
    const next: CurveLine[] = [];
    for (const targetId of neighbors.get(activeId) ?? []) {
      const targetEl = chipRefs.current.get(targetId);
      if (!targetEl) continue;
      const targetRect = targetEl.getBoundingClientRect();
      const targetCenterY = targetRect.top + targetRect.height / 2 - wrapperRect.top;
      const sourceRect = sourceEl.getBoundingClientRect();
      const sourceCenterY = sourceRect.top + sourceRect.height / 2 - wrapperRect.top;
      const from = anchor(sourceEl, targetCenterY);
      const to = anchor(targetEl, sourceCenterY);
      const dy = to.y - from.y;
      const pull = Math.max(Math.abs(dy) * 0.45, 36);
      const dir = Math.sign(dy || 1);
      const path = `M ${from.x} ${from.y} C ${from.x} ${from.y + dir * pull}, ${to.x} ${to.y - dir * pull}, ${to.x} ${to.y}`;
      next.push({ path, key: `${activeId}->${targetId}` });
    }
    setLines(next);
  }, [activeId, neighbors, graph, measureTick]);

  const setChipRef = useCallback((id: string) => (el: HTMLButtonElement | null) => {
    if (el) chipRefs.current.set(id, el);
    else chipRefs.current.delete(id);
  }, []);

  const handleChipClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setFocusId(prev => (prev === id ? null : id));
  };

  const reset = () => {
    setFocusId(null);
    setHoverId(null);
  };

  // Convert [[folder/page]] wikilinks to internal markdown anchors
  // (#folder__page), same scheme WikiView uses, so they render as links.
  const processWikiLinks = (text: string) =>
    text.replace(/\[\[(.*?)\]\]/g, (_match, ref: string) => {
      const target = ref.trim();
      const path = `${target}.md`;
      const label = nodeById.get(path)?.title
        ?? target.split('/').pop()?.replace(/-/g, ' ')
        ?? target;
      return `[${label}](#${target.replace(/\//g, '__')})`;
    });

  if (loading) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full w-full overflow-y-auto">
        <div className="p-8 md:p-12 max-w-4xl mx-auto">
          <h1 className="text-4xl font-extrabold text-gray-900 dark:text-gray-100 mb-6 tracking-tight">Link View</h1>
          <div className="p-4 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 rounded-xl text-red-700 dark:text-red-400 text-sm">
            {error}
          </div>
        </div>
      </div>
    );
  }

  const activeNode = activeId ? nodeById.get(activeId) : null;
  const activeStroke = activeNode ? strokeFor(activeNode.group) : '#3b82f6';
  const connected = activeId ? neighbors.get(activeId) ?? new Set<string>() : new Set<string>();
  const dimChrome = mode !== 'rest';
  const focusedNode = focusId ? nodeById.get(focusId) : null;
  const parsed = pageContent !== null ? splitFrontmatter(pageContent) : null;

  return (
    <div className="h-full w-full flex flex-col" onClick={reset}>
      <style>{`@keyframes linkview-draw { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }`}</style>
      <div className="flex-1 relative overflow-hidden">
        <div className="h-full overflow-y-auto">
          <div className="p-8 md:p-12 max-w-7xl mx-auto pb-16">
            <h1 className="text-4xl font-extrabold text-gray-900 dark:text-gray-100 mb-3 tracking-tight">Link View</h1>
            <p className="text-xl text-gray-500 dark:text-gray-400 mb-8 leading-relaxed">
              Every page and its wikilinks in one map. Hover a page to see its connections; click to focus and read it.
            </p>

            {graph && graph.nodes.length === 0 && (
              <div className="p-8 text-center text-gray-400 dark:text-gray-600 border border-dashed border-gray-300 dark:border-gray-700 rounded-2xl">
                <Network className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p>No pages yet — ingest some sources and the link map will build itself.</p>
              </div>
            )}

            <div ref={wrapperRef} className="relative space-y-6">
              {graph?.groups.map(group => {
                const groupNodes = nodesByGroup.get(group.id) ?? [];
                if (groupNodes.length === 0) return null;
                const palette = paletteFor(group.id);
                return (
                  <section
                    key={group.id}
                    className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5"
                  >
                    <div className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 transition-opacity duration-200 ${dimChrome ? 'opacity-30' : 'opacity-100'}`}>
                      <span className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${palette.dot}`} />
                        <span className={`text-xs font-bold uppercase tracking-widest ${palette.title}`}>{group.name}</span>
                      </span>
                      {group.description && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">{group.description}</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 mt-4">
                      {groupNodes.map(node => {
                        const isActive = node.id === activeId;
                        const isFocused = node.id === focusId;
                        const isConnected = connected.has(node.id);
                        const highlighted = isActive || isFocused || isConnected;
                        const dimmed = mode !== 'rest' && !highlighted;
                        return (
                          <button
                            key={node.id}
                            ref={setChipRef(node.id)}
                            onMouseEnter={() => setHoverId(node.id)}
                            onMouseLeave={() => setHoverId(null)}
                            onClick={(e) => handleChipClick(e, node.id)}
                            style={highlighted ? { borderColor: activeStroke } : undefined}
                            className={`px-3 py-1.5 rounded-full border text-sm font-medium transition-all duration-200 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                              isActive || isFocused
                                ? 'bg-blue-50 dark:bg-gray-800 text-gray-900 dark:text-white shadow-sm'
                                : isConnected
                                  ? 'bg-white dark:bg-gray-800/80 text-gray-800 dark:text-gray-100'
                                  : 'bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300'
                            } ${dimmed ? (mode === 'focus' ? 'opacity-15' : 'opacity-25') : 'opacity-100'}`}
                          >
                            {node.title}
                          </button>
                        );
                      })}
                    </div>
                  </section>
                );
              })}

              {lines.length > 0 && (
                <svg className="absolute inset-0 w-full h-full pointer-events-none z-10 overflow-visible" style={{ margin: 0 }}>
                  {lines.map(line => (
                    <path
                      key={line.key}
                      d={line.path}
                      fill="none"
                      stroke={activeStroke}
                      strokeWidth={mode === 'focus' ? 2.5 : 1.5}
                      strokeLinecap="round"
                      opacity={mode === 'focus' ? 0.95 : 0.65}
                      pathLength={1}
                      strokeDasharray={1}
                      style={{ animation: 'linkview-draw 300ms ease-out forwards' }}
                    />
                  ))}
                </svg>
              )}
            </div>
          </div>
        </div>

        {/* Reading panel — slides in from the right when a page is focused */}
        {/* Slide transform + visibility live in inline styles, not Tailwind
            classes: prod serves CSS through a CDN cache, and a stale
            stylesheet missing a class new to this component would leave the
            closed panel parked over the whole map. Inline styles can't go
            stale independently of the component. max-w-md (28rem) is used
            app-wide, so it exists in any cached stylesheet. */}
        <aside
          onClick={(e) => e.stopPropagation()}
          aria-hidden={!focusId}
          style={{
            transform: focusId ? 'translateX(0)' : 'translateX(100%)',
            visibility: focusId ? 'visible' : 'hidden',
            transition: 'transform 300ms ease-in-out, visibility 300ms',
          }}
          className="absolute inset-y-0 right-0 z-20 w-full max-w-md bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 shadow-2xl flex flex-col"
        >
          <div className="shrink-0 px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                {focusedNode && (
                  <span className={`w-2 h-2 rounded-full shrink-0 ${paletteFor(focusedNode.group).dot}`} />
                )}
                <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">
                  {focusedNode?.title ?? ''}
                </h2>
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500 font-mono truncate mt-0.5">{focusId}</p>
            </div>
            <button
              onClick={reset}
              title="Close"
              aria-label="Close reading panel"
              className="p-2 -mr-2 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div ref={panelBodyRef} className="flex-1 overflow-y-auto px-6 py-5">
            {pageLoading && (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading page…</span>
              </div>
            )}
            {pageError && (
              <div className="p-4 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 rounded-xl text-red-700 dark:text-red-400 text-sm">
                {pageError}
              </div>
            )}
            {!pageLoading && !pageError && parsed && (
              <>
                {parsed.fields.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    {parsed.fields.map(([key, value]) => (
                      <span
                        key={key}
                        className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                      >
                        <span className="text-gray-400 dark:text-gray-500 mr-1.5 text-[10px] uppercase tracking-wider">{key}</span>
                        {value.replace(/\[\[|\]\]/g, '')}
                      </span>
                    ))}
                  </div>
                )}
                <div className="prose prose-sm prose-slate dark:prose-invert max-w-none break-words">
                  <ReactMarkdown
                    components={{
                      a: ({ node: _n, ...props }) => {
                        if (props.href?.startsWith('#')) {
                          const pagePath = `${props.href.slice(1).replace(/__/g, '/')}.md`;
                          const exists = nodeById.has(pagePath);
                          return (
                            <a
                              {...props}
                              onClick={(e) => {
                                e.preventDefault();
                                if (exists) setFocusId(pagePath);
                              }}
                              className={exists
                                ? 'text-blue-600 dark:text-blue-400 hover:underline cursor-pointer font-medium'
                                : 'text-gray-400 dark:text-gray-500 cursor-default no-underline'}
                            >
                              {props.children}
                            </a>
                          );
                        }
                        return (
                          <a {...props} className="text-blue-600 dark:text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer" />
                        );
                      },
                    }}
                  >
                    {processWikiLinks(parsed.body)}
                  </ReactMarkdown>
                </div>
              </>
            )}
          </div>
          {focusedNode && (
            <div className="shrink-0 px-6 py-3 border-t border-gray-200 dark:border-gray-800 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
              <FileText className="w-3.5 h-3.5" />
              <span>
                {(neighbors.get(focusedNode.id)?.size ?? 0)} {(neighbors.get(focusedNode.id)?.size ?? 0) === 1 ? 'connection' : 'connections'}
              </span>
            </div>
          )}
        </aside>
      </div>

      <div className="shrink-0 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-6 py-2.5 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>
          <span className="font-semibold text-gray-700 dark:text-gray-300">{graph?.nodes.length ?? 0} nodes</span>
          {' · '}
          <span className="font-semibold text-gray-700 dark:text-gray-300">{graph?.edges.length ?? 0} connections</span>
          {activeNode && (
            <span className="ml-3" style={{ color: activeStroke }}>
              {activeNode.title} — {connected.size} {connected.size === 1 ? 'link' : 'links'}
            </span>
          )}
        </span>
        <span>Esc or click the background to reset</span>
      </div>
    </div>
  );
};

export default LinkView;
