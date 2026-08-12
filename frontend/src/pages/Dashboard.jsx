import React, { useState, useEffect } from 'react';
import { fetchEvents, fetchHealth } from '../services/api';

const Dashboard = () => {
    const [events, setEvents] = useState([]);
    const [status, setStatus] = useState('loading');
    const [error, setError] = useState(null);
    const [videoError, setVideoError] = useState(false);

    const videoUrl = `${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/video_feed`;

    useEffect(() => {
        let isMounted = true;
        const refreshEvents = async () => {
            try {
                const health = await fetchHealth();
                if (!isMounted) return;
                setStatus(health.status === 'healthy' ? 'online' : 'degraded');
            } catch (err) {
                if (!isMounted) return;
                setStatus('offline');
                setError('Backend unavailable');
            }

            try {
                const latestEvents = await fetchEvents(20);
                if (!isMounted) return;
                setEvents(latestEvents);
                setError(null);
            } catch (err) {
                if (!isMounted) return;
                setError('Unable to load event feed');
            }
        };

        refreshEvents();
        const interval = setInterval(refreshEvents, 3000);
        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, []);

    return (
        <div className="dashboard-page" style={{ padding: '2rem' }}>
            <div style={{ marginBottom: '2rem' }}>
                <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Live Surveillance Feed</h1>
                <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                    Camera 01 - Main Entrance
                </p>
            </div>

            <div className="video-container">
                {/* The Scanning Animation */}
                <div className="scan-line"></div>
                <div className="grid-overlay"></div>

                <div style={{
                    position: 'absolute',
                    top: '1rem',
                    right: '1rem',
                    background: 'rgba(255,255,255,0.9)',
                    borderRadius: '999px',
                    padding: '0.5rem 1rem',
                    fontSize: '0.85rem',
                    fontWeight: '600'
                }}>
                    {status === 'online' ? 'LIVE' : status === 'degraded' ? 'DEGRADED' : 'OFFLINE'}
                </div>

                {videoError ? (
                    <div style={{
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#ef4444',
                        flexDirection: 'column',
                        gap: '1rem'
                    }}>
                        <span style={{ fontSize: '3rem' }}>⚠️</span>
                        <h2 style={{ margin: 0 }}>Feed Unavailable</h2>
                        <p style={{ color: 'var(--text-muted)', margin: 0 }}>
                            Unable to connect to camera stream.
                        </p>
                        <button 
                            onClick={() => setVideoError(false)}
                            style={{
                                padding: '0.5rem 1rem',
                                background: 'var(--color-accent)',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer'
                            }}
                        >
                            Retry Connection
                        </button>
                    </div>
                ) : (
                    <img 
                        src={videoUrl} 
                        alt="Live Surveillance Feed"
                        onError={() => setVideoError(true)}
                        style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            display: 'block'
                        }}
                    />
                )}
            </div>

            {/* Quick Stats Summary */}
            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                gap: '1.5rem', 
                marginTop: '2rem' 
            }}>
                <div className="stat-card" style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '8px' }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>Status</div>
                    <div style={{ color: 'var(--color-accent)', fontWeight: 'bold' }}>
                        {status === 'online' ? 'ONLINE' : status === 'degraded' ? 'DEGRADED' : 'OFFLINE'}
                    </div>
                </div>
                <div className="stat-card" style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '8px' }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>Recent Events</div>
                    <div style={{ fontWeight: 'bold' }}>{events.length}</div>
                </div>
                <div className="stat-card" style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '8px' }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>Refresh Rate</div>
                    <div style={{ fontWeight: 'bold' }}>3 sec</div>
                </div>
            </div>

            <div style={{ marginTop: '2rem' }}>
                <h2 style={{ marginBottom: '1rem' }}>Latest Backend Events</h2>
                {events.length === 0 ? (
                    <p style={{ color: 'var(--text-muted)' }}>
                        No events yet. The backend is collecting detection events from the pipeline.
                    </p>
                ) : (
                    <div style={{ display: 'grid', gap: '1rem' }}>
                        {events.map((event) => (
                            <div key={event.event_id || `${event.event_type}-${event.timestamp}`} className="stat-card" style={{ background: 'var(--bg-card)', padding: '1rem', borderRadius: '8px' }}>
                                <div style={{ fontWeight: '700', marginBottom: '0.5rem' }}>{event.event_type.replace('_', ' ').toUpperCase()}</div>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '0.75rem' }}>
                                    <div><strong>Confidence</strong><br />{event.confidence.toFixed(2)}</div>
                                    <div><strong>Camera</strong><br />{event.camera_id}</div>
                                    <div><strong>Timestamp</strong><br />{new Date(event.timestamp * 1000).toLocaleTimeString()}</div>
                                    <div><strong>BBox</strong><br />[{event.bbox.map((n) => n.toFixed(0)).join(', ')}]</div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
