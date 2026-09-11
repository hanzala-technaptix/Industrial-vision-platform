import React, { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import {
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

const Corners = () => (
  <>
    <i className="corner tl" />
    <i className="corner tr" />
    <i className="corner bl" />
    <i className="corner br" />
  </>
);

const firstDetector = (detectors) => (detectors.detectors || [])[0] || {};

const complianceTag = (state) => {
  if (state === 'compliant') return <span className="tag tag-accent">OK</span>;
  if (state === 'violating') return <span className="tag tag-solid">Miss</span>;
  return <span className="tag tag-neutral">—</span>;
};

const Dashboard = () => {
  const [catalog, setCatalog] = useState([]);
  const [current, setCurrent] = useState('ppe');
  const [stats, setStats] = useState({ total_events: 0, by_type: {}, violations_by_subtype: {} });
  const [health, setHealth] = useState({ status: 'loading' });
  const [detectors, setDetectors] = useState({ detectors: [], alerts: [] });
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
        const [h, s, d] = await Promise.all([
          fetchHealth().catch(() => ({ status: 'offline' })),
          fetchStats().catch(() => null),
          fetchDetectors().catch(() => ({ detectors: [], alerts: [] })),
        ]);
        if (!alive) return;
        setHealth(h);
        if (s) setStats(s);
        setDetectors(d);
        if (h.use_case) setCurrent(h.use_case);
        setError(null);
      } catch (err) {
        if (!alive) return;
        setError(String(err));
      }
    };
    const tickLive = async () => {
      try {
        const d = await fetchDetectors();
        if (!alive) return;
        setDetectors(d);
      } catch {
        /* keep last readings */
      }
    };
    refreshCatalog().catch((err) => setError(String(err)));
    tick();
    const t = setInterval(tick, 3000);
    const live = setInterval(tickLive, 400);
    return () => { alive = false; clearInterval(t); clearInterval(live); };
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
  const status = switching ? 'switching' : (health.status || 'unknown');
  const metrics = specMetrics(current, det, stats, persons);
  const alert = liveAlert(current, det, detectors.alerts || [], persons);

  return (
    <div className="board">
      <aside className="index">
        <div className="index-head">Drawing index · 01–08</div>
        {catalog.map((c) => {
          const on = c.id === current;
          return (
            <button
              key={c.id}
              type="button"
              className={`index-item ${on ? 'on' : ''}`}
              disabled={!c.ready || switching}
              onClick={() => onSelect(c.id, c.ready)}
              title={c.ready ? `${c.summary} · ${ENGINE_LABEL[c.engine] || c.engine}` : `Needs: ${c.expected_video}`}
            >
              {on && <Corners />}
              <span className="index-num">{c.number}</span>
              <span className="index-title">{c.title}</span>
              <span className="engine">
                {ENGINE_LABEL[c.engine] || c.engine}
                {!c.ready && ' · not ready'}
              </span>
            </button>
          );
        })}
      </aside>

      <section className="main">
        <div className="title-block">
          <Corners />
          <div className="title-no">{active.number || '—'}</div>
          <div className="title-copy">
            <div className="title-kicker">Factory vision · spec sheet</div>
            <h1 className="title-name">{active.title || 'Showcase'}</h1>
            <p className="title-summary">{active.summary || 'Select a use case from the index'}</p>
          </div>
          <div className="title-status">
            <span className={status === 'healthy' ? 'tag tag-accent' : 'tag tag-solid'}>
              <Activity size={14} strokeWidth={1.5} />
              {status}
            </span>
          </div>
        </div>

        {error && <div className="banner">{error}</div>}

        <div className="work">
          <div className="figure">
            <div className="figure-bar">
              <span>Fig. 01 — Live feed</span>
              <span>Boxes only · status on the right</span>
            </div>
            <div className="figure-stage">
              <Corners />
              {videoError ? (
                <div className="feed-empty">
                  <div>Video feed unavailable</div>
                  <button type="button" className="btn btn-primary" onClick={() => setVideoError(false)}>
                    Retry
                  </button>
                </div>
              ) : (
                <img
                  src={videoFeedUrl(videoToken)}
                  alt="Live feed"
                  onError={() => setVideoError(true)}
                />
              )}
            </div>
            <div className="figure-meta">
              <div className="meta-cell">
                <span>Engine</span>
                <strong>{ENGINE_LABEL[active.engine] || active.engine || '—'}</strong>
              </div>
              <div className="meta-cell">
                <span>Detector</span>
                <strong>{det.detector || current || '—'}</strong>
              </div>
              <div className="meta-cell">
                <span>Pipeline</span>
                <strong>{switching ? 'Load' : 'Run'}</strong>
              </div>
            </div>
          </div>

          <aside className="spec">
            <Corners />
            <div className="spec-bar">
              <span>Alert · readings</span>
              <span>Live</span>
            </div>
            {alert && (
              <div className={`alert-plate ${alert.tone || ''}`}>
                <div className="alert-kicker">{alert.kicker}</div>
                <div className="alert-title">{alert.title}</div>
                {alert.note && <div className="alert-note">{alert.note}</div>}
                {alert.lines?.length > 0 && (
                  <ul className="alert-lines">
                    {alert.lines.map((line) => <li key={line}>{line}</li>)}
                  </ul>
                )}
              </div>
            )}
            <dl className="spec-rows">
              {metrics.map((row) => (
                <div className="spec-row" key={row.label}>
                  <dt>{row.label}</dt>
                  <dd className={row.tone || ''}>{row.value}</dd>
                  {row.note && <div className="spec-note">{row.note}</div>}
                </div>
              ))}
            </dl>
          </aside>
        </div>

        {current === 'ppe' && <PpeTable persons={persons} />}
      </section>
    </div>
  );
};

