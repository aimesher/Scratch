import { Check, Loader2 } from 'lucide-react'

export default function Pipeline({ steps, stepStatus, currentStep, onStepClick }) {
  return (
    <div style={styles.container}>
      <div style={styles.steps}>
        {steps.map((step, idx) => {
          const status = stepStatus(step.id)
          return (
            <div key={step.id} style={styles.stepWrapper}>
              {idx > 0 && (
                <div style={{
                  ...styles.connector,
                  background: status === 'completed' || stepStatus(steps[idx - 1].id) === 'completed'
                    ? '#66bb6a' : '#2a2d35',
                }} />
              )}
              <button
                onClick={() => onStepClick(step.id)}
                style={{
                  ...styles.stepContent,
                  ...(status === 'active' ? styles.active : {}),
                  ...(status === 'completed' ? styles.completed : {}),
                }}
              >
                <div style={{
                  ...styles.icon,
                  ...(status === 'active' ? styles.iconActive : {}),
                  ...(status === 'completed' ? styles.iconCompleted : {}),
                }}>
                  {status === 'completed' ? (
                    <Check size={14} />
                  ) : status === 'active' ? (
                    <span style={{ fontSize: 14 }}>{step.icon}</span>
                  ) : (
                    <span style={{ fontSize: 14, color: '#5c636a' }}>{step.icon}</span>
                  )}
                </div>
                <div style={styles.info}>
                  <div style={{
                    ...styles.label,
                    color: status === 'active' ? '#f1f3f5' :
                           status === 'completed' ? '#f1f3f5' : '#868e96',
                  }}>
                    {step.label}
                  </div>
                  <div style={{
                    ...styles.status,
                    color: status === 'active' ? '#ffca28' :
                           status === 'completed' ? '#66bb6a' : '#5c636a',
                  }}>
                    {status === 'active' ? 'In Progress' :
                     status === 'completed' ? 'Done' : 'Pending'}
                  </div>
                </div>
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const styles = {
  container: { marginBottom: 32 },
  steps: {
    display: 'flex',
    alignItems: 'center',
    overflowX: 'auto',
    padding: '4px 0',
  },
  stepWrapper: {
    display: 'flex',
    alignItems: 'center',
    flexShrink: 0,
  },
  connector: {
    width: 32,
    height: 2,
    background: '#2a2d35',
    flexShrink: 0,
  },
  stepContent: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '12px 18px',
    borderRadius: 10,
    border: '1px solid #2a2d35',
    background: '#1a1d22',
    cursor: 'pointer',
    transition: 'all 0.2s',
    minWidth: 155,
    fontFamily: 'inherit',
    textAlign: 'left',
    color: 'inherit',
  },
  active: {
    borderColor: '#ffc107',
    background: 'rgba(255, 193, 7, 0.15)',
    boxShadow: '0 0 20px rgba(255, 193, 7, 0.1)',
  },
  completed: {
    borderColor: '#66bb6a',
    background: 'rgba(76, 175, 80, 0.08)',
  },
  icon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    background: '#212529',
    color: '#5c636a',
  },
  iconActive: {
    background: '#ffc107',
    color: '#0d0f12',
  },
  iconCompleted: {
    background: '#4caf50',
    color: 'white',
  },
  info: {
    display: 'flex',
    flexDirection: 'column',
  },
  label: {
    fontSize: 13,
    fontWeight: 600,
  },
  status: {
    fontSize: 11,
  },
}
