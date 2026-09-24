import { BookOpen, ArrowRight, FileText } from 'lucide-react'

export default function ResearchPanel({ research, onNext, generating }) {
  if (research.length === 0) return null

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <BookOpen size={18} style={{ color: '#66bb6a' }} />
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Research Findings</h3>
        </div>
        <span style={styles.badge}>{research.length} sections</span>
      </div>
      <div style={styles.body}>
        {research.map((r, i) => (
          <div key={i} style={styles.finding}>
            <div style={styles.findingIcon}>
              <FileText size={14} />
            </div>
            <div style={{ flex: 1 }}>
              <h4 style={styles.findingTitle}>{r.title}</h4>
              <p style={styles.findingText}>{r.content}</p>
            </div>
          </div>
        ))}
        <button onClick={onNext} disabled={generating} style={{
          ...styles.btn,
          opacity: generating ? 0.5 : 1,
          cursor: generating ? 'not-allowed' : 'pointer',
        }}>
          {generating ? 'Generating...' : 'Generate Storyboard'}
          {!generating && <ArrowRight size={16} />}
        </button>
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
  badge: {
    display: 'inline-flex',
    padding: '3px 10px',
    borderRadius: 100,
    fontSize: 11,
    fontWeight: 600,
    background: 'rgba(76, 175, 80, 0.15)',
    color: '#66bb6a',
  },
  body: { padding: 24 },
  finding: {
    display: 'flex',
    gap: 14,
    padding: '14px 0',
    borderBottom: '1px solid #2a2d35',
  },
  findingIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: '#212529',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#868e96',
    flexShrink: 0,
    marginTop: 2,
  },
  findingTitle: {
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 4,
    color: '#f1f3f5',
  },
  findingText: {
    fontSize: 12,
    color: '#868e96',
    lineHeight: 1.5,
  },
  btn: {
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
    marginTop: 20,
    cursor: 'pointer',
  },
}
