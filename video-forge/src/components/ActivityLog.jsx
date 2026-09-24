export default function ActivityLog({ logs }) {
  if (logs.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.3 }}>◈</div>
        <div style={{ fontSize: 13, color: '#5c636a' }}>Activity will appear here</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {logs.map(log => (
        <div key={log.id} style={styles.entry}>
          <div style={{
            ...styles.dot,
            background: log.type === 'success' ? '#66bb6a' :
                         log.type === 'error' ? '#ef5350' :
                         log.type === 'info' ? '#ffc107' : '#868e96',
          }} />
          <div style={{ flex: 1 }}>
            <div style={styles.text}>{log.message}</div>
            <div style={styles.time}>{log.time}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

const styles = {
  container: {
    maxHeight: 420,
    overflowY: 'auto',
  },
  empty: {
    textAlign: 'center',
    padding: '40px 20px',
  },
  entry: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 12,
    padding: '10px 0',
    borderBottom: '1px solid #2a2d35',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    marginTop: 5,
    flexShrink: 0,
  },
  text: {
    fontSize: 13,
    color: '#ced4da',
    lineHeight: 1.5,
  },
  time: {
    fontSize: 11,
    color: '#5c636a',
    marginTop: 2,
  },
}
