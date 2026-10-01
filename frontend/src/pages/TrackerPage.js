import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import {
  Sparkles, Camera, Loader2, CheckCircle2, Mail, KeyRound, ArrowLeft,
  Calendar, TrendingUp, Lock, Crown, Sun, Moon, Droplet, ShieldCheck,
  ThumbsUp, ThumbsDown, Gift, ChevronRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const TOKEN_KEY = 'cg_auth_token';
const USER_KEY = 'cg_auth_user';

const TASK_ICON = { use: Droplet, care: ShieldCheck, do: ThumbsUp, dont: ThumbsDown };
const TASK_STYLE = {
  use: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  care: 'bg-sky-50 text-sky-700 ring-sky-200',
  do: 'bg-violet-50 text-violet-700 ring-violet-200',
  dont: 'bg-rose-50 text-rose-700 ring-rose-200',
};

function loadRazorpay() {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

/* ------------------------------- LOGIN GATE ------------------------------- */
function LoginGate({ onLogin }) {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const sendOtp = async (e) => {
    e?.preventDefault();
    setError(''); setLoading(true);
    try {
      const r = await axios.post(`${API}/api/auth/send-otp`, { email: email.trim().toLowerCase() });
      setMsg(r.data.message || 'Code sent to your email.');
      setStep('otp');
    } catch (e2) {
      setError(e2.response?.data?.detail || 'Could not send code. Try again.');
    } finally { setLoading(false); }
  };

  const verifyOtp = async (e) => {
    e?.preventDefault();
    setError(''); setLoading(true);
    try {
      const r = await axios.post(`${API}/api/auth/verify-otp`, { email: email.trim().toLowerCase(), otp: otp.trim() });
      try {
        localStorage.setItem(TOKEN_KEY, r.data.token);
        localStorage.setItem(USER_KEY, JSON.stringify(r.data.user));
      } catch {}
      onLogin(r.data.token, r.data.user);
    } catch (e2) {
      setError(e2.response?.data?.detail || 'Invalid code. Try again.');
    } finally { setLoading(false); }
  };

  return (
    <div className="max-w-md mx-auto px-4 mt-8">
      <div className="bg-white rounded-3xl ring-1 ring-stone-200 shadow-sm p-6 sm:p-8">
        <div className="w-14 h-14 rounded-2xl bg-emerald-600 grid place-items-center mx-auto mb-4">
          <Sparkles size={26} className="text-white" />
        </div>
        <h1 className="font-heading text-xl font-black text-stone-900 text-center">Your AI Skin Progress Tracker</h1>
        <p className="text-sm text-stone-500 text-center mt-1 mb-6">Login with your email to access daily tasks, photo progress & AI suggestions.</p>

        {step === 'email' ? (
          <form onSubmit={sendOtp} className="space-y-3">
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-wide">Email address</label>
            <div className="flex items-center gap-2 rounded-xl ring-1 ring-stone-200 px-3 focus-within:ring-2 focus-within:ring-emerald-500">
              <Mail size={16} className="text-stone-400" />
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@email.com" data-testid="tracker-login-email"
                className="flex-1 py-3 text-sm outline-none bg-transparent" />
            </div>
            <button disabled={loading} data-testid="tracker-send-otp"
              className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-60">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />} Send login code
            </button>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="space-y-3">
            {msg && <p className="text-xs text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">{msg}</p>}
            <label className="block text-xs font-bold text-stone-500 uppercase tracking-wide">6-digit code</label>
            <input inputMode="numeric" maxLength={6} required value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
              placeholder="••••••" data-testid="tracker-otp-input"
              className="w-full py-3 text-center text-2xl font-black tracking-[0.4em] rounded-xl ring-1 ring-stone-200 outline-none focus:ring-2 focus:ring-emerald-500" />
            <button disabled={loading} data-testid="tracker-verify-otp"
              className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-60">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Verify & continue
            </button>
            <button type="button" onClick={() => { setStep('email'); setOtp(''); setError(''); }}
              className="w-full text-xs font-semibold text-stone-500 hover:text-stone-800">Change email</button>
          </form>
        )}
        {error && <p className="text-xs text-rose-600 mt-3 text-center">{error}</p>}
      </div>
    </div>
  );
}

/* ------------------------------- MAIN PAGE -------------------------------- */
export default function TrackerPage() {
  const [token, setToken] = useState(() => (typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null));
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // enroll form
  const [skinType, setSkinType] = useState('all');
  const [age, setAge] = useState('25-35');
  const [concerns, setConcerns] = useState([]);
  // daily log form
  const [photo, setPhoto] = useState(null);
  const [notes, setNotes] = useState('');

  const auth = token ? { headers: { Authorization: `Bearer ${token}` } } : {};

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/tracker/status`, { headers: { Authorization: `Bearer ${token}` } });
      setStatus(r.data);
    } catch (e) {
      if (e.response?.status === 401) { localStorage.removeItem(TOKEN_KEY); setToken(null); }
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const toggleConcern = (c) =>
    setConcerns((prev) => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);

  const enroll = async () => {
    setEnrolling(true); setError('');
    try {
      const r = await axios.post(`${API}/api/tracker/enroll`,
        { skin_type: skinType, age, concerns }, auth);
      if (r.data.needs_subscription) { await subscribe(); }
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not enroll. Try again.');
    } finally { setEnrolling(false); }
  };

  const subscribe = async () => {
    setBusy(true); setError('');
    try {
      const ok = await loadRazorpay();
      if (!ok) throw new Error('Could not load payment gateway');
      const r = await axios.post(`${API}/api/tracker/subscribe`, {}, auth);
      const { subscription_id, key_id, amount, customer_email } = r.data;
      const rzp = new window.Razorpay({
        key: key_id,
        subscription_id,
        name: 'Celesta Glow',
        description: `AI Skin Tracker — ₹${amount}/month auto-pay`,
        theme: { color: '#059669' },
        prefill: { email: customer_email },
        handler: async (resp) => {
          try {
            await axios.post(`${API}/api/tracker/subscribe/verify`, {
              razorpay_payment_id: resp.razorpay_payment_id,
              razorpay_subscription_id: resp.razorpay_subscription_id,
              razorpay_signature: resp.razorpay_signature,
            }, auth);
            await load();
          } catch (e) {
            setError('Payment captured but verification failed. Contact support.');
          }
        },
      });
      rzp.open();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Subscription failed.');
    } finally { setBusy(false); }
  };

  const onPhoto = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setPhoto(reader.result);
    reader.readAsDataURL(f);
  };

  const submitLog = async () => {
    if (!photo && !notes.trim()) { setError('Add a photo or a note.'); return; }
    setBusy(true); setError('');
    try {
      await axios.post(`${API}/api/tracker/log`, { photo_base64: photo, notes }, auth);
      setPhoto(null); setNotes('');
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not save your entry.');
    } finally { setBusy(false); }
  };

  if (!token) return <div className="min-h-screen bg-stone-50 py-6"><TopBack /><LoginGate onLogin={(t) => { setToken(t); }} /></div>;

  if (loading) return (
    <div className="min-h-screen bg-stone-50 grid place-items-center">
      <Loader2 size={30} className="animate-spin text-emerald-600" />
    </div>
  );

  const CONCERN_OPTS = [
    { slug: 'brightening-glow', label: 'Brightening & Glow' },
    { slug: 'aging', label: 'Anti-Aging' },
    { slug: 'acne-breakouts', label: 'Acne & Breakouts' },
    { slug: 'pigmentation', label: 'Pigmentation' },
    { slug: 'texture-pores', label: 'Texture & Pores' },
    { slug: 'hydration', label: 'Hydration' },
  ];

  return (
    <div className="min-h-screen bg-stone-50 pb-16">
      <TopBack />
      <div className="max-w-2xl mx-auto px-4 sm:px-6">

        {/* NOT ENROLLED */}
        {status && !status.enrolled && (
          <div className="mt-4 space-y-4">
            <div className="bg-gradient-to-br from-emerald-600 to-teal-600 rounded-3xl p-6 text-white">
              <div className="flex items-center gap-2 mb-2"><Sparkles size={20} /><span className="text-xs font-black uppercase tracking-wider">AI Skin Tracker</span></div>
              <h1 className="font-heading text-2xl font-black leading-tight">Track your glow-up, day by day</h1>
              <p className="text-sm text-white/90 mt-2">Daily AI tasks, photo progress & personalised improvement suggestions every 3 days.</p>
              {status.eligible_free ? (
                <div className="mt-4 bg-white/15 rounded-2xl p-3 flex items-center gap-2">
                  <Gift size={18} /><p className="text-sm font-bold">You qualify for <b>1 month FREE</b> (order ≥ ₹{status.free_order_min})!</p>
                </div>
              ) : (
                <div className="mt-4 bg-white/15 rounded-2xl p-3 flex items-center gap-2">
                  <Crown size={18} /><p className="text-sm font-bold">₹{status.price}/month auto-pay subscription</p>
                </div>
              )}
            </div>

            <div className="bg-white rounded-3xl ring-1 ring-stone-200 p-5 space-y-4">
              <h2 className="font-heading font-black text-stone-900">Tell us about your skin</h2>
              <div>
                <p className="text-xs font-bold text-stone-500 uppercase mb-2">Skin type</p>
                <div className="flex flex-wrap gap-2">
                  {['all', 'oily', 'dry', 'combination', 'sensitive'].map(s => (
                    <button key={s} onClick={() => setSkinType(s)}
                      className={`px-3 py-1.5 rounded-full text-xs font-bold ring-1 capitalize transition-colors ${skinType === s ? 'bg-emerald-600 text-white ring-emerald-600' : 'bg-white text-stone-600 ring-stone-200'}`}>{s}</button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-bold text-stone-500 uppercase mb-2">Age group</p>
                <div className="flex flex-wrap gap-2">
                  {['18-24', '25-35', '35-50', '50+'].map(a => (
                    <button key={a} onClick={() => setAge(a)}
                      className={`px-3 py-1.5 rounded-full text-xs font-bold ring-1 transition-colors ${age === a ? 'bg-emerald-600 text-white ring-emerald-600' : 'bg-white text-stone-600 ring-stone-200'}`}>{a}</button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-bold text-stone-500 uppercase mb-2">Your concerns</p>
                <div className="flex flex-wrap gap-2">
                  {CONCERN_OPTS.map(c => (
                    <button key={c.slug} onClick={() => toggleConcern(c.slug)}
                      className={`px-3 py-1.5 rounded-full text-xs font-bold ring-1 transition-colors ${concerns.includes(c.slug) ? 'bg-violet-600 text-white ring-violet-600' : 'bg-white text-stone-600 ring-stone-200'}`}>{c.label}</button>
                  ))}
                </div>
              </div>
              {error && <p className="text-xs text-rose-600">{error}</p>}
              <button onClick={enroll} disabled={enrolling} data-testid="tracker-enroll-btn"
                className="w-full py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-black text-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-60">
                {enrolling ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                {status.eligible_free ? 'Start my FREE tracker' : `Subscribe ₹${status.price}/mo & start`}
              </button>
            </div>
          </div>
        )}

        {/* ENROLLED */}
        {status && status.enrolled && (
          <div className="mt-4 space-y-4">
            {/* status card */}
            <div className="bg-white rounded-3xl ring-1 ring-stone-200 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${status.plan === 'free' ? 'bg-emerald-100 text-emerald-700' : status.plan === 'paid' ? 'bg-amber-100 text-amber-700' : 'bg-stone-100 text-stone-600'}`}>
                      {status.plan === 'free' ? 'FREE MONTH' : status.plan === 'paid' ? 'PREMIUM' : 'PENDING'}
                    </span>
                    {status.has_access && <span className="text-[10px] font-bold text-stone-400">Day {status.day_number}</span>}
                  </div>
                  <h1 className="font-heading text-xl font-black text-stone-900 mt-1">My Progress</h1>
                </div>
                {status.has_access && (
                  <div className="text-right">
                    <p className="text-2xl font-black text-emerald-600">{status.days_left}</p>
                    <p className="text-[10px] font-bold text-stone-400 uppercase">days left</p>
                  </div>
                )}
              </div>
            </div>

            {/* expired / needs subscription */}
            {!status.has_access && (
              <div className="bg-gradient-to-br from-amber-500 to-orange-500 rounded-3xl p-6 text-white text-center">
                <Lock size={26} className="mx-auto mb-2" />
                <h2 className="font-heading text-lg font-black">{status.plan === 'pending' ? 'Activate your tracker' : 'Your free month ended'}</h2>
                <p className="text-sm text-white/90 mt-1 mb-4">Continue your AI skin journey for ₹{status.price}/month (auto-pay).</p>
                {error && <p className="text-xs bg-white/20 rounded-lg px-3 py-2 mb-3">{error}</p>}
                <button onClick={subscribe} disabled={busy} data-testid="tracker-subscribe-btn"
                  className="w-full py-3 rounded-xl bg-white text-orange-600 font-black text-sm flex items-center justify-center gap-2 disabled:opacity-60">
                  {busy ? <Loader2 size={16} className="animate-spin" /> : <Crown size={16} />} Subscribe ₹{status.price}/month
                </button>
              </div>
            )}

            {status.has_access && (
              <>
                {/* today's tasks */}
                <div className="bg-white rounded-3xl ring-1 ring-stone-200 p-5">
                  <div className="flex items-center gap-2 mb-1">
                    <Calendar size={16} className="text-emerald-700" />
                    <h2 className="font-heading font-black text-stone-900">Today's plan</h2>
                  </div>
                  {status.today_focus && <p className="text-sm text-emerald-700 font-semibold mb-3">{status.today_focus}</p>}
                  <div className="space-y-2">
                    {(status.today_tasks || []).map((t, i) => {
                      const Icon = TASK_ICON[t.type] || Sun;
                      return (
                        <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-stone-50">
                          <span className={`shrink-0 w-8 h-8 rounded-lg grid place-items-center ring-1 ${TASK_STYLE[t.type] || 'bg-stone-100 text-stone-600 ring-stone-200'}`}>
                            <Icon size={15} />
                          </span>
                          <div className="min-w-0">
                            <p className="text-sm font-bold text-stone-900">{t.title}</p>
                            {t.detail && <p className="text-xs text-stone-500 mt-0.5">{t.detail}</p>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* daily log */}
                <div className="bg-white rounded-3xl ring-1 ring-stone-200 p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <Camera size={16} className="text-emerald-700" />
                    <h2 className="font-heading font-black text-stone-900">Log today's progress</h2>
                  </div>
                  <label className="block cursor-pointer">
                    <div className={`rounded-2xl border-2 border-dashed ${photo ? 'border-emerald-300' : 'border-stone-200'} p-4 text-center transition-colors`}>
                      {photo ? (
                        <img src={photo} alt="preview" className="w-28 h-28 object-cover rounded-xl mx-auto ring-1 ring-emerald-200" />
                      ) : (
                        <div className="py-4">
                          <Camera size={26} className="text-stone-300 mx-auto mb-1" />
                          <p className="text-xs font-bold text-stone-500">Tap to add today's selfie</p>
                        </div>
                      )}
                    </div>
                    <input type="file" accept="image/*" capture="user" onChange={onPhoto} className="hidden" data-testid="tracker-photo-input" />
                  </label>
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="How does your skin feel today? (optional)"
                    className="w-full mt-3 rounded-xl ring-1 ring-stone-200 p-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500 resize-none" data-testid="tracker-notes" />
                  {error && <p className="text-xs text-rose-600 mt-2">{error}</p>}
                  <button onClick={submitLog} disabled={busy} data-testid="tracker-log-btn"
                    className="w-full mt-3 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-black text-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-60">
                    {busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Save entry
                  </button>
                  <p className="text-[11px] text-stone-400 text-center mt-2">AI improvement suggestions arrive every 3 days ✨</p>
                </div>

                {/* timeline */}
                {(status.logs || []).length > 0 && (
                  <div className="bg-white rounded-3xl ring-1 ring-stone-200 p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp size={16} className="text-emerald-700" />
                      <h2 className="font-heading font-black text-stone-900">Your journey</h2>
                    </div>
                    <div className="space-y-3">
                      {status.logs.map((l) => (
                        <div key={l.id} className="flex gap-3 p-3 rounded-2xl bg-stone-50">
                          {l.photo_url ? (
                            <img src={l.photo_url} alt={`Day ${l.day_number}`} className="w-16 h-16 object-cover rounded-xl ring-1 ring-stone-200 shrink-0" />
                          ) : (
                            <div className="w-16 h-16 rounded-xl bg-stone-100 grid place-items-center shrink-0"><Moon size={18} className="text-stone-300" /></div>
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-black text-stone-900">Day {l.day_number}</span>
                              <span className="text-[10px] text-stone-400">{l.date}</span>
                              {l.ai_trend && <span className={`text-[9px] font-black px-1.5 py-0.5 rounded-full ${l.ai_trend === 'improving' ? 'bg-emerald-100 text-emerald-700' : l.ai_trend === 'needs attention' ? 'bg-rose-100 text-rose-700' : 'bg-stone-100 text-stone-500'}`}>{l.ai_trend}</span>}
                            </div>
                            {l.notes && <p className="text-xs text-stone-600 mt-0.5">{l.notes}</p>}
                            {l.ai_suggestion && (
                              <p className="text-xs text-emerald-800 bg-emerald-50 rounded-lg px-2 py-1.5 mt-1.5 flex gap-1.5">
                                <Sparkles size={13} className="shrink-0 mt-0.5" />{l.ai_suggestion}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {status.plan === 'free' && (
                  <Link to="#" onClick={(e) => { e.preventDefault(); subscribe(); }}
                    className="block bg-white rounded-2xl ring-1 ring-stone-200 p-4 hover:ring-amber-300 transition-colors">
                    <div className="flex items-center gap-3">
                      <Crown size={18} className="text-amber-500" />
                      <div className="flex-1">
                        <p className="text-sm font-bold text-stone-900">Keep it going after your free month</p>
                        <p className="text-xs text-stone-500">₹{status.price}/month auto-pay — cancel anytime</p>
                      </div>
                      <ChevronRight size={16} className="text-stone-400" />
                    </div>
                  </Link>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TopBack() {
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 pt-2">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-stone-500 hover:text-stone-900">
        <ArrowLeft size={16} /> Home
      </Link>
    </div>
  );
}
