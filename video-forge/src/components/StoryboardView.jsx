import { Film, ArrowRight, Clock, Hash } from 'lucide-react'

export default function StoryboardView({ storyboard, onNext, generating }) {
  if (storyboard.length === 0) return null

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Film size={18} style={{ color: '#ffca28' }} />
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Storyboard</h3>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={styles.badge}>{storyboard.length} scenes</span>
          <button onClick={onNext} disabled={generating} style={{
            ...styles.btn,
            opacity: generating ? 0.5 : 1,
            cursor: generating ? 'not-allowed' : 'pointer',
          }}>
            {generating ? 'Generating...' : 'Generate Characters'}
            {!generating && <ArrowRight size={14} />}
          </button>
        </div>
      </div>
      <div style={styles.grid}>
        {storyboard.map(scene => (
          <div key={scene.id} style={styles.scene}>
            <div style={styles.sceneImage}>
              {scene.imageUrl ? (
                <img src={scene.imageUrl} alt={scene.title} style={styles.img} />
              ) : (
                <div style={styles.placeholder}>
                  <Film size={24} style={{ opacity: 0.3 }} />
                </div>
              )}
              <div style={styles.sceneNumber}>
                <Hash size={10} /> {scene.id}
              </div>
              <div style={styles.sceneDuration}>
                <Clock size={10} /> {scene.duration}
              </div>
              {scene.status === 'generated' && (
                <div style={styles.genBadge}>✓ Generated</div>
              )}
            </div>
            <div style={styles.sceneDetails}>
              <h4 style={styles.sceneTitle}>{scene.title}</h4>
              <p style={styles.sceneDesc}>{scene.description}</p>
              <div style={styles.scenePrompt}>
                <span style={{ color: '#5c636a', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>Prompt:</span>
                <br />
                {scene.prompt}
              </div>
            </div>
          </div>
        ))}
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
    flexWrap: 'wrap',
    gap: 12,
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '5px 12px',
    borderRadius: 100,
    fontSize: 11,
    fontWeight: 600,
    background: 'rgba(255, 193, 7, 0.15)',
    color: '#ffca28',
  },
  btn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '7px 16px',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    border: 'none',
    fontFamily: 'inherit',
    background: 'linear-gradient(135deg, #ffc107, #ffb300)',
    color: '#0d0f12',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: 16,
    padding: 24,
  },
  scene: {
    background: '#14161a',
    border: '1px solid #2a2d35',
    borderRadius: 10,
    overflow: 'hidden',
    transition: 'all 0.2s',
  },
  sceneImage: {
    width: '100%',
    aspectRatio: '16/9',
    background: '#0d0f12',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    overflow: 'hidden',
  },
  img: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  placeholder: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#5c636a',
  },
  sceneNumber: {
    position: 'absolute',
    top: 10,
    left: 10,
    background: 'rgba(0,0,0,0.75)',
    color: '#ffca28',
    padding: '3px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    gap: 3,
  },
  sceneDuration: {
    position: 'absolute',
    bottom: 10,
    right: 10,
    background: 'rgba(0,0,0,0.75)',
    color: '#f1f3f5',
    padding: '3px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 500,
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  genBadge: {
    position: 'absolute',
    top: 10,
    right: 10,
    background: 'rgba(76,175,80,0.9)',
    color: 'white',
    padding: '3px 8px',
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 600,
  },
  sceneDetails: { padding: 14 },
  sceneTitle: {
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 6,
    color: '#f1f3f5',
  },
  sceneDesc: {
    fontSize: 12,
    color: '#868e96',
    lineHeight: 1.5,
    marginBottom: 8,
  },
  scenePrompt: {
    padding: '8px 10px',
    background: '#0d0f12',
    borderRadius: 6,
    fontSize: 11,
    color: '#5c636a',
    fontStyle: 'italic',
    lineHeight: 1.5,
  },
}
