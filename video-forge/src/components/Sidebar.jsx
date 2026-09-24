import {
  Flame, LayoutDashboard, Wand2, Film, ImagePlus, Users,
  Settings, HelpCircle, Zap, BarChart3
} from 'lucide-react'

const navSections = [
  {
    label: 'Create',
    items: [
      { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { id: 'project', icon: Wand2, label: 'New Project' },
      { id: 'projects', icon: Film, label: 'My Projects' },
    ],
  },
  {
    label: 'Assets',
    items: [
      { id: 'images', icon: ImagePlus, label: 'Generated Images' },
      { id: 'characters', icon: Users, label: 'Character Library' },
    ],
  },
  {
    label: 'Account',
    items: [
      { id: 'usage', icon: BarChart3, label: 'Usage & Stats' },
      { id: 'settings', icon: Settings, label: 'Settings' },
      { id: 'help', icon: HelpCircle, label: 'Help & Docs' },
    ],
  },
]

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside style={styles.sidebar}>
      <div style={styles.logo}>
        <div style={styles.logoIcon}><Flame size={20} color="#0d0f12" /></div>
        <div>
          <h1 style={styles.logoText}>VideoForge</h1>
        </div>
        <span style={styles.proBadge}>PRO</span>
      </div>

      <nav style={styles.nav}>
        {navSections.map(section => (
          <div key={section.label} style={styles.section}>
            <div style={styles.sectionLabel}>{section.label}</div>
            {section.items.map(item => {
              const Icon = item.icon
              const isActive = activePage === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  style={{
                    ...styles.navItem,
                    ...(isActive ? styles.navItemActive : {}),
                  }}
                >
                  <Icon size={18} style={isActive ? { color: '#ffc107' } : {}} />
                  <span>{item.label}</span>
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      <div style={styles.footer}>
        <div style={styles.accountCard}>
          <div style={styles.accountEmail}>user@studio.ai</div>
          <div style={styles.accountPlan}>
            <div style={styles.activeDot} />
            <Zap size={13} />
            Google AI Pro
          </div>
        </div>
      </div>
    </aside>
  )
}

const styles = {
  sidebar: {
    width: 260,
    background: '#16191d',
    borderRight: '1px solid #2a2d35',
    display: 'flex',
    flexDirection: 'column',
    position: 'fixed',
    top: 0,
    left: 0,
    bottom: 0,
    zIndex: 100,
  },
  logo: {
    padding: '24px 20px',
    borderBottom: '1px solid #2a2d35',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  logoIcon: {
    width: 36,
    height: 36,
    background: 'linear-gradient(135deg, #ffc107, #ff5722)',
    borderRadius: 10,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    fontSize: 18,
    fontWeight: 700,
    letterSpacing: -0.3,
    color: '#f1f3f5',
  },
  proBadge: {
    fontSize: 10,
    background: '#ffc107',
    color: '#0d0f12',
    padding: '2px 8px',
    borderRadius: 4,
    fontWeight: 700,
    marginLeft: 'auto',
    letterSpacing: 0.5,
  },
  nav: {
    flex: 1,
    padding: '16px 12px',
    overflowY: 'auto',
  },
  section: {
    marginBottom: 24,
  },
  sectionLabel: {
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: 1.2,
    color: '#5c636a',
    padding: '0 8px',
    marginBottom: 8,
    fontWeight: 600,
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    borderRadius: 6,
    color: '#868e96',
    cursor: 'pointer',
    fontSize: 13.5,
    fontWeight: 500,
    border: 'none',
    background: 'none',
    width: '100%',
    textAlign: 'left',
    fontFamily: 'inherit',
    transition: 'all 0.15s',
  },
  navItemActive: {
    background: 'rgba(255, 193, 7, 0.15)',
    color: '#ffca28',
  },
  footer: {
    padding: 16,
    borderTop: '1px solid #2a2d35',
  },
  accountCard: {
    background: '#1a1d22',
    borderRadius: 10,
    padding: 14,
  },
  accountEmail: {
    fontSize: 12,
    color: '#868e96',
    marginBottom: 8,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  accountPlan: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 13,
    fontWeight: 600,
    color: '#ffca28',
  },
  activeDot: {
    width: 8,
    height: 8,
    background: '#66bb6a',
    borderRadius: '50%',
    animation: 'pulse 2s infinite',
  },
}
