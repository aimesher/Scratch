import { Zap, Image, Clock, Activity } from 'lucide-react'
import { accountStats } from '../utils/mockData'

function UsageBar({ used, limit, color }) {
  const pct = Math.min((used / limit) * 100, 100)
  return (
    <div style={{ marginTop: 10 }}>
      <div style={styles.barLabels}>
        <span>{used.toLocaleString()} used</span>
        <span>{limit.toLocaleString()} limit</span>
      </div>
      <div style={styles.bar}>
        <div style={{ ...styles.barFill, width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

export default function StatsBar() {
  const s = accountStats
  return (
    <div style={styles.grid}>
      <div style={{ ...styles.card, borderColor: 'rgba(255,193,7,0.2)', background: 'linear-gradient(135deg, rgba(255,193,7,0.06), transparent)' }}>
        <div style={styles.label}><Zap size={14} /> API Calls</div>
        <div style={{ ...styles.value, color: '#ffca28' }}>{s.apiCalls.used.toLocaleString()}</div>
        <UsageBar used={s.apiCalls.used} limit={s.apiCalls.limit} color="#ffc107" />
      </div>

      <div style={styles.card}>
        <div style={styles.label}><Activity size={14} /> Tokens Used</div>
        <div style={{ ...styles.value, color: '#66bb6a' }}>{(s.tokens.used / 1e6).toFixed(1)}M</div>
        <UsageBar used={s.tokens.used} limit={s.tokens.limit} color="#4caf50" />
      </div>

      <div style={styles.card}>
        <div style={styles.label}><Image size={14} /> Image Credits</div>
        <div style={{ ...styles.value, color: '#ff7043' }}>{s.imageCredits.used}</div>
        <UsageBar used={s.imageCredits.used} limit={s.imageCredits.limit} color="#ff5722" />
      </div>

      <div style={styles.card}>
        <div style={styles.label}><Clock size={14} /> Video Minutes</div>
        <div style={styles.value}>{s.videoMinutes.used}</div>
        <UsageBar used={s.videoMinutes.used} limit={s.videoMinutes.limit} color="#ffca28" />
      </div>
    </div>
  )
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 16,
    marginBottom: 28,
  },
  card: {
    background: '#1a1d22',
    border: '1px solid #2a2d35',
    borderRadius: 14,
    padding: '20px 22px',
    transition: 'all 0.2s',
  },
  label: {
    fontSize: 12,
    color: '#868e96',
    marginBottom: 8,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  value: {
    fontSize: 26,
    fontWeight: 700,
    letterSpacing: -0.5,
    color: '#f1f3f5',
  },
  barLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    color: '#5c636a',
    marginBottom: 6,
  },
  bar: {
    height: 6,
    background: '#212529',
    borderRadius: 3,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: 3,
    transition: 'width 0.8s ease',
  },
}
