import React, { useEffect, useState } from 'react';
import {
  fetchEvents,
  fetchStats,
  fetchHealth,
  fetchDetectors,
  fetchUseCases,
  switchUseCase,
  videoFeedUrl,
} from '../services/api';

const REQUIRED_PPE = ['hardhat', 'mask', 'vest', 'gloves'];

const ENGINE_LABEL = {
  model: 'Trained model',
  motion: 'Motion (demo)',
  hybrid: 'Model + motion',
};

const badge = (state) => {
  const map = {
    compliant: { bg: '#10b981', label: 'OK' },
    violating: { bg: '#ef4444', label: 'MISS' },
    unknown: { bg: '#6b7280', label: '—' },
  };
  const s = map[state] || map.unknown;
  return (
    <span style={{
      display: 'inline-block',
      background: s.bg, color: 'white',
      padding: '2px 8px', borderRadius: 999,
      fontSize: '0.7rem', fontWeight: 700,
      minWidth: 40, textAlign: 'center',
    }}>{s.label}</span>
  );
};

const Card = ({ children, style }) => (
  <div style={{
    background: 'var(--bg-card, #1f2937)',
    borderRadius: 8, padding: '1rem',
    border: '1px solid rgba(255,255,255,0.06)',
    ...style,
  }}>{children}</div>
);

const firstDetector = (detectors) => (detectors.detectors || [])[0] || {};

const Dashboard = () => {
  const [catalog, setCatalog] = useState([]);
  const [current, setCurrent] = useState('ppe');
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({ total_events: 0, by_type: {}, violations_by_subtype: {} });
  const [health, setHealth] = useState({ status: 'loading' });
  const [detectors, setDetectors] = useState({ detectors: [] });
  const [videoToken, setVideoToken] = useState(1);
  const [videoError, setVideoError] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState(null);

  const refreshCatalog = async () => {
    const data = await fetchUseCases();
    setCatalog(data.use_cases || []);
    if (data.current) setCurrent(data.current);
    return data;
  };

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const [h, s, d, e] = await Promise.all([
          fetchHealth().catch(() => ({ status: 'offline' })),
          fetchStats().catch(() => null),
          fetchDetectors().catch(() => ({ detectors: [] })),
          fetchEvents(30).catch(() => []),
        ]);
        if (!alive) return;
        setHealth(h);
        if (s) setStats(s);
        setDetectors(d);
        setEvents(e);
        if (h.use_case) setCurrent(h.use_case);
        setError(null);
      } catch (err) {
        if (!alive) return;
        setError(String(err));
      }
    };
    refreshCatalog().catch((err) => setError(String(err)));
    tick();
    const t = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const onSelect = async (id, ready) => {
    if (!ready || switching || id === current) return;
    setSwitching(true);
    setError(null);
    try {
      const data = await switchUseCase(id);
      setCatalog(data.use_cases || []);
      setCurrent(data.current || id);
      setVideoError(false);
      setVideoToken((n) => n + 1);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setSwitching(false);
    }
  };

  const active = catalog.find((c) => c.id === current) || {};
  const det = firstDetector(detectors);
  const persons = det.persons || [];
  const status = health.status || 'unknown';

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '1rem', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>
            {active.number ? `${active.number} — ${active.title}` : 'Factory AI showcase'}
          </h1>
          <p style={{ color: 'var(--text-muted, #9ca3af)', margin: '4px 0 0' }}>
            {active.summary || 'Select a use case'}
          </p>
        </div>
        <span style={{
          background: status === 'healthy' ? '#10b981' : (status === 'starting' ? '#f59e0b' : '#ef4444'),
          color: 'white', padding: '4px 12px', borderRadius: 999,
          fontSize: '0.75rem', fontWeight: 700,
        }}>{switching ? 'SWITCHING' : status.toUpperCase()}</span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: '1rem' }}>
        {catalog.map((c) => {
          const on = c.id === current;
          return (
            <button
              key={c.id}
              type="button"
              disabled={!c.ready || switching}
              onClick={() => onSelect(c.id, c.ready)}
              title={c.ready ? `${c.summary} · ${ENGINE_LABEL[c.engine] || c.engine}` : `Needs: ${c.expected_video}`}
              style={{
                border: on ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.12)',
                background: on ? 'rgba(16,185,129,0.15)' : (c.ready ? '#1e293b' : '#111827'),
                color: c.ready ? '#f8fafc' : '#64748b',
                padding: '8px 12px',
                borderRadius: 8,
                cursor: c.ready && !switching ? 'pointer' : 'not-allowed',
                fontSize: '0.8rem',
              }}
            >
              <strong>{c.number}</strong> {c.title}
              <div style={{ fontSize: '0.65rem', opacity: 0.7, marginTop: 2 }}>
                {ENGINE_LABEL[c.engine] || c.engine || ''}
                {!c.ready && ' · not ready'}
              </div>
            </button>
          );
        })}
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', color: 'white', padding: '0.75rem 1rem', borderRadius: 6, marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 2fr) minmax(280px, 1fr)', gap: '1rem' }}>
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ position: 'relative', background: '#000', aspectRatio: '16/9' }}>
            {videoError ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#f87171' }}>
                <div>Video feed unavailable</div>
                <button
                  type="button"
                  onClick={() => setVideoError(false)}
                  style={{ marginTop: 8, padding: '4px 12px', border: 0, borderRadius: 4, cursor: 'pointer' }}
                >
                  Retry
                </button>
              </div>
            ) : (
              <img
                src={videoFeedUrl(videoToken)}
                alt="Live feed"
                onError={() => setVideoError(true)}
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            )}
          </div>
        </Card>

        <div style={{ display: 'grid', gap: '1rem', gridAutoRows: 'min-content' }}>
          <StatsCards current={current} det={det} stats={stats} persons={persons} />
        </div>
      </div>

      {current === 'ppe' && (
        <PpeTable persons={persons} events={events} stats={stats} />
      )}
      {current !== 'ppe' && events.length > 0 && (
        <Card style={{ marginTop: '1rem' }}>
          <h2 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Recent events</h2>
          <EventList events={events} />
        </Card>
      )}
    </div>
  );
};

