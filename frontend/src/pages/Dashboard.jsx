import React, { useEffect, useState } from 'react';
import {
  fetchEvents,
  fetchStats,
  fetchHealth,
  fetchDetectors,
  videoFeedUrl,
} from '../services/api';

const REQUIRED_PPE = ['hardhat', 'mask', 'vest', 'gloves'];

const badge = (state) => {
  const map = {
    compliant: { bg: '#10b981', label: 'OK' },
    violating: { bg: '#ef4444', label: 'MISS' },
    unknown:   { bg: '#6b7280', label: '—' },
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

const Dashboard = () => {
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({ total_events: 0, by_type: {}, violations_by_subtype: {}, unique_tracks: 0 });
  const [health, setHealth] = useState({ status: 'loading' });
  const [detectors, setDetectors] = useState({ detectors: [] });
  const [videoError, setVideoError] = useState(false);
  const [error, setError] = useState(null);

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
        setError(null);
      } catch (err) {
        if (!alive) return;
        setError(String(err));
      }
    };
    tick();
    const t = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const ppeDetector = (detectors.detectors || []).find((x) => x.detector === 'ppe') || {};
  const persons = ppeDetector.persons || [];
  const status = health.status || 'unknown';

  const violationCount = events.filter((e) => e.event_type === 'ppe_violation').length;

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Factory AI — Phase 1: PPE</h1>
          <p style={{ color: 'var(--text-muted, #9ca3af)', margin: '4px 0 0' }}>
            Person + Helmet · Mask · Vest · Gloves
          </p>
        </div>
        <span style={{
          background: status === 'healthy' ? '#10b981' : (status === 'starting' ? '#f59e0b' : '#ef4444'),
          color: 'white', padding: '4px 12px', borderRadius: 999,
          fontSize: '0.75rem', fontWeight: 700,
        }}>{status.toUpperCase()}</span>
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', color: 'white', padding: '0.75rem 1rem', borderRadius: 6, marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 2fr) minmax(280px, 1fr)', gap: '1rem' }}>
        {/* LEFT — video */}
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ position: 'relative', background: '#000', aspectRatio: '16/9' }}>
            {videoError ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#f87171' }}>
                <span style={{ fontSize: '2.5rem' }}>⚠️</span>
                <div>Video feed unavailable</div>
                <button onClick={() => setVideoError(false)} style={{ marginTop: 8, padding: '4px 12px', border: 0, borderRadius: 4, cursor: 'pointer' }}>Retry</button>
              </div>
            ) : (
              <img
                src={videoFeedUrl()}
                alt="Live feed"
                onError={() => setVideoError(true)}
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            )}
          </div>
        </Card>

        {/* RIGHT — live stats */}
        <div style={{ display: 'grid', gap: '1rem', gridAutoRows: 'min-content' }}>
          <Card>
            <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tracked persons</div>
            <div style={{ fontSize: '2rem', fontWeight: 700 }}>{persons.length}</div>
          </Card>
          <Card>
            <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total events</div>
            <div style={{ fontSize: '2rem', fontWeight: 700 }}>{stats.total_events}</div>
            <div style={{ fontSize: '0.8rem', color: '#f87171', marginTop: 4 }}>
              {stats.by_type?.ppe_violation || 0} violations · {stats.by_type?.ppe_compliant || 0} recoveries
            </div>
          </Card>
          <Card>
            <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Violations by type</div>
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
              )
            }
          </Card>
        </div>
      </div>

      {/* Compliance table — one row per tracked person */}
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

      {/* Event feed */}
      <Card style={{ marginTop: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, fontSize: '1rem' }}>Recent events</h2>
          <span style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.8rem' }}>{events.length} shown · refresh 3s</span>
        </div>
        {events.length === 0 ? (
          <div style={{ color: 'var(--text-muted, #9ca3af)', fontSize: '0.9rem' }}>No events yet.</div>
        ) : (
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
                    <span style={{ color: 'var(--text-muted, #9ca3af)' }}>· {e.camera_id}</span>
                  </span>
                  <span style={{ textAlign: 'right', color: 'var(--text-muted, #9ca3af)' }}>{(e.confidence || 0).toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
};

export default Dashboard;
