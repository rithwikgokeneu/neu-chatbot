import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Bot, Calendar, Car, Newspaper, GraduationCap, MessageSquare, LogIn, ArrowRight, Zap, MapPin, Lock, ChevronDown, Database, Radio, Clock, Cpu } from 'lucide-react'

const PHRASES = [
  'events happening today.',
  'parking availability.',
  'co-op opportunities.',
  'financial aid options.',
  'campus news.',
  'admissions requirements.',
]

const FEATURES = [
  { Icon: Bot, title: 'Agentic AI Reasoning', desc: 'Multi-step decision making that combines data sources, detects conflicts, and gives context-aware recommendations.', bg: 'rgba(255,56,92,0.08)', color: '#ff385c' },
  { Icon: Calendar, title: 'Live Events Feed', desc: 'Real-time campus events, lectures, and workshops pulled directly from events.northeastern.edu.', bg: 'rgba(66,139,255,0.08)', color: '#428bff' },
  { Icon: Car, title: 'Live Parking Data', desc: 'Check available spaces at all NEU garages in real time. Never waste time circling.', bg: 'rgba(0,184,148,0.08)', color: '#00b894' },
  { Icon: Newspaper, title: 'Campus News', desc: "Stay current with the latest research breakthroughs and stories from Northeastern's newsroom.", bg: 'rgba(108,92,231,0.08)', color: '#6c5ce7' },
  { Icon: GraduationCap, title: 'Academic Advisor', desc: 'Ask about co-op programs, financial aid, admissions, and academic policies from a 12K+ page knowledge base.', bg: 'rgba(253,203,110,0.1)', color: '#f59e0b' },
  { Icon: MessageSquare, title: 'Persistent History', desc: 'All conversations are saved securely to your account. Pick up right where you left off.', bg: 'rgba(255,56,92,0.06)', color: '#ff385c' },
]

const STEPS = [
  { num: '1', title: 'Sign In', desc: 'Use Google, Microsoft, or GitHub for instant, secure access.', Icon: LogIn },
  { num: '2', title: 'Ask Anything', desc: 'Type your question naturally. The AI understands context and intent.', Icon: MessageSquare },
  { num: '3', title: 'Get Smart Answers', desc: 'Receive personalized, real-time recommendations powered by live data.', Icon: Zap },
]

const STATS = [
  { value: '12,800+', label: 'Knowledge Chunks', Icon: Database },
  { value: '5', label: 'Live Data Sources', Icon: Radio },
  { value: '24/7', label: 'Always Available', Icon: Clock },
  { value: '70B+', label: 'Parameter AI Model', Icon: Cpu },
]

const BRANDS = [
  { Icon: MapPin, t: 'Boston, MA' }, { Icon: GraduationCap, t: 'Northeastern University' },
  { Icon: Bot, t: 'Llama 3.3 70B' }, { Icon: Zap, t: 'Powered by Groq' },
  { Icon: Calendar, t: 'Live Events' }, { Icon: Car, t: 'Real-time Parking' },
  { Icon: Newspaper, t: 'Campus News' }, { Icon: Lock, t: 'Google OAuth' },
]

