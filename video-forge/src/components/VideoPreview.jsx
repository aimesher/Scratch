import { Play, Download, Share2, RotateCcw, CheckCircle2 } from 'lucide-react'

export default function VideoPreview({ completedSteps }) {
  const isReady = completedSteps.has('video')

  if (!isReady) return null

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <CheckCircle2 size={18} style={{ color: '#66bb6a' }} />
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Video Ready</h3>
        </div>
        <div style={styles.readyBadge}>
          <div style={styles.dot} />
          Export Ready
        </div>
      </div>
      <div style={styles.body}>
        <div style={styles.player}>
          <div style={styles.playOverlay}>
            <div style={styles.playBtn}>
              <Play size={28} fill="white" />
            </div>
          </div>
          <div style={styles.playerBottom}>
            <div style={styles.timeline}>
              <div style={styles.timelineFill} />
            </div>
            <div style={styles.playerInfo}>
              <span>0:00 / 1:00</span>
              <span>1080p • H.264</span>
            </div>
          </div>
        </div>

        <div style={styles.actions}>
          <button style={styles.actionBtn}>
            <Download size={16} />
            Export MP4
          </button>
          <button style={styles.actionBtnSecondary}>
            <Share2 size={16} />
            Share
          </button>
          <button style={styles.actionBtnSecondary}>
            <RotateCcw size={16} />
            Regenerate
          </button>
        </div>

        <div style={styles.meta}>
          <div style={styles.metaRow}>
            <span style={styles.metaLabel}>Format</span>
            <span style={styles.metaValue}>MP4 (H.264)</span>
          </div>
          <div style={styles.metaRow}>
            <span style={styles.metaLabel}>Resolution</span>
            <span style={styles.metaValue}>1080 × 1920</span>
          </div>
          <div style={styles.metaRow}>
            <span style={styles.metaLabel}>Duration</span>
            <span style={styles.metaValue}>1:00</span>
          </div>
          <div style={styles.metaRow}>
            <span style={styles.metaLabel}>Scenes</span>
            <span style={styles.metaValue}>6</span>
          </div>
          <div style={styles.metaRow}>
            <span style={styles.metaLabel}>Image Model</span>
            <span style={styles.metaValue}>Nano Banana Pro</span>
          </div>
          <div style={styles.metaRow}>
            <span style={styles.metaLabel}>AI Engine</span>
            <span style={styles.metaValue}>Gemini 2.5 Pro</span>
          </div>
        </div>
      </div>
    </div>
  )
}

const styles = {
  card: {
    background: '#1a1d22',
    border: '1px solid #2a2d35',
    borderRadius: 14,
    overflow: 'hidden',
  },
  header: {
    padding: '20px 24px',
    borderBottom: '1px solid #2a2d35',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  readyBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '5px 12px',
    borderRadius: 100,
    fontSize: 11,
    fontWeight: 600,
    background: 'rgba(76,175,80,0.15)',
    color: '#66bb6a',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#66bb6a',
  },
  body: { padding: 24 },
  player: {
    aspectRatio: '16/9',
    background: 'linear-gradient(135deg, #0d0f12, #212529)',
    borderRadius: 10,
    position: 'relative',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  playOverlay: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'absolute',
    inset: 0,
  },
  playBtn: {
    width: 64,
    height: 64,
    borderRadius: '50%',
    background: 'rgba(255,193,7,0.9)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    paddingLeft: 4,
  },
  playerBottom: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: '12px 16px',
    background: 'linear-gradient(transparent, rgba(0,0,0,0.8))',
  },
  timeline: {
    height: 3,
    background: 'rgba(255,255,255,0.15)',
    borderRadius: 2,
    marginBottom: 8,
    overflow: 'hidden',
  },
  timelineFill: {
    width: '0%',
    height: '100%',
    background: '#ffc107',
    borderRadius: 2,
  },
  playerInfo: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    color: 'rgba(255,255,255,0.6)',
  },
  actions: {
    display: 'flex',
    gap: 10,
    marginBottom: 20,
  },
  actionBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 20px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    border: 'none',
    fontFamily: 'inherit',
    background: 'linear-gradient(135deg, #ffc107, #ffb300)',
    color: '#0d0f12',
    cursor: 'pointer',
    flex: 1,
    justifyContent: 'center',
  },
  actionBtnSecondary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 20px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    border: '1px solid #2a2d35',
    fontFamily: 'inherit',
    background: '#14161a',
    color: '#f1f3f5',
    cursor: 'pointer',
    flex: 1,
    justifyContent: 'center',
  },
  meta: {
    background: '#14161a',
    borderRadius: 10,
    padding: 16,
  },
  metaRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #1a1d22',
    fontSize: 13,
  },
  metaLabel: { color: '#5c636a' },
  metaValue: { color: '#ced4da', fontWeight: 500 },
}