function liveAlert(current, det, alerts, persons) {
  if (current === 'worker_idle') {
    const state = (det.state || 'absent').toUpperCase();
    const threshold = det.idle_seconds ?? 8;
    const idleFor = det.idle_for || 0;
    const motion = det.motion || 0;
    return {
      kicker: 'Worker',
      title: state,
      tone: det.state === 'active' ? 'ok' : 'warn',
      note: det.state === 'absent'
        ? 'No person in frame · timer holds at 0'
        : `Idle ${idleFor.toFixed(1)}s / ${threshold}s · motion ${motion.toFixed(3)}`,
    };
  }
  if (current === 'ppe') {
    const violating = persons.filter((p) => (p.violating || []).length).length;
    return {
      kicker: 'PPE',
      title: violating ? `${violating} miss` : 'Clear',
      tone: violating ? 'warn' : 'ok',
      lines: alerts.length ? alerts : (violating ? ['See Schedule A'] : ['No active PPE alerts']),
    };
  }
  if (current === 'zone') {
    return {
      kicker: 'Zone',
      title: det.present ? 'Intrusion' : 'Clear',
      tone: det.present ? 'warn' : 'ok',
      note: `${det.person_count ?? 0} people in view`,
    };
  }
  if (current === 'person') {
    return {
      kicker: 'People',
      title: String(det.count ?? 0),
      tone: 'ok',
      note: 'On-floor count',
    };
  }
  if (current === 'product_counting') {
    return {
      kicker: 'Line count',
      title: String(det.count ?? 0),
      tone: 'ok',
      note: 'Motion blobs crossing the line',
    };
  }
  if (current === 'quality') {
    const ok = String(det.label || '').toLowerCase() === 'good';
    return {
      kicker: 'Inspection',
      title: (det.label || '—').toUpperCase(),
      tone: ok ? 'ok' : 'warn',
      note: `Confidence ${(det.confidence || 0).toFixed(2)}`,
    };
  }
  if (current === 'machine_idle' || current === 'downtime') {
    const idle = det.state === 'idle';
    return {
      kicker: 'Machine',
      title: idle ? 'IDLE' : 'RUNNING',
      tone: idle ? 'warn' : 'ok',
      note: `Idle ${(det.idle_for || 0).toFixed(1)}s · motion ${(det.motion || 0).toFixed(3)}`,
    };
  }
  return { kicker: 'Detector', title: det.detector || '—', tone: '' };
}

function specMetrics(current, det, stats, persons) {
  if (current === 'ppe') {
    const subtypes = Object.entries(stats.violations_by_subtype || {});
    return [
      { label: 'Tracked persons', value: persons.length },
      { label: 'Events', value: stats.total_events || 0, note: `${stats.by_type?.ppe_violation || 0} violations · ${stats.by_type?.ppe_compliant || 0} recoveries` },
      { label: 'Top violation', value: subtypes[0] ? `${subtypes[0][0]} ${subtypes[0][1]}` : '—' },
    ];
  }
  if (current === 'person') {
    return [{ label: 'People on floor', value: det.count ?? 0 }];
  }
  if (current === 'zone') {
    return [
      { label: 'Zone', value: det.present ? 'Intrusion' : 'Clear', tone: det.present ? 'warn' : 'ok' },
      { label: 'People', value: det.person_count ?? 0 },
    ];
  }
  if (current === 'worker_idle') {
    return [
      { label: 'Idle timer', value: `${(det.idle_for || 0).toFixed(1)}s` },
      { label: 'Motion', value: (det.motion || 0).toFixed(3) },
      { label: 'Threshold', value: `${det.idle_seconds ?? 8}s` },
    ];
  }
  if (current === 'product_counting') {
    return [{ label: 'Line count', value: det.count ?? 0 }];
  }
  if (current === 'quality') {
    return [
      { label: 'Confidence', value: (det.confidence || 0).toFixed(2), note: 'Still images · trained classifier' },
    ];
  }
  if (current === 'machine_idle' || current === 'downtime') {
    return [
      { label: 'Uptime', value: `${(det.uptime_pct || 0).toFixed(0)}%`, note: `run ${(det.running_s || 0).toFixed(0)}s · idle ${(det.idle_s || 0).toFixed(0)}s` },
      { label: 'Motion', value: (det.motion || 0).toFixed(3) },
    ];
  }
  return [{ label: 'Detector', value: det.detector || '—' }];
}

const PpeTable = ({ persons }) => (
  <div className="sheet">
    <div className="sheet-kicker">Schedule A — PPE compliance ({persons.length})</div>
    {persons.length === 0 ? (
      <div className="muted">No persons currently tracked.</div>
    ) : (
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Track</th>
              {REQUIRED_PPE.map((k) => <th key={k}>{k}</th>)}
              <th>Violating</th>
            </tr>
          </thead>
          <tbody>
            {persons.map((p) => (
              <tr key={p.track_id}>
                <td><strong>#{p.track_id}</strong></td>
                {REQUIRED_PPE.map((k) => (
                  <td key={k}>{complianceTag(p.compliance?.[k] || 'unknown')}</td>
                ))}
                <td className={(p.violating || []).length ? 'warn' : 'muted'}>
                  {(p.violating || []).join(', ') || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

export default Dashboard;