export default function Landing() {
  const [typed, setTyped] = useState('')
  const [scrolled, setScrolled] = useState(false)
  const phraseIdx = useRef(0)
  const charIdx = useRef(0)
  const deleting = useRef(false)

  useEffect(() => {
    let timer
    const tick = () => {
      const phrase = PHRASES[phraseIdx.current]
      if (!deleting.current) {
        charIdx.current++
        setTyped(phrase.slice(0, charIdx.current))
        if (charIdx.current === phrase.length) { deleting.current = true; timer = setTimeout(tick, 2000); return }
      } else {
        charIdx.current--
        setTyped(phrase.slice(0, charIdx.current))
        if (charIdx.current === 0) { deleting.current = false; phraseIdx.current = (phraseIdx.current + 1) % PHRASES.length; timer = setTimeout(tick, 350); return }
      }
      timer = setTimeout(tick, deleting.current ? 40 : 70)
    }
    timer = setTimeout(tick, 800)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', fn)
    return () => window.removeEventListener('scroll', fn)
  }, [])

  useEffect(() => {
    const els = document.querySelectorAll('.rv')
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.style.opacity = 1; e.target.style.transform = 'translateY(0)'; obs.unobserve(e.target) } })
    }, { threshold: 0.1 })
    els.forEach(el => obs.observe(el))
    return () => obs.disconnect()
  }, [])

  const rv = { opacity: 0, transform: 'translateY(28px)', transition: 'opacity 0.7s ease, transform 0.7s ease' }

  return (
    <div style={{ background: '#fff', color: '#222', minHeight: '100vh' }}>
      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes marquee { to { transform: translateX(-50%); } }
      `}</style>

      {/* Nav */}
      <nav style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        padding: '14px 48px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: scrolled ? 'rgba(255,255,255,0.97)' : 'rgba(255,255,255,0.8)',
        backdropFilter: 'blur(20px)', borderBottom: '1px solid #ebebeb', transition: 'background 0.3s',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg, #ff385c, #e00b41)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(255,56,92,0.25)' }}>
            <GraduationCap size={18} color="#fff" strokeWidth={2.5} />
          </div>
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-0.4px' }}>NEU Assistant</span>
        </div>
        <div style={{ display: 'flex', gap: 32 }}>
          {['Features', 'Live Data', 'How it Works'].map(t => (
            <a key={t} href={`#${t.toLowerCase().replace(/ /g, '-')}`} style={{ fontSize: 14, fontWeight: 500, color: '#6a6a6a' }}>{t}</a>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link to="/login" style={{ padding: '8px 20px', borderRadius: 8, border: '1px solid #ddd', fontSize: 14, fontWeight: 500, color: '#222', display: 'flex', alignItems: 'center', gap: 6 }}>
            <LogIn size={14} /> Sign In
          </Link>
          <Link to="/login" style={{ padding: '8px 22px', borderRadius: 8, background: '#222', fontSize: 14, fontWeight: 600, color: '#fff', display: 'flex', alignItems: 'center', gap: 6 }}>
            Get Started <ArrowRight size={14} />
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 80, textAlign: 'center', background: 'radial-gradient(ellipse at 50% 0%, rgba(255,56,92,0.06) 0%, transparent 60%)' }}>
        <div style={{ maxWidth: 720, padding: '0 28px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(255,56,92,0.06)', border: '1px solid rgba(255,56,92,0.15)', borderRadius: 100, padding: '6px 18px', fontSize: 13, fontWeight: 600, color: '#ff385c', marginBottom: 28 }}>
            <Zap size={12} fill="#ff385c" /> AI-Powered Campus Intelligence
          </div>
          <h1 style={{ fontSize: 'clamp(40px, 6vw, 72px)', fontWeight: 800, letterSpacing: '-2.5px', lineHeight: 1.05, marginBottom: 22 }}>
            Your Intelligent<br/><span style={{ color: '#ff385c' }}>Campus Companion</span>
          </h1>
          <p style={{ fontSize: 18, color: '#6a6a6a', lineHeight: 1.7, maxWidth: 520, margin: '0 auto 40px' }}>
            Ask anything about Northeastern — get instant answers on<br/>
            <span style={{ color: '#222', fontWeight: 500 }}>{typed}</span>
            <span style={{ display: 'inline-block', width: 2, height: 20, background: '#ff385c', marginLeft: 2, verticalAlign: 'middle', animation: 'blink .9s infinite' }} />
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link to="/login" style={{ padding: '15px 32px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 16, fontWeight: 600, boxShadow: '0 8px 24px rgba(255,56,92,0.25)', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              Get Started Free <ArrowRight size={16} />
            </Link>
            <a href="#features" style={{ padding: '15px 32px', borderRadius: 8, border: '1px solid #ddd', color: '#222', fontSize: 16, fontWeight: 500, background: '#fff', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              Explore Features <ChevronDown size={16} />
            </a>
          </div>
        </div>
      </section>

      {/* Brand Bar */}
      <div style={{ borderTop: '1px solid #ebebeb', borderBottom: '1px solid #ebebeb', padding: '16px 0', overflow: 'hidden' }}>
        <div style={{ display: 'flex', gap: 48, alignItems: 'center', animation: 'marquee 25s linear infinite', width: 'max-content' }}>
          {[...Array(2)].flatMap((_, j) => BRANDS.map((b, i) => (
            <span key={`${j}-${i}`} style={{ fontSize: 13, fontWeight: 500, color: '#6a6a6a', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 6 }}>
              <b.Icon size={14} /> {b.t}
            </span>
          )))}
        </div>
      </div>

      {/* Features */}
      <section id="features" style={{ maxWidth: 1120, margin: '0 auto', padding: '100px 48px' }}>
        <div className="rv" style={rv}>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: '#ff385c', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Zap size={12} /> Features
          </div>
          <h2 style={{ fontSize: 'clamp(28px, 4vw, 42px)', fontWeight: 700, letterSpacing: '-1px', marginBottom: 14 }}>Everything you need,<br/>right on campus</h2>
          <p style={{ fontSize: 16, color: '#6a6a6a', lineHeight: 1.7, maxWidth: 460, marginBottom: 56 }}>From live parking to personalized event picks — all in one intelligent assistant.</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
          {FEATURES.map((f, i) => (
            <div key={i} className="rv" style={{ ...rv, transitionDelay: `${i * 0.08}s`, background: '#fff', border: '1px solid #ebebeb', borderRadius: 20, padding: '32px 28px', transition: 'all 0.3s, opacity 0.7s ease, transform 0.7s ease', cursor: 'default' }}
              onMouseEnter={e => { e.currentTarget.style.boxShadow = 'rgba(0,0,0,0.08) 0px 4px 12px'; e.currentTarget.style.transform = 'translateY(-4px)' }}
              onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)' }}>
              <div style={{ width: 52, height: 52, borderRadius: 14, background: f.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
                <f.Icon size={24} color={f.color} strokeWidth={1.8} />
              </div>
              <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 8 }}>{f.title}</div>
              <div style={{ fontSize: 14, color: '#6a6a6a', lineHeight: 1.65 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Live Preview */}
      <section id="live-data" style={{ background: '#f7f7f7' }}>
        <div style={{ maxWidth: 1120, margin: '0 auto', padding: '100px 48px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 48, alignItems: 'center' }}>
            <div className="rv" style={rv}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 100, padding: '5px 14px', fontSize: 12, fontWeight: 600, color: '#16a34a', marginBottom: 20 }}>
                <Radio size={10} /> Refreshed every 2 minutes
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: '#ff385c', marginBottom: 14 }}>Live Data</div>
              <h2 style={{ fontSize: 36, fontWeight: 700, letterSpacing: '-1px', marginBottom: 14 }}>Real-time campus data</h2>
              <p style={{ fontSize: 16, color: '#6a6a6a', lineHeight: 1.7, marginBottom: 28 }}>No more guessing if there's parking or what's on today.</p>
              <Link to="/login" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '13px 28px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 15, fontWeight: 600 }}>
                Try it now <ArrowRight size={16} />
              </Link>
            </div>
            <div className="rv" style={{ ...rv, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ background: '#fff', border: '1px solid #ebebeb', borderRadius: 20, padding: '20px 24px', boxShadow: 'rgba(0,0,0,0.02) 0px 0px 0px 1px, rgba(0,0,0,0.04) 0px 2px 6px, rgba(0,0,0,0.1) 0px 4px 8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#6a6a6a', textTransform: 'uppercase', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Calendar size={14} /> Upcoming Events
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#16a34a', background: 'rgba(34,197,94,0.08)', borderRadius: 100, padding: '2px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Radio size={8} /> LIVE
                  </span>
                </div>
                {[{ n: 'AI in Healthcare Symposium', m: 'Today \u00B7 3:00 PM \u00B7 Snell Library' }, { n: 'Entrepreneurship Networking Night', m: 'Tomorrow \u00B7 6:00 PM \u00B7 Curry Center' }, { n: 'CS Research Showcase', m: 'Fri \u00B7 2:00 PM \u00B7 ISEC Building' }].map((e, i) => (
                  <div key={i} style={{ padding: '8px 0', borderBottom: i < 2 ? '1px solid #f2f2f2' : 'none' }}>
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>{e.n}</div>
                    <div style={{ fontSize: 12, color: '#ff385c', fontWeight: 500 }}>{e.m}</div>
                  </div>
                ))}
              </div>
              <div style={{ background: '#fff', border: '1px solid #ebebeb', borderRadius: 20, padding: '20px 24px', boxShadow: 'rgba(0,0,0,0.02) 0px 0px 0px 1px, rgba(0,0,0,0.04) 0px 2px 6px, rgba(0,0,0,0.1) 0px 4px 8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#6a6a6a', textTransform: 'uppercase', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Car size={14} /> Parking Availability
                  </span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#16a34a', background: 'rgba(34,197,94,0.08)', borderRadius: 100, padding: '2px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Radio size={8} /> LIVE
                  </span>
                </div>
                {[{ n: 'West Village Garage', v: 342, ok: true }, { n: 'Renaissance Park', v: 201, ok: true }, { n: 'Gainsborough Garage', v: 47, ok: false }, { n: 'Columbus Garage', v: 189, ok: true }].map((p, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: i < 3 ? '1px solid #f2f2f2' : 'none' }}>
                    <span style={{ fontSize: 13, color: '#6a6a6a' }}>{p.n}</span>
                    <span style={{ fontSize: 20, fontWeight: 700, color: p.ok ? '#16a34a' : '#d97706' }}>{p.v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section id="how-it-works" style={{ maxWidth: 1120, margin: '0 auto', padding: '100px 48px', textAlign: 'center' }}>
        <div className="rv" style={rv}>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: '#ff385c', marginBottom: 14 }}>How it Works</div>
          <h2 style={{ fontSize: 'clamp(28px, 4vw, 42px)', fontWeight: 700, letterSpacing: '-1px', marginBottom: 56 }}>Simple. Smart. Instant.</h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
          {STEPS.map((s, i) => (
            <div key={i} className="rv" style={{ ...rv, textAlign: 'center', padding: '0 20px' }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#ff385c', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', boxShadow: '0 8px 24px rgba(255,56,92,0.25)' }}>
                <s.Icon size={24} strokeWidth={2.5} />
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>{s.title}</div>
              <div style={{ fontSize: 14, color: '#6a6a6a', lineHeight: 1.65 }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Stats */}
      <section style={{ borderTop: '1px solid #ebebeb', borderBottom: '1px solid #ebebeb' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', maxWidth: 1120, margin: '0 auto' }}>
          {STATS.map((s, i) => (
            <div key={i} className="rv" style={{ ...rv, textAlign: 'center', padding: '56px 20px', borderRight: i < 3 ? '1px solid #ebebeb' : 'none' }}>
              <s.Icon size={24} color="#ff385c" style={{ margin: '0 auto 12px', display: 'block' }} />
              <div style={{ fontSize: 44, fontWeight: 800, letterSpacing: '-1.5px', lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 14, color: '#6a6a6a', marginTop: 8, fontWeight: 500 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '100px 48px', textAlign: 'center' }}>
        <div className="rv" style={{ ...rv, background: '#f7f7f7', border: '1px solid #ebebeb', borderRadius: 32, padding: '80px 48px' }}>
          <h2 style={{ fontSize: 'clamp(28px, 4vw, 46px)', fontWeight: 800, letterSpacing: '-1.5px', marginBottom: 18 }}>Ready to transform your<br/>campus experience?</h2>
          <p style={{ fontSize: 18, color: '#6a6a6a', marginBottom: 40 }}>Join Northeastern students who ask smarter questions every day.</p>
          <Link to="/login" style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '17px 40px', borderRadius: 8, background: '#ff385c', color: '#fff', fontSize: 16, fontWeight: 700, boxShadow: '0 8px 28px rgba(255,56,92,0.25)' }}>
            Start Now — It's Free <ArrowRight size={18} />
          </Link>
          <p style={{ marginTop: 16, fontSize: 13, color: '#6a6a6a' }}>Sign in with Google &middot; No password needed</p>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid #ebebeb', padding: '32px 48px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'linear-gradient(135deg, #ff385c, #e00b41)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <GraduationCap size={14} color="#fff" />
          </div>
          <span style={{ fontSize: 14, fontWeight: 700 }}>NEU Assistant</span>
        </div>
        <div style={{ fontSize: 13, color: '#6a6a6a' }}>&copy; 2025 NEU Assistant &middot; Built for Northeastern University</div>
        <div style={{ display: 'flex', gap: 24 }}>
          <Link to="/login" style={{ fontSize: 13, color: '#6a6a6a' }}>Sign In</Link>
          <a href="#features" style={{ fontSize: 13, color: '#6a6a6a' }}>Features</a>
          <a href="https://northeastern.edu" target="_blank" rel="noreferrer" style={{ fontSize: 13, color: '#6a6a6a' }}>northeastern.edu</a>
        </div>
      </footer>
    </div>
  )
}