const StatsCards = ({ current, det, stats, persons }) => {
  if (current === 'ppe') {
    return (
      <>
        <Card>
          <div style={labelStyle}>Tracked persons</div>
          <div style={valueStyle}>{persons.length}</div>
        </Card>
        <Card>
          <div style={labelStyle}>Total events</div>
          <div style={valueStyle}>{stats.total_events || 0}</div>
          <div style={{ fontSize: '0.8rem', color: '#f87171', marginTop: 4 }}>
            {stats.by_type?.ppe_violation || 0} violations · {stats.by_type?.ppe_compliant || 0} recoveries
          </div>
        </Card>
        <Card>
          <div style={labelStyle}>Violations by type</div>
          {Object.keys(stats.violations_by_subtype || {}).length === 0
            ? <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.85rem', marginTop: 6 }}>No violations recorded</div>
            : (
              <ul style={{ margin: '6px 0 0', padding: 0, listStyle: 'none' }}>
                {Object.entries(stats.violations_by_subtype).map(([k, v]) => (
                  <li key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', padding: '2px 0' }}>
                    <span>{k}</span><strong>{v}</strong>
                  </li>
                ))}
              </ul>
            )}
        </Card>
      </>
    );
  }
  if (current === 'person') {
    return (
      <Card>
        <div style={labelStyle}>People on floor</div>
        <div style={valueStyle}>{det.count ?? 0}</div>
      </Card>
    );
  }
  if (current === 'zone') {
    return (
      <>
        <Card>
          <div style={labelStyle}>Zone</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: det.present ? '#f87171' : '#10b981' }}>
            {det.present ? 'INTRUSION' : 'CLEAR'}
          </div>
        </Card>
        <Card>
          <div style={labelStyle}>People</div>
          <div style={valueStyle}>{det.person_count ?? 0}</div>
        </Card>
      </>
    );
  }
  if (current === 'worker_idle') {
    const color = det.state === 'active' ? '#10b981' : (det.state === 'idle' ? '#f59e0b' : '#ef4444');
    return (
      <>
        <Card>
          <div style={labelStyle}>Worker</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color }}>{(det.state || 'absent').toUpperCase()}</div>
        </Card>
        <Card>
          <div style={labelStyle}>Idle timer</div>
          <div style={valueStyle}>{(det.idle_for || 0).toFixed(1)}s</div>
        </Card>
      </>
    );
  }
  if (current === 'product_counting') {
    return (
      <Card>
        <div style={labelStyle}>Line count</div>
        <div style={valueStyle}>{det.count ?? 0}</div>
      </Card>
    );
  }
  if (current === 'quality') {
    const ok = String(det.label || '').toLowerCase() === 'good';
    return (
      <>
        <Card>
          <div style={labelStyle}>Inspection</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: ok ? '#10b981' : '#ef4444' }}>
            {(det.label || '—').toUpperCase()}
          </div>
        </Card>
        <Card>
          <div style={labelStyle}>Confidence</div>
          <div style={valueStyle}>{(det.confidence || 0).toFixed(2)}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted, #9ca3af)', marginTop: 4 }}>
            Still images · trained classifier
          </div>
        </Card>
      </>
    );
  }
  if (current === 'machine_idle' || current === 'downtime') {
    const color = det.state === 'idle' ? '#ef4444' : '#10b981';
    return (
      <>
        <Card>
          <div style={labelStyle}>Machine</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color }}>
            {det.state === 'idle' ? 'IDLE' : 'RUNNING'}
          </div>
        </Card>
        <Card>
          <div style={labelStyle}>Uptime</div>
          <div style={valueStyle}>{(det.uptime_pct || 0).toFixed(0)}%</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted, #9ca3af)', marginTop: 4 }}>
            run {(det.running_s || 0).toFixed(0)}s · idle {(det.idle_s || 0).toFixed(0)}s
          </div>
        </Card>
      </>
    );
  }
  return (
    <Card>
      <div style={labelStyle}>Detector</div>
      <div style={valueStyle}>{det.detector || '—'}</div>
    </Card>
  );
};

