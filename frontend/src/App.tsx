import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowRight, Check, CircleAlert, Link2, LockKeyhole, MapPin, SlidersHorizontal, Sparkles, X } from 'lucide-react'
import LinkForm from './components/LinkForm'
import PriceForm from './components/PriceForm'
import ResultCard from './components/ResultCard'
import { predict, type Phone, type Result } from './lib/api'

export default function App() {
  const [mode, setMode] = useState<'link' | 'manual'>('link')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const controller = useRef<AbortController | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  useEffect(() => () => controller.current?.abort(), [])
  function clear() { setResult(null); setError('') }
  function cancel() { controller.current?.abort(); controller.current = null; setBusy(false) }
  function changeMode(next: 'link' | 'manual') { cancel(); clear(); setMode(next) }
  async function check(phone?: Phone, price?: number, url?: string) {
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    clear(); setBusy(true)
    try {
      const response = await predict(url ? '/predict-from-url' : '/predict', url ? { url } : { ...phone, actual_price_azn: price }, active.signal)
      if (controller.current !== active) return
      setResult({ prediction: response, phone: response.features || phone!, url })
      if (window.matchMedia('(max-width: 800px)').matches) requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (error) {
      if (!active.signal.aborted && controller.current === active) setError((error as Error).message)
    } finally { if (controller.current === active) { setBusy(false); controller.current = null } }
  }
  return <>
    <a href="#price-checker" className="skip-link">Skip to price checker</a>
    <header className="site-header"><div className="header-inner"><a href="#" className="wordmark" aria-label="Fair Price AZ home"><span className="brand-symbol"><Check size={23} strokeWidth={3} /></span><span>fairprice<span className="brand-az">.az</span></span></a><nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#about">About the estimate</a></nav><span className="market-label"><MapPin size={14} /> Made for Azerbaijan</span></div></header>
    <main className="page-shell">
      <section className="hero"><div className="eyebrow"><span /> A SECOND OPINION ON YOUR NEXT PHONE</div><h1>A fair price.<br className="mobile-break" /> <span>A smarter purchase.</span></h1><p>Know what a phone’s price looks like before you commit.<br className="desktop-break" /> Check a Tap.az listing or enter the details yourself.</p><a href="#price-checker" className="hero-link">Let’s check that price <ArrowDown size={14} /></a><div className="hero-decoration" aria-hidden="true">₼<span /></div></section>
      <section className="checker-grid" id="price-checker" aria-label="Phone price checker">
        <div className="form-card"><div className="method-tabs" role="tablist" aria-label="Choose how to check a phone">
          <button id="link-tab" role="tab" aria-selected={mode === 'link'} aria-controls="link-panel" tabIndex={mode === 'link' ? 0 : -1} onClick={() => changeMode('link')} onKeyDown={e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); changeMode('manual'); document.getElementById('manual-tab')?.focus() } }}><Link2 size={18} /> Paste a link <span className="easy-tag">Quickest</span></button>
          <button id="manual-tab" role="tab" aria-selected={mode === 'manual'} aria-controls="manual-panel" tabIndex={mode === 'manual' ? 0 : -1} onClick={() => changeMode('manual')} onKeyDown={e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); changeMode('link'); document.getElementById('link-tab')?.focus() } }}><SlidersHorizontal size={18} /> Enter details</button>
        </div><div className="form-body">
          <div id="link-panel" role="tabpanel" aria-labelledby="link-tab" hidden={mode !== 'link'}><LinkForm busy={busy} onSubmit={url => check(undefined, undefined, url)} onEdit={clear} onManual={() => changeMode('manual')} /></div>
          <div id="manual-panel" role="tabpanel" aria-labelledby="manual-tab" hidden={mode !== 'manual'}><PriceForm busy={busy} onSubmit={(phone, price) => check(phone, price)} onEdit={clear} /></div>
          {busy && <div className="request-status" role="status"><span>{mode === 'link' ? 'Tap.az can take a moment to respond.' : 'Your estimate is on its way.'}</span><button onClick={cancel}><X size={13} /> Cancel</button></div>}
          {error && <div className="error-panel" role="alert"><CircleAlert size={20} /><div><strong>We couldn’t finish this check</strong><p>{error}</p>{mode === 'link' && <button onClick={() => changeMode('manual')}>Enter details instead <ArrowRight size={14} /></button>}</div></div>}
          <div className="privacy-note"><LockKeyhole size={13} /> No sign-up. Your checks aren’t saved.</div>
        </div></div>
        <div ref={resultRef} className="result-column"><ResultCard result={result} busy={busy} mode={mode} /></div>
      </section>
      <section id="how-it-works" className="how-section"><div className="section-heading"><span className="eyebrow">LESS GUESSWORK, MORE CONFIDENCE</span><h2>From “is this fair?” to a clearer picture.</h2></div><div className="steps">
        <article><span className="step-number">01</span><div><h3>Bring the phone details</h3><p>Paste a listing link or tell us the model, storage, and condition.</p></div></article>
        <article><span className="step-number">02</span><div><h3>Get a local price estimate</h3><p>Our model learns from new and used phone listings in Azerbaijan.</p></div></article>
        <article><span className="step-number">03</span><div><h3>Make a more informed choice</h3><p>Compare the asking price, then inspect the phone before you buy.</p></div></article>
      </div></section>
      <section id="about" className="about-note"><span className="about-icon"><Sparkles size={21} /></span><div><h2>A useful starting point. Not the whole story.</h2><p>Prices are estimates from local asking prices, not completed sales. Rare models, battery health, and repairs can affect accuracy. A good deal still deserves a good inspection.</p></div><span className="beta-label">EARLY ACCESS</span></section>
    </main><footer className="site-footer"><span>fairprice.az <span className="footer-dot">·</span> A little more certainty.</span><span>Phone prices in Azerbaijani manat <strong>₼</strong></span></footer>
  </>
}
