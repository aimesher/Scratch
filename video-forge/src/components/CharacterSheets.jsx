import { Users, ArrowRight, Palette } from 'lucide-react'

export default function CharacterSheets({ characters, onNext, generating }) {
  if (characters.length === 0) return null

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Users size={18} style={{ color: '#ff7043' }} />
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Character Sheets</h3>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={styles.badge}>{characters.length} characters</span>
          <button onClick={onNext} disabled={generating} style={{
            ...styles.btn,
            opacity: generating ? 0.5 : 1,
            cursor: generating ? 'not-allowed' : 'pointer',
          }}>
            {generating ? 'Generating...' : 'Generate All Images'}
            {!generating && <ArrowRight size={14} />}
          </button>
        </div>
      </div>
      <div style={styles.grid}>
        {characters.map(char => (
          <div key={char.id} style={styles.charCard}>
            <div style={styles.avatar}>
              {char.imageUrl ? (
                <img src={char.imageUrl} alt={char.name} style={styles.avatarImg} />
              ) : (
                <div style={styles.avatarPlaceholder}>
                  <Palette size={32} style={{ opacity: 0.2 }} />
                </div>
              )}
            </div>
            <div style={styles.info}>
              <h4 style={styles.name}>{char.name}</h4>
              <div style={styles.role}>{char.role}</div>
              <p style={styles.desc}>{char.description}</p>
              <div style={styles.traits}>
                {char.traits.map(t => (
                  <span key={t} style={styles.trait}>{t}</span>
                ))}
              </div>
              <div style={styles.prompt}>
                <span style={{ color: '#5c636a', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Nano Banana Pro Prompt:
                </span>
                <br />
                {char.prompt}
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
    padding: '5px 12px',
    borderRadius: 100,
    fontSize: 11,
    fontWeight: 600,
    background: 'rgba(255, 112, 67, 0.15)',
    color: '#ff7043',
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
    cursor: 'pointer',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
    gap: 16,
    padding: 24,
  },
  charCard: {
    background: '#14161a',
    border: '1px solid #2a2d35',
    borderRadius: 10,
    overflow: 'hidden',
    transition: 'all 0.2s',
  },
  avatar: {
    width: '100%',
    aspectRatio: '1',
    background: 'linear-gradient(135deg, #212529, #343a40)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarImg: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
  avatarPlaceholder: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#5c636a',
  },
  info: { padding: 16 },
  name: {
    fontSize: 14,
    fontWeight: 600,
    marginBottom: 4,
    color: '#f1f3f5',
  },
  role: {
    fontSize: 12,
    color: '#ffca28',
    fontWeight: 500,
    marginBottom: 8,
  },
  desc: {
    fontSize: 12,
    color: '#868e96',
    lineHeight: 1.5,
    marginBottom: 10,
  },
  traits: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  trait: {
    padding: '3px 10px',
    borderRadius: 100,
    fontSize: 10,
    fontWeight: 600,
    background: 'rgba(255,193,7,0.1)',
    color: '#ffca28',
  },
  prompt: {
    padding: '8px 10px',
    background: '#0d0f12',
    borderRadius: 6,
    fontSize: 11,
    color: '#5c636a',
    fontStyle: 'italic',
    lineHeight: 1.5,
  },
}
