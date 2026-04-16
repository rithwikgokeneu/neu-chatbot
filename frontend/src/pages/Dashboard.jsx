import { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { GraduationCap, Clock, Calendar, BookOpen, Bell, Settings, MessageSquare, RefreshCw, ExternalLink, Phone, Smartphone, Trash2, LogOut, FileText, BarChart3, ClipboardList, Megaphone, MessagesSquare, Pin, Zap, AlertTriangle, CheckCircle2, Radio } from 'lucide-react'

const URGENCY = { overdue: { color: '#dc2626', bg: 'rgba(220,38,38,0.06)', label: 'OVERDUE' }, critical: { color: '#ef4444', bg: 'rgba(239,68,68,0.06)', label: 'DUE TODAY' }, high: { color: '#f97316', bg: 'rgba(249,115,22,0.06)', label: 'DUE SOON' }, medium: { color: '#eab308', bg: 'rgba(234,179,8,0.06)', label: 'THIS WEEK' }, low: { color: '#22c55e', bg: 'rgba(34,197,94,0.06)', label: 'UPCOMING' }, completed: { color: '#6a6a6a', bg: 'rgba(106,106,106,0.06)', label: 'COMPLETED' }, announcement: { color: '#6366f1', bg: 'rgba(99,102,241,0.06)', label: 'ANNOUNCEMENT' } }
const TYPE_ICONS = { assignment: FileText, quiz: BarChart3, exam: ClipboardList, announcement: Megaphone, discussion: MessagesSquare }

function Toast({ msg, type }) {
  if (!msg) return null
  return <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 999, background: '#fff', border: `1px solid ${type === 'ok' ? 'rgba(34,197,94,0.3)' : type === 'err' ? 'rgba(220,38,38,0.3)' : '#ebebeb'}`, borderRadius: 12, padding: '12px 18px', fontSize: 14, fontWeight: 500, boxShadow: 'rgba(0,0,0,0.02) 0px 0px 0px 1px, rgba(0,0,0,0.04) 0px 2px 6px, rgba(0,0,0,0.1) 0px 4px 8px' }}>{msg}</div>
}

