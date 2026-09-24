import { useState } from 'react'
import { Bell, Search, Plus, ArrowRight } from 'lucide-react'
import Sidebar from './components/Sidebar'
import StatsBar from './components/StatsBar'
import Pipeline from './components/Pipeline'
import TopicForm from './components/TopicForm'
import ResearchPanel from './components/ResearchPanel'
import StoryboardView from './components/StoryboardView'
import CharacterSheets from './components/CharacterSheets'
import VideoPreview from './components/VideoPreview'
import ActivityLog from './components/ActivityLog'
import { useProject } from './hooks/useProject'

export default function App() {
  const [activePage, setActivePage] = useState('project')
  const {
    PIPELINE_STEPS,
    currentStep,
    setCurrentStep,
    project,
    setProject,
    research,
    storyboard,
    characters,
    logs,
    generating,
    completedSteps,
    stepStatus,
    startResearch,
    generateStoryboard,
    generateCharacters,
    generateImages,
    assembleVideo,
  } = useProject()

  return (
    <div style={styles.layout}>
      <Sidebar activePage={activePage} onNavigate={setActivePage} />

      <main style={styles.main}>
        {/* Top bar */}
        <div style={styles.topBar}>
          <h2 style={styles.topTitle}>
            {activePage === 'project' ? '✦ New Video Project' :
             activePage === 'dashboard' ? 'Dashboard' :
             activePage === 'usage' ? 'Usage & Statistics' :
             activePage === 'projects' ? 'My Projects' :
             activePage === 'images' ? 'Generated Images' :
             activePage === 'characters' ? 'Character Library' :
             activePage === 'settings' ? 'Settings' : 'VideoForge'}
          </h2>
          <div style={styles.topActions}>
            <button style={styles.iconBtn}>
              <Search size={18} />
            </button>
            <button style={styles.iconBtn}>
              <Bell size={18} />
            </button>
            <button style={styles.newBtn} onClick={() => setActivePage('project')}>
              <Plus size={16} />
              New Project
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={styles.content}>
          {activePage === 'dashboard' && <DashboardPage onStart={() => setActivePage('project')} />}
          {activePage === 'usage' && <UsagePage />}
          {activePage === 'project' && (
            <>
              <StatsBar />

              <Pipeline
                steps={PIPELINE_STEPS}
                stepStatus={stepStatus}
                currentStep={currentStep}
                onStepClick={setCurrentStep}
              />

              <div style={styles.twoCol}>
                <div style={styles.mainCol}>
                  {(currentStep === 'topic' || !completedSteps.has('topic')) && (
                    <TopicForm
                      project={project}
                      setProject={setProject}
                      onStart={startResearch}
                      generating={generating}
                    />
                  )}

                  {research.length > 0 && (
                    <div style={{ marginTop: 24 }}>
                      <ResearchPanel
                        research={research}
                        onNext={generateStoryboard}
                        generating={generating}
                      />
                    </div>
                  )}

                  {storyboard.length > 0 && (
                    <div style={{ marginTop: 24 }}>
                      <StoryboardView
                        storyboard={storyboard}
                        onNext={generateCharacters}
                        generating={generating}
                      />
                    </div>
                  )}

                  {characters.length > 0 && (
                    <div style={{ marginTop: 24 }}>
                      <CharacterSheets
                        characters={characters}
                        onNext={generateImages}
                        generating={generating}
                      />
                    </div>
                  )}

                  {completedSteps.has('images') && !completedSteps.has('video') && (
                    <div style={{ marginTop: 24 }}>
                      <div style={styles.assembleCard}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                          <span style={{ fontSize: 20 }}>▶</span>
                          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Ready to Assemble</h3>
                        </div>
                        <p style={{ fontSize: 13, color: '#868e96', marginBottom: 16, lineHeight: 1.6 }}>
                          All images generated. Assemble into a video with transitions, narration, and background music via Gemini.
                        </p>
                        <button
                          onClick={assembleVideo}
                          disabled={generating}
                          style={{
                            ...styles.assembleBtn,
                            opacity: generating ? 0.5 : 1,
                            cursor: generating ? 'not-allowed' : 'pointer',
                          }}
                        >
                          {generating ? (
                            <>
                              <div style={styles.spinner} />
                              Assembling Video...
                            </>
                          ) : (
                            <>
                              Assemble Video
                              <ArrowRight size={16} />
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )}

                  {completedSteps.has('video') && (
                    <div style={{ marginTop: 24 }}>
                      <VideoPreview completedSteps={completedSteps} />
                    </div>
                  )}
                </div>

                <div style={styles.sideCol}>
                  <div style={styles.logCard}>
                    <div style={styles.logHeader}>
                      <h3 style={{ fontSize: 14, fontWeight: 600 }}>Activity Log</h3>
                      <span style={{ fontSize: 11, color: '#5c636a' }}>
                        {logs.length} events
                      </span>
                    </div>
                    <div style={styles.logBody}>
                      <ActivityLog logs={logs} />
                    </div>
                  </div>

                  {/* Model info card */}
                  <div style={styles.modelCard}>
                    <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#f1f3f5' }}>
                      Active Models
                    </h4>
                    <div style={styles.modelRow}>
                      <div style={styles.modelDot('#ffc107')} />
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>Gemini 2.5 Pro</div>
                        <div style={{ fontSize: 11, color: '#5c636a' }}>Research & Storyboard</div>
                      </div>
                    </div>
                    <div style={styles.modelRow}>
                      <div style={styles.modelDot('#ff7043')} />
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>Nano Banana Pro</div>
                        <div style={{ fontSize: 11, color: '#5c636a' }}>Image Generation</div>
                      </div>
                    </div>
                    <div style={styles.modelRow}>
                      <div style={styles.modelDot('#66bb6a')} />
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>Gemini Audio</div>
                        <div style={{ fontSize: 11, color: '#5c636a' }}>Narration & Voice</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {activePage !== 'project' && activePage !== 'dashboard' && activePage !== 'usage' && (
            <div style={styles.emptyState}>
              <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.2 }}>◈</div>
              <h4 style={{ fontSize: 16, color: '#868e96', marginBottom: 8 }}>
                {activePage === 'projects' ? 'No projects yet' :
                 activePage === 'images' ? 'No generated images' :
                 activePage === 'characters' ? 'No characters saved' :
                 'Coming soon'}
              </h4>
              <p style={{ fontSize: 13, color: '#5c636a', maxWidth: 360, margin: '0 auto' }}>
                Start a new project to begin generating videos with AI.
              </p>
              <button style={{ ...styles.newBtn, marginTop: 20 }} onClick={() => setActivePage('project')}>
                <Plus size={16} />
                New Project
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function DashboardPage({ onStart }) {
  return (
    <>
      <StatsBar />
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: 20,
      }}>
        <div style={styles.dashCard}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Quick Start</h3>
          <p style={{ fontSize: 13, color: '#868e96', marginBottom: 20, lineHeight: 1.6 }}>
            Create a full video from a topic. AI handles research, storyboarding, character design, image generation, and final assembly.
          </p>
          <button style={styles.newBtn} onClick={onStart}>
            <Plus size={16} />
            New Project
          </button>
        </div>
        <div style={styles.dashCard}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Recent Activity</h3>
          <p style={{ fontSize: 13, color: '#5c636a', lineHeight: 1.6 }}>
            No recent projects. Start your first video project to see activity here.
          </p>
        </div>
        <div style={styles.dashCard}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Platform Status</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#66bb6a' }} />
            <span style={{ fontSize: 13, color: '#66bb6a' }}>All systems operational</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#66bb6a' }} />
            <span style={{ fontSize: 13, color: '#868e96' }}>Google AI API — Connected</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#66bb6a' }} />
            <span style={{ fontSize: 13, color: '#868e96' }}>Nano Banana Pro — Online</span>
          </div>
        </div>
      </div>
    </>
  )
}

function UsagePage() {
  return (
    <>
      <StatsBar />
      <div style={styles.usageCard}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Billing & Plan</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, color: '#5c636a', marginBottom: 4 }}>Current Plan</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#ffca28' }}>Google AI Pro</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#5c636a', marginBottom: 4 }}>Billing Cycle</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#f1f3f5' }}>Sep 1 – Sep 30, 2026</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#5c636a', marginBottom: 4 }}>Monthly Spend</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#f1f3f5' }}>$29.00</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#5c636a', marginBottom: 4 }}>Status</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#66bb6a' }} />
              <span style={{ fontSize: 14, fontWeight: 500, color: '#66bb6a' }}>Active</span>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

const styles = {
  layout: {
    display: 'flex',
    minHeight: '100vh',
  },
  main: {
    flex: 1,
    marginLeft: 260,
    minHeight: '100vh',
  },
  topBar: {
    height: 60,
    borderBottom: '1px solid #2a2d35',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 32px',
    background: '#16191d',
    position: 'sticky',
    top: 0,
    zIndex: 50,
  },
  topTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: '#f1f3f5',
  },
  topActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  iconBtn: {
    width: 36,
    height: 36,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 6,
    border: '1px solid #2a2d35',
    background: 'transparent',
    color: '#868e96',
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  newBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    border: 'none',
    fontFamily: 'inherit',
    background: 'linear-gradient(135deg, #ffc107, #ffb300)',
    color: '#0d0f12',
    cursor: 'pointer',
  },
  content: {
    padding: 32,
    maxWidth: 1400,
  },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 360px',
    gap: 24,
    alignItems: 'start',
  },
  mainCol: {},
  sideCol: {
    position: 'sticky',
    top: 92,
  },
  logCard: {
    background: '#1a1d22',
    border: '1px solid #2a2d35',
    borderRadius: 14,
    overflow: 'hidden',
  },
  logHeader: {
    padding: '16px 20px',
    borderBottom: '1px solid #2a2d35',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logBody: {
    padding: '0 20px 16px',
  },
  modelCard: {
    background: '#1a1d22',
    border: '1px solid #2a2d35',
    borderRadius: 14,
    padding: 20,
    marginTop: 16,
  },
  modelRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 0',
    borderBottom: '1px solid #2a2d35',
  },
  modelDot: (color) => ({
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: color,
    flexShrink: 0,
  }),
  assembleCard: {
    background: '#1a1d22',
    border: '1px solid rgba(255,193,7,0.2)',
    borderRadius: 14,
    padding: 24,
    background: 'linear-gradient(135deg, rgba(255,193,7,0.06), transparent)',
  },
  assembleBtn: {
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
  emptyState: {
    textAlign: 'center',
    padding: '80px 20px',
  },
  dashCard: {
    background: '#1a1d22',
    border: '1px solid #2a2d35',
    borderRadius: 14,
    padding: 24,
  },
  usageCard: {
    background: '#1a1d22',
    border: '1px solid #2a2d35',
    borderRadius: 14,
    padding: 24,
  },
}
