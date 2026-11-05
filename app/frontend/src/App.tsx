import { useEffect, useRef, useState } from 'react'
import './App.css'

type Box = { x: number; y: number; w: number; h: number }
type Line = { id?: string; points: number[][] }
type Candidate = { text: string; confidence: number }
type Word = { id: string; line: number; box: Box; predicted: string; confidence: number; text: string; status: string; candidates: Candidate[] }
type RecordData = { id: string; source_image: string; box: Box; group_id?: string; lines: Line[]; words: Word[]; status: string }
type Page = 'home' | 'new' | 'pending' | 'review' | 'saved' | 'folders' | 'groups'

const menu: { label: string; page: Page }[] = [
  { label: 'Início', page: 'home' }, { label: 'Novo registro', page: 'new' },
  { label: 'Não analisados', page: 'pending' }, { label: 'Em análise', page: 'review' },
  { label: 'Prontos', page: 'saved' }, { label: 'Coleções', page: 'folders' },
  { label: 'Grupos de registros', page: 'groups' },
]

async function api<T>(url: string, body?: unknown, method?: string): Promise<T> {
  const requestMethod = method ?? (body === undefined ? 'GET' : 'POST')
  const response = await fetch(url, {
    method: requestMethod,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const raw = await response.text()
  let data: { error?: string }
  try { data = JSON.parse(raw) as { error?: string } } catch { throw new Error(`Servidor retornou ${response.status}.`) }
  if (!response.ok) throw new Error(data.error ?? response.statusText)
  return data as T
}

function imageUrl(name: string) {
  return `/api/image/${name.split('/').map(encodeURIComponent).join('/')}`
}

function App() {
  const [page, setPage] = useState<Page>('home')
  const [collapsed, setCollapsed] = useState(false)
  const [images, setImages] = useState<string[]>([])
  const [records, setRecords] = useState<RecordData[]>([])
  const [currentImage, setCurrentImage] = useState('')
  const [record, setRecord] = useState<RecordData | null>(null)
  const [selected, setSelected] = useState(-1)
  const [selectedLine, setSelectedLine] = useState(-1)
  const [mode, setMode] = useState<'idle' | 'draw' | 'edit' | 'review'>('idle')
  const [scale, setScale] = useState(1)
  const [message, setMessage] = useState('')
  const [groupId, setGroupId] = useState('')
  const [authOpen, setAuthOpen] = useState(false)
  const imageRef = useRef<HTMLImageElement>(new Image())
  const bgRef = useRef<HTMLCanvasElement>(null)
  const fgRef = useRef<HTMLCanvasElement>(null)
  const viewRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ kind: string; startX: number; startY: number; box?: Box; line?: number; node?: number } | null>(null)
  const panRef = useRef<{ x: number; y: number; left: number; top: number } | null>(null)

  const loadData = async () => {
    const [imageList, recordList] = await Promise.all([api<string[]>('/api/images'), api<RecordData[]>('/api/records/all')])
    setImages(imageList); setRecords(recordList)
  }
  useEffect(() => { void loadData() }, [])

  const paint = () => {
    const bg = bgRef.current; const fg = fgRef.current; const image = imageRef.current
    if (!bg || !fg || !image.complete) return
    bg.width = fg.width = Math.round(image.naturalWidth * scale); bg.height = fg.height = Math.round(image.naturalHeight * scale)
    const bctx = bg.getContext('2d'); const ctx = fg.getContext('2d')
    if (!bctx || !ctx) return
    bctx.drawImage(image, 0, 0, bg.width, bg.height); ctx.clearRect(0, 0, fg.width, fg.height)
    if (!record) return
    const box = (b: Box, fill: string, stroke: string) => { ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.fillRect(b.x * scale, b.y * scale, b.w * scale, b.h * scale); ctx.strokeRect(b.x * scale, b.y * scale, b.w * scale, b.h * scale) }
    box(record.box, 'rgba(40,120,255,.1)', '#58f')
    record.lines.forEach((line, index) => {
      ctx.beginPath(); line.points.forEach((point, i) => i ? ctx.lineTo(point[0] * scale, point[1] * scale) : ctx.moveTo(point[0] * scale, point[1] * scale)); ctx.closePath()
      ctx.strokeStyle = index === selectedLine ? '#e90' : '#48f'; ctx.fillStyle = index === selectedLine ? 'rgba(255,220,0,.18)' : 'rgba(40,120,255,.08)'; ctx.stroke(); ctx.fill()
      if (mode === 'edit') line.points.forEach(point => { ctx.fillStyle = index === selectedLine ? '#e90' : '#48f'; ctx.fillRect(point[0] * scale - 4, point[1] * scale - 4, 8, 8) })
    })
    record.words.forEach((word, index) => box(word.box, index === selected ? 'rgba(255,220,0,.55)' : word.status === 'reviewed' ? 'rgba(70,190,70,.35)' : 'rgba(255,170,0,.25)', index === selected ? '#cc0' : word.status === 'reviewed' ? '#2a2' : '#d90'))
  }
  useEffect(() => { paint() }, [record, scale, selected, selectedLine, mode])

  const openImage = async (name: string, nextMode: 'idle' | 'draw' = 'idle') => {
    setCurrentImage(name); setRecord(null); setSelected(-1); setSelectedLine(-1); setMode(nextMode); setMessage('')
    const image = new Image(); image.onload = () => { imageRef.current = image; setScale(Math.min(1, ((viewRef.current?.clientWidth ?? 800) - 20) / image.naturalWidth)); void loadRecord(name) }; image.onerror = () => setMessage('Não foi possível carregar a imagem.'); image.src = imageUrl(name)
  }
  const loadRecord = async (name: string) => {
    const found = (await api<RecordData[]>(`/api/records?image=${encodeURIComponent(name)}`)).at(-1)
    if (found) { setRecord(found); setGroupId(found.group_id ?? ''); setMode('edit') } else { setMode('draw'); setMessage('Desenhe o retângulo completo do registro.') }
  }
  const openWorkspace = (name: string, nextMode: 'idle' | 'draw' = 'draw') => { setPage('new'); void openImage(name, nextMode) }
  const beginNew = () => { setPage('new'); setRecord(null); setMode('draw'); setMessage('Desenhe o retângulo completo do registro.'); if (images[0]) void openImage(images[0], 'draw') }
  const zoom = (factor: number) => setScale(value => Math.max(.1, Math.min(8, value * factor)))

  const canvasPoint = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: (event.clientX - rect.left) / scale, y: (event.clientY - rect.top) / scale }
  }
  const startCanvas = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (event.button !== 0 || (event.currentTarget !== fgRef.current) || (mode !== 'draw' && mode !== 'edit')) return
    const point = canvasPoint(event)
    if (mode === 'edit' && record) {
      for (let li = 0; li < record.lines.length; li++) {
        const points = record.lines[li].points; const hit = points.findIndex(node => Math.hypot(point.x - node[0], point.y - node[1]) < 14)
        const inside = point.x >= Math.min(...points.map(p => p[0])) - 14 && point.x <= Math.max(...points.map(p => p[0])) + 14 && point.y >= Math.min(...points.map(p => p[1])) - 14 && point.y <= Math.max(...points.map(p => p[1])) + 14
        if (inside) { setSelectedLine(li); setSelected(-1); dragRef.current = hit >= 0 ? { kind: 'line', line: li, node: hit, startX: point.x, startY: point.y } : null; return }
      }
      const wordIndex = record.words.findIndex(word => point.x >= word.box.x && point.x <= word.box.x + word.box.w && point.y >= word.box.y && point.y <= word.box.y + word.box.h)
      if (wordIndex >= 0) { const word = record.words[wordIndex]; setSelected(wordIndex); setSelectedLine(-1); dragRef.current = { kind: point.x >= word.box.x + word.box.w - 14 && point.y >= word.box.y + word.box.h - 14 ? 'resize' : 'word', startX: point.x, startY: point.y, box: { ...word.box } }; return }
    }
    dragRef.current = { kind: 'draw', startX: point.x, startY: point.y, box: { x: point.x, y: point.y, w: 0, h: 0 } }
  }
  const moveCanvas = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current; if (!drag) return; const point = canvasPoint(event)
    if (drag.kind === 'line' && record && drag.line !== undefined && drag.node !== undefined) { const lines = [...record.lines]; lines[drag.line] = { ...lines[drag.line], points: lines[drag.line].points.map((node, i) => i === drag.node ? [Math.round(point.x), Math.round(point.y)] : node) }; setRecord({ ...record, lines }); return }
    if ((drag.kind === 'word' || drag.kind === 'resize') && record && drag.box) { const words = [...record.words]; const word = words[selected]; const nextBox = drag.kind === 'resize' ? { ...word.box, w: Math.max(4, Math.round(drag.box.w + point.x - drag.startX)), h: Math.max(4, Math.round(drag.box.h + point.y - drag.startY)) } : { ...word.box, x: Math.max(0, Math.round(drag.box.x + point.x - drag.startX)), y: Math.max(0, Math.round(drag.box.y + point.y - drag.startY)) }; words[selected] = { ...word, box: nextBox }; setRecord({ ...record, words }); return }
    drag.box = { x: Math.min(drag.startX, point.x), y: Math.min(drag.startY, point.y), w: Math.abs(point.x - drag.startX), h: Math.abs(point.y - drag.startY) }; setRecord(record ? { ...record } : null)
  }
  const finishCanvas = async () => {
    const drag = dragRef.current; dragRef.current = null; if (!drag || !drag.box || drag.box.w < 5 || drag.box.h < 5) return
    if (drag.kind === 'draw' && currentImage) {
      try { const analyzed = await api<RecordData>('/api/records/analyze', { image: currentImage, box: drag.box }); setRecord(analyzed); setMode('edit'); setMessage('Rascunho não salvo. Corrija e clique em Salvar registro.') } catch (error) { setMessage(error instanceof Error ? error.message : 'Falha ao analisar registro.') }
    }
  }

  const save = async () => { if (!record) return; try { const saved = await api<RecordData>('/api/records/save', { ...record, group_id: groupId }); setRecord(saved); await loadData(); setMessage('Registro salvo.') } catch (error) { setMessage(error instanceof Error ? error.message : 'Falha ao salvar.') } }
  const resegment = async () => { if (!record) return; const updated = await api<RecordData>(`/api/records/${encodeURIComponent(record.id)}/resegment`, record, 'POST'); setRecord(updated); setSelected(-1); setMessage('Palavras reidentificadas pelas linhas.') }
  const updateText = (text: string) => { if (!record || selected < 0) return; const words = [...record.words]; words[selected] = { ...words[selected], text, status: 'reviewed' }; setRecord({ ...record, words }) }
  const deleteWord = () => { if (!record || selected < 0) return; setRecord({ ...record, words: record.words.filter((_, index) => index !== selected) }); setSelected(-1); setMessage('Palavra excluída do rascunho. Salve para manter.') }
  const startPan = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.button !== 1 || !viewRef.current) return
    event.preventDefault(); panRef.current = { x: event.clientX, y: event.clientY, left: viewRef.current.scrollLeft, top: viewRef.current.scrollTop }
  }
  const movePan = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!panRef.current || !viewRef.current) return
    viewRef.current.scrollLeft = panRef.current.left - (event.clientX - panRef.current.x)
    viewRef.current.scrollTop = panRef.current.top - (event.clientY - panRef.current.y)
  }
  const stopPan = () => { panRef.current = null }

  const homeContent = () => <><section className="welcome-card"><p className="eyebrow">HTR Genealogia</p><h1>Página inicial</h1><p>Escolha uma ação para analisar registros manuscritos em português.</p></section><section className="feature-grid">{['Novo registro', 'Não analisados', 'Em análise', 'Prontos', 'Coleções'].map(label => <button className="feature-card action-card" key={label} onClick={() => label === 'Novo registro' ? beginNew() : setPage(menu.find(item => item.label === label)?.page ?? 'home')} type="button"><strong>{label}</strong><span> Abrir seção</span></button>)}</section></>
  const collectionContent = () => { const folders = images.reduce<Record<string, string[]>>((all, name) => { const parts = name.split('/'); const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : 'Coleção avulsa'; (all[folder] ??= []).push(name); return all }, {}); return <><h1>Coleções</h1><p className="hint">Cada subpasta em <code>dataset/originals</code> aparece como uma coleção.</p>{Object.entries(folders).map(([folder, names]) => <section className="collection" key={folder}><h2>{folder}</h2><div className="image-grid">{names.map(name => <button className="image-card" key={name} onClick={() => openWorkspace(name)} type="button"><img src={imageUrl(name)} alt={name} /><span>{name.split('/').pop()}</span></button>)}</div></section>)}</> }
  const listContent = (kind: 'pending' | 'review' | 'saved') => { const used = new Set(records.map(item => item.source_image)); const data = kind === 'pending' ? images.filter(name => !used.has(name)) : records.filter(item => kind === 'saved' ? item.status === 'reviewed' : item.status === 'pending'); return <><h1>{kind === 'pending' ? 'Não analisados' : kind === 'review' ? 'Em análise' : 'Prontos'}</h1><div className="image-grid">{data.map(item => { const name = typeof item === 'string' ? item : item.source_image; return <button className="image-card" key={name} onClick={() => openWorkspace(name, kind === 'pending' ? 'draw' : 'idle')} type="button"><img src={imageUrl(name)} alt={name} /><span>{name}</span><b>Abrir</b></button> })}</div></> }

  return <div className="app-shell">
    <header className="topbar"><strong>HTR Genealogia</strong><span>{menu.find(item => item.page === page)?.label ?? 'Em análise'}</span><button className="collapse-top" onClick={() => setCollapsed(!collapsed)} type="button">☰</button><button className="account-button" onClick={() => setAuthOpen(true)} type="button">Entrar / Cadastrar</button></header>
    <div className="app-body"><nav className={collapsed ? 'sidebar collapsed' : 'sidebar'}><button className="collapse-button" onClick={() => setCollapsed(!collapsed)} type="button">☰</button>{!collapsed && menu.map(item => <button className={item.page === page ? 'nav-item active' : 'nav-item'} key={item.page} onClick={() => item.page === 'new' ? beginNew() : setPage(item.page)} type="button">{item.label}</button>)}</nav>
      {page === 'new' ? <Editor /> : <main className="content">{page === 'home' ? homeContent() : page === 'folders' ? collectionContent() : page === 'pending' || page === 'review' || page === 'saved' ? listContent(page) : <><h1>Grupos de registros</h1>{records.map(item => <div className="card" key={item.id}><b>{item.group_id || 'Sem grupo'}</b><p>{item.source_image}</p></div>)}</>}</main>}
    </div>{authOpen && <div className="modal" onClick={event => { if (event.target === event.currentTarget) setAuthOpen(false) }}><form className="auth-card" onSubmit={event => { event.preventDefault(); setAuthOpen(false) }}><button className="modal-close" onClick={() => setAuthOpen(false)} type="button">×</button><h2>Entrar / Cadastrar</h2><label>E-mail<input type="email" required /></label><label>Senha<input type="password" required /></label><button type="submit">Continuar</button><small>Demonstração visual. Login e cadastro ainda não estão conectados.</small></form></div>}
  </div>

  function Editor() {
    const selectedWord = record && selected >= 0 ? record.words[selected] : null
    return <main className="editor"><div className="editor-toolbar"><select value={currentImage} onChange={event => void openImage(event.target.value)}>{images.map(name => <option key={name}>{name}</option>)}</select><button onClick={() => zoom(.8)} type="button">−</button><span>{Math.round(scale * 100)}%</span><button onClick={() => zoom(1.25)} type="button">+</button><button disabled={!record} onClick={() => setMode(mode === 'edit' ? 'review' : 'edit')} type="button">Editar linhas e palavras</button><button disabled={!record} onClick={() => void resegment()} type="button">Reidentificar palavras</button><button disabled={!record} onClick={() => void save()} type="button">Salvar registro</button></div><div className="editor-main"><div className="canvas-view" ref={viewRef} onMouseDown={startPan} onMouseMove={movePan} onMouseUp={stopPan} onMouseLeave={stopPan} onWheel={event => { if (event.ctrlKey) { event.preventDefault(); zoom(event.deltaY < 0 ? 1.1 : .9) } }}><div className="canvas-stack"><canvas ref={bgRef} /><canvas ref={fgRef} onMouseDown={startCanvas} onMouseMove={moveCanvas} onMouseUp={() => void finishCanvas()} /></div></div><aside className="review-panel"><h2>Palavras do registro</h2><label>Grupo<input value={groupId} onChange={event => setGroupId(event.target.value)} placeholder="ex.: batismo-joao-1890" /></label>{record?.words.map((word, index) => <button className={`word ${word.status} ${index === selected ? 'selected' : ''}`} key={word.id} onClick={() => { setSelected(index); setSelectedLine(-1); setMode('review') }} type="button"><span>{index + 1}. {word.text || word.predicted || '(sem leitura)'}</span><small>{Math.round(word.confidence * 100)}%</small></button>)}{selectedWord && <><div className="candidates">{selectedWord.candidates.map(candidate => <button key={candidate.text} onClick={() => updateText(candidate.text)} type="button">{candidate.text} — {Math.round(candidate.confidence * 100)}%</button>)}</div><input value={selectedWord.text || selectedWord.predicted} onChange={event => updateText(event.target.value)} /><button onClick={() => updateText(selectedWord.text)} type="button">Revisar palavra</button><button onClick={deleteWord} type="button">Excluir palavra</button></>}{message && <p className="message">{message}</p>}</aside></div></main>
  }
}

export default App
