import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { marked } from 'marked'
import { Calendar, Car, Newspaper, GraduationCap, Briefcase, DollarSign, MessageSquare, Search, Plus, LogOut, Send, ExternalLink, Radio, X, LayoutDashboard } from 'lucide-react'

const SUGGESTIONS = [
  { icon: Calendar, text: 'Events this week' },
  { icon: Car, text: 'Parking spaces now' },
  { icon: Newspaper, text: 'Latest NEU news' },
  { icon: GraduationCap, text: 'How do I apply?' },
  { icon: Briefcase, text: 'Co-op programs' },
  { icon: DollarSign, text: 'Financial aid info' },
]

export default function Chat() {
  const nav = useNavigate()
  const [user, setUser] = useState(null)
  const [convos, setConvos] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [search, setSearch] = useState('')
  const [panel, setPanel] = useState(null)
  const [liveData, setLiveData] = useState(null)
  const chatRef = useRef(null)
  const inputRef = useRef(null)

  // Auth
  useEffect(() => {
    fetch('/api/me', { credentials: 'include' }).then(r => { if (!r.ok) throw 0; return r.json() }).then(setUser).catch(() => nav('/login'))
  }, [nav])

  // Load conversations
  const loadConvos = useCallback(async () => {
    try { const r = await fetch('/api/conversations', { credentials: 'include' }); setConvos(await r.json()) } catch {}
  }, [])
  useEffect(() => { loadConvos() }, [loadConvos])

  // Load live data
  useEffect(() => {
    const load = async () => { try { const r = await fetch('/api/live-feed', { credentials: 'include' }); setLiveData(await r.json()) } catch {} }
    load(); const i = setInterval(load, 120000); return () => clearInterval(i)
  }, [])

  // Auto-scroll
  useEffect(() => { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' }) }, [msgs, sending])

  const openConvo = async (id) => {
    setActiveId(id); setPanel(null)
    try { const r = await fetch(`/api/conversations/${id}`, { credentials: 'include' }); const d = await r.json(); setMsgs(d.messages || []) } catch { setMsgs([{ role: 'assistant', content: 'Could not load conversation.' }]) }
  }

  const deleteConvo = async (e, id) => {
    e.stopPropagation()
    await fetch(`/api/conversations/${id}`, { method: 'DELETE', credentials: 'include' })
    if (activeId === id) { setActiveId(null); setMsgs([]) }
    setConvos(c => c.filter(x => x.id !== id))
  }

  const send = async (text) => {
    const msg = (text || input).trim()
    if (!msg || sending) return
    setInput(''); setSending(true)
    setMsgs(prev => [...prev, { role: 'user', content: msg }])
    try {
      const r = await fetch('/chat', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg, conversation_id: activeId }) })
      const txt = await r.text()
      let d
      try { d = JSON.parse(txt) } catch { d = { error: `Server error (${r.status}): ${txt.slice(0, 200)}` } }
      setSending(false)
      if (d.error) { setMsgs(prev => [...prev, { role: 'assistant', content: 'Sorry \u2014 ' + d.error }]) }
      else { setMsgs(prev => [...prev, { role: 'assistant', content: d.answer }]); if (!activeId) setActiveId(d.conversation_id); loadConvos() }
    } catch (err) { setSending(false); setMsgs(prev => [...prev, { role: 'assistant', content: 'Connection error: ' + err.message }]) }
  }

  const newChat = () => { setActiveId(null); setMsgs([]); inputRef.current?.focus() }

  const groupConvos = (list) => {
    const now = new Date(); now.setHours(0,0,0,0)
    const yday = new Date(now); yday.setDate(yday.getDate() - 1)
    const groups = { Today: [], Yesterday: [], 'This week': [], Earlier: [] }
    list.forEach(c => {
      const d = new Date(c.updated_at)
      if (d >= now) groups.Today.push(c)
      else if (d >= yday) groups.Yesterday.push(c)
      else if ((now - d) < 7 * 86400000) groups['This week'].push(c)
      else groups.Earlier.push(c)
    })
    return groups
  }

  const filtered = convos.filter(c => c.title.toLowerCase().includes(search.toLowerCase()))
  const groups = groupConvos(filtered)
  const showWelcome = msgs.length === 0

  if (!user) return null

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#f7f7f7', fontFamily: "'Inter', -apple-system, sans-serif" }}>
      <style>{`
        @keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}
        .bot-bubble h1,.bot-bubble h2,.bot-bubble h3{font-size:14px;font-weight:700;margin:12px 0 6px}
        .bot-bubble p{margin:0 0 8px;line-height:1.65}.bot-bubble p:last-child{margin:0}
        .bot-bubble ul,.bot-bubble ol{padding-left:18px;margin:4px 0 8px}
        .bot-bubble li{margin-bottom:4px;line-height:1.6}
        .bot-bubble strong{font-weight:700;color:#111}
        .bot-bubble code{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;padding:1px 5px;font-family:monospace;font-size:12.5px}
        .bot-bubble pre{background:#222;border-radius:8px;padding:12px 14px;margin:8px 0;overflow-x:auto}
        .bot-bubble pre code{background:none;border:none;padding:0;color:#e2e8f0}
        .bot-bubble a{color:#ff385c;text-decoration:underline}
        .bot-bubble blockquote{border-left:3px solid #ff385c;padding-left:12px;color:#555;margin:8px 0;font-style:italic}
      `}</style>

      {/* Sidebar */}
      <aside style={{ width: 260, background: '#fff', borderRight: '1px solid #ebebeb', display: 'flex', flexDirection: 'column', height: '100vh', flexShrink: 0 }}>
        <div style={{ padding: '18px 14px 12px', display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ width: 30, height: 30, background: 'linear-gradient(135deg, #ff385c, #e00b41)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <GraduationCap size={15} color="#fff" strokeWidth={2.5} />
          </div>
          <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: '-0.3px' }}>NEU Assistant</span>
        </div>

        {/* Search */}
        <div style={{ padding: '0 10px 10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#f7f7f7', border: '1px solid #ebebeb', borderRadius: 8, padding: '7px 11px' }}>
            <Search size={13} color="#6a6a6a" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search conversations..." style={{ border: 'none', outline: 'none', background: 'transparent', fontSize: 13, width: '100%', color: '#222' }} />
          </div>
        </div>

        {/* Nav */}
        <div style={{ padding: '4px 10px 6px' }}>
          {[
            { label: 'Chat', Icon: MessageSquare, onClick: () => setPanel(null) },
            { label: 'Events', Icon: Calendar, onClick: () => setPanel('events'), live: true },
            { label: 'News', Icon: Newspaper, onClick: () => setPanel('news'), live: true },
            { label: 'Parking', Icon: Car, onClick: () => setPanel('parking'), live: true },
          ].map(n => {
            const active = panel === n.label?.toLowerCase() || (!panel && n.label === 'Chat')
            return (
              <div key={n.label} onClick={n.onClick} style={{
                display: 'flex', alignItems: 'center', gap: 9, padding: '8px 10px', borderRadius: 8,
                cursor: 'pointer', fontSize: 13, fontWeight: 500, color: active ? '#222' : '#6a6a6a',
                background: active ? '#f2f2f2' : 'transparent', transition: 'all 0.15s',
              }}>
                <n.Icon size={16} strokeWidth={active ? 2 : 1.5} /> {n.label}
                {n.live && <span style={{ marginLeft: 'auto', width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />}
              </div>
            )
          })}
        </div>

        {/* History */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 10px', minHeight: 0 }}>
          {Object.entries(groups).map(([label, items]) => items.length > 0 && (
            <div key={label}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#6a6a6a', textTransform: 'uppercase', letterSpacing: 0.6, padding: '10px 10px 4px' }}>{label}</div>
              {items.map(c => (
                <div key={c.id} onClick={() => openConvo(c.id)} style={{
                  padding: '7px 10px', borderRadius: 8, fontSize: 13, color: c.id === activeId ? '#222' : '#6a6a6a',
                  background: c.id === activeId ? '#f2f2f2' : 'transparent',
                  cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.title}</span>
                  <span onClick={e => deleteConvo(e, c.id)} style={{ fontSize: 14, color: '#6a6a6a', opacity: 0, cursor: 'pointer', flexShrink: 0 }}
                    onMouseEnter={e => e.target.style.opacity = 1} onMouseLeave={e => e.target.style.opacity = 0}><X size={12} /></span>
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* User footer */}
        <div style={{ padding: '12px 14px', borderTop: '1px solid #ebebeb', display: 'flex', alignItems: 'center', gap: 9 }}>
          {user.avatar ? <img src={user.avatar} alt="" style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover' }} /> :
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, #ff385c, #e00b41)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: '#fff' }}>{user.name?.[0]?.toUpperCase() || 'U'}</div>}
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.name}</div>
            <div style={{ fontSize: 11, color: '#6a6a6a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.email}</div>
          </div>
          <a href="/logout" title="Sign out" style={{ width: 26, height: 26, borderRadius: 6, border: '1px solid #ebebeb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6a6a6a' }}>
            <LogOut size={14} />
          </a>
        </div>
      </aside>

      {/* Panel overlay */}
      {panel && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex' }} onClick={() => setPanel(null)}>
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.15)' }} />
          <div onClick={e => e.stopPropagation()} style={{
            position: 'absolute', left: 260, top: 0, bottom: 0, width: 320,
            background: '#fff', borderRight: '1px solid #ebebeb', boxShadow: '0 12px 40px rgba(0,0,0,.1)',
            display: 'flex', flexDirection: 'column', zIndex: 201,
          }}>
            <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid #ebebeb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {{ events: <Calendar size={14} />, news: <Newspaper size={14} />, parking: <Car size={14} /> }[panel]}
                  {{ events: 'Upcoming Events', news: 'Latest News', parking: 'Parking' }[panel]}
                </div>
                <div style={{ fontSize: 11, color: '#6a6a6a' }}>{liveData ? `Updated ${liveData.ts}` : 'Loading...'}</div>
              </div>
              <button onClick={() => setPanel(null)} style={{ width: 26, height: 26, borderRadius: 6, background: '#f2f2f2', border: 'none', color: '#6a6a6a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <X size={14} />
              </button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
              {!liveData ? <div style={{ padding: 40, textAlign: 'center', color: '#6a6a6a', fontSize: 13 }}>Loading...</div> :
                panel === 'events' ? (liveData.events || []).map((e, i) => (
                  <a key={i} href={e.url} target="_blank" rel="noreferrer" style={{ display: 'block', padding: '11px 12px', borderRadius: 10, border: '1px solid #ebebeb', marginBottom: 8, background: '#fff', transition: 'all 0.2s' }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 5 }}>{e.name}</div>
                    <div style={{ fontSize: 12, color: '#ff385c', fontWeight: 500, marginBottom: 2 }}>{e.date}</div>
                    <div style={{ fontSize: 11, color: '#6a6a6a' }}>{e.place || 'Northeastern University'}</div>
                  </a>
                )) :
                panel === 'news' ? (liveData.news || []).map((n, i) => (
                  <a key={i} href={n.url} target="_blank" rel="noreferrer" style={{ display: 'block', padding: '10px 0', borderBottom: '1px solid #f2f2f2' }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{n.title}</div>
                    {n.desc && <div style={{ fontSize: 12, color: '#6a6a6a', lineHeight: 1.4 }}>{n.desc}</div>}
                  </a>
                )) :
                (liveData.parking || []).map((p, i) => {
                  const n = parseInt(p.spaces) || 0
                  return (
                    <div key={i} style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid #ebebeb', marginBottom: 8, background: '#fff' }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>{p.name}</div>
                      <div style={{ fontSize: 28, fontWeight: 700, color: !p.spaces ? '#6a6a6a' : n === 0 ? '#dc2626' : n < 60 ? '#d97706' : '#16a34a' }}>{p.spaces ?? '\u2014'}</div>
                      <div style={{ fontSize: 11, color: '#6a6a6a', marginTop: 2 }}>spaces available</div>
                      {p.hours && <div style={{ fontSize: 11, color: '#6a6a6a', borderTop: '1px solid #f2f2f2', paddingTop: 6, marginTop: 6 }}>{p.hours}</div>}
                      <a href={p.url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#ff385c', marginTop: 4, display: 'inline-block' }}>View details &rarr;</a>
                    </div>
                  )
                })
              }
            </div>
          </div>
        </div>
      )}

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <div style={{ padding: '12px 22px', display: 'flex', justifyContent: 'flex-end', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button onClick={newChat} style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#fff', border: '1px solid #ebebeb', borderRadius: 20, padding: '6px 14px', fontSize: 13, fontWeight: 500, color: '#222', boxShadow: '0 1px 3px rgba(0,0,0,.04)' }}>
              <Plus size={13} /> New Chat
            </button>
            <a href="/dashboard" style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#fff', border: '1px solid #ebebeb', borderRadius: 20, padding: '6px 14px', fontSize: 13, fontWeight: 500, color: '#222', boxShadow: '0 1px 3px rgba(0,0,0,.04)' }}>
              <LayoutDashboard size={13} /> Dashboard
            </a>
          </div>
        </div>

        {/* Chat area */}
        <div ref={chatRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0 24px 20px', scrollBehavior: 'smooth', minHeight: 0 }}>
          {showWelcome && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px 24px', maxWidth: 680 }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'linear-gradient(135deg, #ff385c, #e00b41)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24, boxShadow: '0 8px 32px rgba(255,56,92,0.3)' }}>
                <GraduationCap size={30} color="#fff" strokeWidth={2} />
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, textAlign: 'center', letterSpacing: '-0.5px', marginBottom: 8 }}>Good day! <span style={{ color: '#ff385c' }}>How can I<br/>assist you today?</span></div>
              <div style={{ fontSize: 15, color: '#6a6a6a', textAlign: 'center', maxWidth: 420, marginBottom: 28 }}>Your Northeastern University assistant — live events, news, parking & more.</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                {SUGGESTIONS.map(s => (
                  <span key={s.text} onClick={() => send(s.text)} style={{
                    background: '#fff', border: '1px solid #ebebeb', padding: '8px 16px', borderRadius: 20,
                    fontSize: 13, fontWeight: 500, cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,.04)',
                    transition: 'all 0.15s', display: 'inline-flex', alignItems: 'center', gap: 6,
                  }}>
                    <s.icon size={14} color="#ff385c" /> {s.text}
                  </span>
                ))}
              </div>
            </div>
          )}

          {msgs.map((m, i) => (
            <div key={i} style={{ width: '100%', maxWidth: 680 }}>
              <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start', padding: '5px 0', flexDirection: m.role === 'user' ? 'row-reverse' : 'row' }}>
                <div style={{
                  width: 30, height: 30, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: m.role === 'user' ? 10 : 14, fontWeight: 700, flexShrink: 0, marginTop: 2,
                  ...(m.role === 'user' ? { background: 'linear-gradient(135deg, #ff385c, #e00b41)', color: '#fff' } : { background: '#222', color: '#fff' }),
                }}>{m.role === 'user' ? (user.name?.[0]?.toUpperCase() || 'U') : <GraduationCap size={14} />}</div>
                <div style={{ maxWidth: 'calc(100% - 42px)' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#6a6a6a', marginBottom: 5, textAlign: m.role === 'user' ? 'right' : 'left' }}>{m.role === 'user' ? 'You' : 'NEU Assistant'}</div>
                  {m.role === 'user' ? (
                    <div style={{ display: 'inline-block', padding: '11px 16px', borderRadius: '16px 16px 4px 16px', fontSize: 14, lineHeight: 1.65, background: '#ff385c', color: '#fff', boxShadow: '0 4px 14px rgba(255,56,92,0.15)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.content}</div>
                  ) : (
                    <div className="bot-bubble" style={{ display: 'inline-block', padding: '11px 16px', borderRadius: '16px 16px 16px 4px', fontSize: 14, lineHeight: 1.65, background: '#fff', color: '#222', border: '1px solid #ebebeb', boxShadow: '0 1px 3px rgba(0,0,0,.04)', maxWidth: '100%', wordBreak: 'break-word' }}
                      dangerouslySetInnerHTML={{ __html: marked.parse(m.content, { breaks: true, gfm: true }) }} />
                  )}
                </div>
              </div>
            </div>
          ))}

          {sending && (
            <div style={{ width: '100%', maxWidth: 680 }}>
              <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start', padding: '5px 0' }}>
                <div style={{ width: 30, height: 30, borderRadius: '50%', background: '#222', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><GraduationCap size={14} /></div>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#6a6a6a', marginBottom: 5 }}>NEU Assistant</div>
                  <div style={{ display: 'inline-flex', gap: 5, alignItems: 'center', padding: '14px 18px', borderRadius: '16px 16px 16px 4px', background: '#fff', border: '1px solid #ebebeb' }}>
                    {[0, 0.18, 0.36].map((d, i) => <div key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: '#d1d5db', animation: `bounce 1.3s infinite ${d}s` }} />)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div style={{ padding: '10px 24px 20px', display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{
            width: '100%', maxWidth: 680, background: '#fff', border: '1px solid #ebebeb',
            borderRadius: 16, boxShadow: 'rgba(0,0,0,0.02) 0px 0px 0px 1px, rgba(0,0,0,0.04) 0px 2px 6px, rgba(0,0,0,0.1) 0px 4px 8px',
            overflow: 'hidden',
          }}>
            <textarea ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder="Ask anything about Northeastern..." rows={1}
              style={{ width: '100%', border: 'none', outline: 'none', padding: '15px 18px 10px', fontSize: 14, lineHeight: 1.5, resize: 'none', minHeight: 52, maxHeight: 200, background: 'transparent', color: '#222' }}
              onInput={e => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px' }} />
            <div style={{ display: 'flex', alignItems: 'center', padding: '6px 10px 10px', gap: 6 }}>
              {['Events', 'Parking', 'News'].map(t => (
                <button key={t} onClick={() => send(`What ${t.toLowerCase() === 'events' ? 'events are happening today' : t.toLowerCase() === 'parking' ? 'parking spaces are available right now' : 'is the latest news from Northeastern'}?`)}
                  style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 11px', borderRadius: 20, background: '#f7f7f7', border: '1px solid #ebebeb', fontSize: 12, fontWeight: 500, color: '#6a6a6a' }}>{t}</button>
              ))}
              <button onClick={() => send()} disabled={sending || !input.trim()}
                style={{
                  marginLeft: 'auto', width: 34, height: 34, background: sending || !input.trim() ? '#ebebeb' : '#ff385c',
                  borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: sending || !input.trim() ? 'none' : '0 2px 8px rgba(255,56,92,0.25)', transition: 'all 0.15s', border: 'none',
                }}>
                <Send size={15} color="#fff" />
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