function TaskCard({ item, onWA, onReminder }) {
  const u = URGENCY[item.urgency] || URGENCY.low
  return (
    <div style={{ background: u.bg, border: `1px solid ${u.color}22`, borderRadius: 14, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8, borderLeft: `3px solid ${u.color}` }}>
      <div style={{ width: 38, height: 38, borderRadius: 10, background: `${u.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        {(() => { const I = TYPE_ICONS[item.type] || Pin; return <I size={18} color={u.color} /> })()}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: 4 }}>{item.title}</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: '#6a6a6a' }}>
          <span style={{ fontWeight: 500 }}>{item.course}</span>
          <span style={{ fontWeight: 600, color: u.color }}>{item.due_fmt}</span>
          {item.points != null && <span>{item.points} pts</span>}
        </div>
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 20, background: u.bg, color: u.color, border: `1px solid ${u.color}30`, textTransform: 'uppercase', letterSpacing: 0.5 }}>{u.label}</span>
      <div style={{ display: 'flex', gap: 5 }}>
        {item.url && <a href={item.url} target="_blank" rel="noreferrer" style={{ width: 30, height: 30, borderRadius: 7, border: '1px solid #ebebeb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6a6a6a', background: '#fff' }}><ExternalLink size={14} /></a>}
        <button onClick={() => onWA?.(item)} style={{ width: 30, height: 30, borderRadius: 7, border: '1px solid #ebebeb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6a6a6a', background: '#fff' }}><Smartphone size={14} /></button>
        <button onClick={() => onReminder?.(item)} style={{ width: 30, height: 30, borderRadius: 7, border: '1px solid #ebebeb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6a6a6a', background: '#fff' }}><Bell size={14} /></button>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const nav = useNavigate()
  const [user, setUser] = useState(null)
  const [view, setView] = useState('today')
  const [canvas, setCanvas] = useState(false)
  const [items, setItems] = useState([])
  const [reminders, setReminders] = useState([])
  const [waConn, setWaConn] = useState(false)
  const [modal, setModal] = useState(false)
  const [toast, setToast] = useState({ msg: '', type: '' })

  const showToast = (msg, type = '') => { setToast({ msg, type }); setTimeout(() => setToast({ msg: '', type: '' }), 3000) }

  useEffect(() => { fetch('/api/me', { credentials: 'include' }).then(r => { if (!r.ok) throw 0; return r.json() }).then(setUser).catch(() => nav('/login')) }, [nav])

  const loadData = useCallback(async () => {
    try { const r = await fetch('/api/canvas/status', { credentials: 'include' }); const d = await r.json(); setCanvas(d.connected) } catch {}
    try { const r = await fetch('/api/whatsapp/status', { credentials: 'include' }); const d = await r.json(); setWaConn(d.configured && d.enabled) } catch {}
  }, [])

  const loadItems = useCallback(async () => {
    try { const r = await fetch('/api/canvas/data', { credentials: 'include' }); if (r.ok) { const d = await r.json(); setItems(d.items || []) } } catch {}
  }, [])

  const loadReminders = useCallback(async () => {
    try { const r = await fetch('/api/reminders', { credentials: 'include' }); if (r.ok) setReminders(await r.json()) } catch {}
  }, [])

  useEffect(() => { loadData().then(loadItems).then(loadReminders) }, [loadData, loadItems, loadReminders])

  const refresh = async () => { showToast('Refreshing...'); if (canvas) { await fetch('/api/canvas/refresh', { method: 'POST', credentials: 'include' }); await loadItems() }; await loadReminders(); showToast('\u2713 Refreshed', 'ok') }

  const connectCanvas = async (url, token) => {
    const r = await fetch('/api/canvas/connect', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ canvas_url: url, canvas_token: token }) })
    const d = await r.json()
    if (d.ok) { setCanvas(true); setModal(false); showToast(`\u2713 Connected as ${d.name}`, 'ok'); await loadItems() } else showToast(d.error || 'Failed', 'err')
  }

  const saveReminder = async (item) => {
    await fetch('/api/reminders', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item_id: item.id, item_type: item.type, title: item.title, course: item.course, due_at: item.due_at, urgency: item.urgency }) })
    showToast('\uD83D\uDD14 Reminder saved', 'ok'); await loadReminders()
  }

  const pending = items.filter(i => i.status === 'pending')
  const overdue = items.filter(i => i.status === 'overdue')
  const completed = items.filter(i => i.status === 'completed')
  const stats = { overdue: overdue.length, critical: pending.filter(i => i.urgency === 'critical').length, high: pending.filter(i => i.urgency === 'high').length, total: pending.length }

  const VIEWS = [
    { id: 'today', label: "Today's Focus", Icon: Clock },
    { id: 'week', label: 'This Week', Icon: Calendar },
    { id: 'courses', label: 'By Course', Icon: BookOpen },
    { id: 'reminders', label: 'Reminders', Icon: Bell },
    { id: 'setup', label: 'Integrations', Icon: Settings },
  ]

  if (!user) return null

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#f7f7f7', fontFamily: "'Inter', -apple-system, sans-serif" }}>
      {/* Sidebar */}
      <aside style={{ width: 250, background: '#fff', borderRight: '1px solid #ebebeb', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid #ebebeb' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
            <div style={{ width: 32, height: 32, borderRadius: 9, background: 'linear-gradient(135deg, #ff385c, #e00b41)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><GraduationCap size={16} color="#fff" strokeWidth={2.5} /></div>
            <span style={{ fontSize: 15, fontWeight: 700 }}>NEU Assistant</span>
          </Link>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.4, textTransform: 'uppercase', color: '#6a6a6a' }}>Academic Dashboard</div>
        </div>
        <nav style={{ padding: '10px 10px', flex: 1 }}>
          {VIEWS.map(v => (
            <div key={v.id} onClick={() => setView(v.id)} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 9,
              fontSize: 13, fontWeight: 500, cursor: 'pointer', marginBottom: 2,
              color: view === v.id ? '#ff385c' : '#6a6a6a',
              background: view === v.id ? 'rgba(255,56,92,0.06)' : 'transparent',
              border: view === v.id ? '1px solid rgba(255,56,92,0.15)' : '1px solid transparent',
            }}>
              <v.Icon size={16} strokeWidth={view === v.id ? 2 : 1.5} /> {v.label}
              {(v.id === 'today' && (overdue.length + stats.critical) > 0) && <span style={{ marginLeft: 'auto', minWidth: 20, height: 20, background: '#ff385c', borderRadius: 10, fontSize: 11, fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 5px' }}>{overdue.length + stats.critical}</span>}
            </div>
          ))}
          <div style={{ height: 1, background: '#ebebeb', margin: '10px 12px' }} />
          <Link to="/app" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 9, fontSize: 13, fontWeight: 500, color: '#6a6a6a' }}>
            <MessageSquare size={16} /> Back to Chat
          </Link>
        </nav>
        <div style={{ padding: '12px 14px', borderTop: '1px solid #ebebeb', display: 'flex', alignItems: 'center', gap: 9 }}>
          {user.avatar ? <img src={user.avatar} alt="" style={{ width: 30, height: 30, borderRadius: '50%', objectFit: 'cover' }} /> :
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg, #ff385c, #e00b41)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#fff' }}>{user.name?.[0]?.toUpperCase() || 'U'}</div>}
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.name}</div>
            <div style={{ fontSize: 11, color: '#6a6a6a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.email}</div>
          </div>
          <a href="/logout" style={{ width: 26, height: 26, borderRadius: 6, border: '1px solid #ebebeb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6a6a6a' }}><LogOut size={13} /></a>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <div style={{ padding: '14px 28px', borderBottom: '1px solid #ebebeb', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0, background: '#fff' }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.3px' }}>{VIEWS.find(v => v.id === view)?.label}</h2>
            <p style={{ fontSize: 13, color: '#6a6a6a', marginTop: 2 }}>
              {view === 'today' ? 'Your most urgent academic items' : view === 'week' ? 'All items due in the next 7 days' : view === 'courses' ? 'Grouped by course' : view === 'reminders' ? 'Your saved reminders' : 'Connect Canvas & WhatsApp'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600, border: '1px solid', ...(canvas ? { color: '#22c55e', borderColor: 'rgba(34,197,94,0.25)', background: 'rgba(34,197,94,0.06)' } : { color: '#6a6a6a', borderColor: '#ebebeb' }) }}>
              <Radio size={10} />
              {canvas ? 'Canvas Live' : 'Canvas not connected'}
            </div>
            <button onClick={refresh} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '8px 16px', borderRadius: 8, border: '1px solid #ebebeb', background: '#fff', fontSize: 13, fontWeight: 600, color: '#222' }}>
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '28px 28px 40px' }}>
          {/* Today view */}
          {view === 'today' && (<>
            {!canvas && (
              <div style={{ background: '#f7f7f7', border: '1px solid #ebebeb', borderRadius: 20, padding: '36px 40px', textAlign: 'center', marginBottom: 28 }}>
                <div style={{ marginBottom: 14 }}><GraduationCap size={42} color="#ff385c" /></div>
                <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 10 }}>Connect your Canvas LMS</h3>
                <p style={{ color: '#6a6a6a', fontSize: 14, marginBottom: 24, maxWidth: 420, margin: '0 auto 24px', lineHeight: 1.6 }}>Sync assignments, quizzes, and announcements for real-time deadline tracking.</p>
                <button onClick={() => setModal(true)} style={{ padding: '10px 24px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 14, fontWeight: 600, border: 'none', boxShadow: '0 4px 16px rgba(255,56,92,0.2)' }}>Connect Canvas Now</button>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 28 }}>
              {[{ l: 'Overdue', v: stats.overdue, c: '#dc2626' }, { l: 'Due Today', v: stats.critical, c: '#f97316' }, { l: 'Due Soon', v: stats.high, c: '#eab308' }, { l: 'Total Upcoming', v: stats.total, c: '#22c55e' }].map((s, i) => (
                <div key={i} style={{ background: '#fff', border: '1px solid #ebebeb', borderRadius: 14, padding: '18px 20px' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#6a6a6a', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>{s.l}</div>
                  <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: '-1px', color: s.c }}>{s.v}</div>
                </div>
              ))}
            </div>
            {/* Overdue — past due and NOT submitted */}
            {overdue.length > 0 && (
              <><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}><h3 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><AlertTriangle size={16} color="#dc2626" /> Overdue ({overdue.length})</h3></div>
              {overdue.map(i => <TaskCard key={i.id} item={i} onReminder={saveReminder} />)}</>
            )}
            {/* Pending — due in the future */}
            {pending.filter(i => ['critical', 'high'].includes(i.urgency)).length > 0 && (
              <><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14, marginTop: 24 }}><h3 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><Clock size={16} color="#f97316" /> Due Soon</h3></div>
              {pending.filter(i => ['critical', 'high'].includes(i.urgency)).map(i => <TaskCard key={i.id} item={i} onReminder={saveReminder} />)}</>
            )}
            {pending.filter(i => ['medium', 'low'].includes(i.urgency)).length > 0 && (
              <><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14, marginTop: 24 }}><h3 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><Calendar size={16} color="#22c55e" /> Upcoming</h3></div>
              {pending.filter(i => ['medium', 'low'].includes(i.urgency)).map(i => <TaskCard key={i.id} item={i} onReminder={saveReminder} />)}</>
            )}
            {/* Completed — recently done */}
            {completed.length > 0 && (
              <><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14, marginTop: 24 }}><h3 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle2 size={16} color="#22c55e" /> Completed ({completed.length})</h3></div>
              {completed.map(i => <TaskCard key={i.id} item={{...i, urgency: 'low'}} />)}</>
            )}
            {canvas && pending.length === 0 && overdue.length === 0 && <div style={{ textAlign: 'center', padding: '48px 20px', color: '#6a6a6a' }}><div style={{ marginBottom: 12 }}><CheckCircle2 size={36} color="#22c55e" /></div><h4 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>All caught up!</h4><p style={{ fontSize: 13 }}>No pending assignments or quizzes.</p></div>}
          </>)}

          {/* Week view */}
          {view === 'week' && (<>
            {!canvas ? <div style={{ textAlign: 'center', padding: 48, color: '#6a6a6a' }}>Connect Canvas to see weekly data.</div> :
              items.filter(i => ['overdue', 'critical', 'high', 'medium'].includes(i.urgency)).length === 0 ? <div style={{ textAlign: 'center', padding: 48 }}><div style={{ marginBottom: 12 }}><CheckCircle2 size={36} color="#22c55e" /></div><h4 style={{ fontSize: 15, fontWeight: 600 }}>Nothing due this week!</h4></div> :
              items.filter(i => ['overdue', 'critical', 'high', 'medium'].includes(i.urgency)).map(i => <TaskCard key={i.id} item={i} onReminder={saveReminder} />)
            }
          </>)}

          {/* Courses view */}
          {view === 'courses' && (<>
            {!canvas ? <div style={{ textAlign: 'center', padding: 48, color: '#6a6a6a' }}>Connect Canvas first.</div> :
              Object.entries(items.reduce((g, i) => { (g[i.course] = g[i.course] || []).push(i); return g }, {})).map(([course, courseItems]) => (
                <div key={course} style={{ marginBottom: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#fff', border: '1px solid #ebebeb', borderRadius: '10px 10px 0 0' }}>
                    <BookOpen size={16} /><h4 style={{ fontSize: 14, fontWeight: 700 }}>{course}</h4>
                    <span style={{ marginLeft: 'auto', fontSize: 12, color: '#6a6a6a' }}>{courseItems.length} items</span>
                  </div>
                  <div style={{ border: '1px solid #ebebeb', borderTop: 'none', borderRadius: '0 0 10px 10px', overflow: 'hidden' }}>
                    {courseItems.map(i => <TaskCard key={i.id} item={i} onReminder={saveReminder} />)}
                  </div>
                </div>
              ))
            }
          </>)}

          {/* Reminders view */}
          {view === 'reminders' && (<>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}><h3 style={{ fontSize: 15, fontWeight: 700 }}>Saved Reminders</h3><span style={{ fontSize: 12, color: '#6a6a6a' }}>{reminders.length} total</span></div>
            {reminders.length === 0 ? <div style={{ textAlign: 'center', padding: 48, color: '#6a6a6a' }}><div style={{ marginBottom: 12 }}><Bell size={36} color="#6a6a6a" /></div><p style={{ fontSize: 13 }}>No reminders yet.</p></div> :
              reminders.map(r => <TaskCard key={r.id} item={r} />)
            }
          </>)}

          {/* Setup view */}
          {view === 'setup' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ background: '#fff', border: '1px solid #ebebeb', borderRadius: 16, overflow: 'hidden' }}>
                <div style={{ padding: '16px 20px', borderBottom: '1px solid #ebebeb', display: 'flex', justifyContent: 'space-between' }}>
                  <h4 style={{ fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><GraduationCap size={16} /> Canvas LMS</h4>
                  <span style={{ fontSize: 12, color: '#6a6a6a' }}>{canvas ? '\u2713 Connected' : 'Not connected'}</span>
                </div>
                <div style={{ padding: '16px 20px' }}>
                  <p style={{ fontSize: 13, color: '#6a6a6a', lineHeight: 1.6, marginBottom: 16 }}>Connect your Canvas account to sync assignments, quizzes, and deadlines.</p>
                  {canvas ?
                    <button onClick={async () => { await fetch('/api/canvas/disconnect', { method: 'POST', credentials: 'include' }); setCanvas(false); setItems([]); showToast('Disconnected') }} style={{ width: '100%', padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(220,38,38,0.25)', background: 'rgba(220,38,38,0.04)', fontSize: 13, fontWeight: 600, color: '#dc2626', cursor: 'pointer' }}>Disconnect Canvas</button> :
                    <button onClick={() => setModal(true)} style={{ width: '100%', padding: '8px 16px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}>Connect Canvas</button>
                  }
                </div>
              </div>
              <div style={{ background: '#fff', border: '1px solid #ebebeb', borderRadius: 16, overflow: 'hidden' }}>
                <div style={{ padding: '16px 20px', borderBottom: '1px solid #ebebeb', display: 'flex', justifyContent: 'space-between' }}>
                  <h4 style={{ fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}><Phone size={16} /> WhatsApp Alerts</h4>
                  <span style={{ fontSize: 12, color: '#6a6a6a' }}>{waConn ? '\u2713 Active' : 'Not configured'}</span>
                </div>
                <div style={{ padding: '16px 20px' }}>
                  <p style={{ fontSize: 13, color: '#6a6a6a', lineHeight: 1.6, marginBottom: 16 }}>Receive deadline reminders directly on WhatsApp via Twilio.</p>
                  <input id="wa-phone" placeholder="+1 617 555 0123" style={{ width: '100%', padding: '10px 14px', border: '1px solid #ebebeb', borderRadius: 8, fontSize: 13, marginBottom: 10, outline: 'none' }} />
                  <button onClick={async () => {
                    const phone = document.getElementById('wa-phone')?.value?.trim()
                    if (!phone) { showToast('Enter phone number', 'err'); return }
                    await fetch('/api/whatsapp/configure', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone, enabled: true }) })
                    setWaConn(true); showToast('\u2713 WhatsApp saved', 'ok')
                  }} style={{ width: '100%', padding: '8px 16px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}>Save Number</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Canvas Modal */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#fff', border: '1px solid #ebebeb', borderRadius: 20, padding: 32, width: 480, maxWidth: '95vw' }}>
            <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>Connect Canvas LMS</h3>
            <p style={{ fontSize: 14, color: '#6a6a6a', marginBottom: 20, lineHeight: 1.6 }}>Enter your Canvas URL and API token.</p>
            <input id="canvas-url" placeholder="https://canvas.northeastern.edu" style={{ width: '100%', padding: '11px 14px', border: '1px solid #ebebeb', borderRadius: 8, fontSize: 14, marginBottom: 12, outline: 'none' }} />
            <input id="canvas-token" type="password" placeholder="Canvas API Token" style={{ width: '100%', padding: '11px 14px', border: '1px solid #ebebeb', borderRadius: 8, fontSize: 14, marginBottom: 12, outline: 'none' }} />
            <p style={{ fontSize: 12, color: '#6a6a6a', marginBottom: 16 }}>Generate at: Canvas &rarr; Account &rarr; Settings &rarr; New Access Token</p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setModal(false)} style={{ flex: 1, padding: '8px 16px', borderRadius: 8, border: '1px solid #ebebeb', background: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => connectCanvas(document.getElementById('canvas-url')?.value?.trim(), document.getElementById('canvas-token')?.value?.trim())} style={{ flex: 1, padding: '8px 16px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}>Connect</button>
            </div>
          </div>
        </div>
      )}

      <Toast msg={toast.msg} type={toast.type} />
    </div>
  )
}
