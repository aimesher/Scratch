import { Sparkles, ArrowRight } from 'lucide-react'
import { videoFormats, imageModels } from '../utils/mockData'

export default function TopicForm({ project, setProject, onStart, generating }) {
  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Sparkles size={18} style={{ color: '#ffc107' }} />
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Start a New Video</h3>
        </div>
      </div>
      <div style={styles.body}>
        <div style={styles.inputGroup}>
          <label style={styles.label}>Topic / Subject</label>
          <input
            type="text"
            placeholder="e.g. The History of Brutalist Architecture"
            value={project.topic}
            onChange={e => setProject(p => ({ ...p, topic: e.target.value }))}
            style={styles.input}
          />
        </div>

        <div style={styles.inputGroup}>
          <label style={styles.label}>Description & Direction</label>
          <textarea
            placeholder="Describe the angle, mood, target audience, or any specific points to cover..."
            value={project.description}
            onChange={e => setProject(p => ({ ...p, description: e.target.value }))}
            style={styles.textarea}
            rows={4}
          />
        </div>

        <div style={styles.row}>
          <div style={{ flex: 1 }}>
            <label style={styles.label}>Format</label>
            <select
              value={project.format}
              onChange={e => setProject(p => ({ ...p, format: e.target.value }))}
              style={styles.select}
            >
              {videoFormats.map(f => (
                <option key={f.id} value={f.id}>
                  {f.label} — {f.aspect} ({f.platform})
                </option>
              ))}
            </select>
          </div>

          <div style={{ flex: 1 }}>
            <label style={styles.label}>Image Model</label>
            <select
              value={project.imageModel}
              onChange={e => setProject(p => ({ ...p, imageModel: e.target.value }))}
              style={styles.select}
            >
              {imageModels.map(m => (
                <option key={m.id} value={m.id}>{m.label} — {m.desc}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={styles.inputGroup}>
          <label style={styles.label}>Visual Style</label>
          <div style={styles.styleGrid}>
            {['Cinematic', 'Documentary', 'Animated', 'Editorial', 'Surreal', 'Minimal'].map(s => (
              <button
                key={s}
                onClick={() => setProject(p => ({ ...p, style: s.toLowerCase() }))}
                style={{
                  ...styles.styleBtn,
                  ...(project.style === s.toLowerCase() ? styles.styleBtnActive : {}),
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={onStart}
          disabled={!project.topic.trim() || generating}
          style={{
            ...styles.btn,
            opacity: !project.topic.trim() || generating ? 0.5 : 1,
            cursor: !project.topic.trim() || generating ? 'not-allowed' : 'pointer',
          }}
        >
          {generating ? (
            <>
              <div style={styles.spinner} />
              Processing...
            </>
          ) : (
            <>
              Start Research
              <ArrowRight size={16} />
            </>
          )}
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
  },
  body: { padding: 24 },
  inputGroup: { marginBottom: 20 },
  label: {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: '#868e96',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  input: {
    width: '100%',
    background: '#14161a',
    border: '1px solid #2a2d35',
    borderRadius: 6,
    padding: '11px 14px',
    color: '#f1f3f5',
    fontSize: 14,
    fontFamily: 'inherit',
    outline: 'none',
  },
  textarea: {
    width: '100%',
    background: '#14161a',
    border: '1px solid #2a2d35',
    borderRadius: 6,
    padding: '11px 14px',
    color: '#f1f3f5',
    fontSize: 14,
    fontFamily: 'inherit',
    outline: 'none',
    resize: 'vertical',
    minHeight: 100,
  },
  select: {
    width: '100%',
    background: '#14161a',
    border: '1px solid #2a2d35',
    borderRadius: 6,
    padding: '11px 14px',
    color: '#f1f3f5',
    fontSize: 14,
    fontFamily: 'inherit',
    outline: 'none',
    cursor: 'pointer',
  },
  row: {
    display: 'flex',
    gap: 16,
    marginBottom: 20,
  },
  styleGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
  },
  styleBtn: {
    padding: '7px 16px',
    fontSize: 12,
    fontWeight: 500,
    color: '#868e96',
    cursor: 'pointer',
    borderRadius: 6,
    border: '1px solid #2a2d35',
    background: '#14161a',
    fontFamily: 'inherit',
    transition: 'all 0.15s',
  },
  styleBtnActive: {
    background: '#ffc107',
    color: '#0d0f12',
    borderColor: '#ffc107',
    fontWeight: 600,
  },
  btn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 24px',
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    border: 'none',
    fontFamily: 'inherit',
    background: 'linear-gradient(135deg, #ffc107, #ffb300)',
    color: '#0d0f12',
    transition: 'all 0.15s',
    marginTop: 8,
    width: '100%',
    justifyContent: 'center',
  },
  spinner: {
    width: 16,
    height: 16,
    border: '2px solid rgba(0,0,0,0.2)',
    borderTopColor: '#0d0f12',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
}