const PpeTable = ({ persons, events, stats }) => (
  <>
    <Card style={{ marginTop: '1rem' }}>
      <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Live PPE compliance ({persons.length})</h2>
      {persons.length === 0 ? (
        <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.9rem' }}>No persons currently tracked.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <th style={{ padding: '6px 4px' }}>Track</th>
                {REQUIRED_PPE.map((k) => (
                  <th key={k} style={{ padding: '6px 4px', textTransform: 'capitalize' }}>{k}</th>
                ))}
                <th style={{ padding: '6px 4px' }}>Violating</th>
              </tr>
            </thead>
            <tbody>
              {persons.map((p) => (
                <tr key={p.track_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <td style={{ padding: '6px 4px' }}><strong>#{p.track_id}</strong></td>
                  {REQUIRED_PPE.map((k) => (
                    <td key={k} style={{ padding: '6px 4px' }}>{badge(p.compliance?.[k] || 'unknown')}</td>
                  ))}
                  <td style={{ padding: '6px 4px', color: (p.violating || []).length ? '#f87171' : 'inherit' }}>
                    {(p.violating || []).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
    <Card style={{ marginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Recent events</h2>
        <span style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.8rem' }}>{events.length} shown</span>
      </div>
      <EventList events={events} />
    </Card>
  </>
);

const EventList = ({ events }) => {
  if (events.length === 0) {
    return <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.9rem' }}>No events yet.</div>;
  }
  return (
    <div style={{ display: 'grid', gap: '0.5rem', maxHeight: 400, overflowY: 'auto' }}>
      {events.map((e) => {
        const isViolation = e.event_type === 'ppe_violation';
        return (
          <div key={e.id} style={{
            display: 'grid',
            gridTemplateColumns: '110px 140px 1fr 90px',
            gap: '0.5rem',
            padding: '6px 8px',
            borderLeft: `3px solid ${isViolation ? '#ef4444' : (e.event_type === 'ppe_compliant' ? '#10b981' : '#6b7280')}`,
            background: 'rgba(255,255,255,0.02)',
            borderRadius: 4,
            alignItems: 'center',
            fontSize: '0.85rem',
          }}>
            <span style={{ fontFamily: 'monospace', color: 'var(--text-muted, #9ca3af)' }}>
              {new Date(e.timestamp_ms || (e.timestamp || 0) * 1000).toLocaleTimeString()}
            </span>
            <strong style={{ color: isViolation ? '#f87171' : 'inherit' }}>{e.event_type}</strong>
            <span>
              {e.event_subtype && <span style={{ color: '#fbbf24' }}>{e.event_subtype} </span>}
              {e.track_id != null && <span style={{ color: 'var(--text-muted, #9ca3af)' }}>track #{e.track_id} </span>}
            </span>
            <span style={{ textAlign: 'right', color: 'var(--text-muted, #9ca3af)' }}>{(e.confidence || 0).toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
};

const labelStyle = {
  color: 'var(--text-muted, #9ca3af)',
  fontSize: '0.75rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};
const valueStyle = { fontSize: '2rem', fontWeight: 700 };

export default Dashboard;
