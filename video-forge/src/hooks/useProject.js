import { useState, useCallback } from 'react'
import { sampleResearch, sampleStoryboard, sampleCharacters } from '../utils/mockData'

const PIPELINE_STEPS = [
  { id: 'topic', label: 'Topic & Prompt', icon: '✦' },
  { id: 'research', label: 'Research', icon: '◈' },
  { id: 'storyboard', label: 'Storyboard', icon: '▦' },
  { id: 'characters', label: 'Characters', icon: '◉' },
  { id: 'images', label: 'Image Gen', icon: '◐' },
  { id: 'video', label: 'Video Assembly', icon: '▶' },
]

export function useProject() {
  const [currentStep, setCurrentStep] = useState('topic')
  const [project, setProject] = useState({
    topic: '',
    description: '',
    format: 'short',
    style: 'cinematic',
    imageModel: 'nano-banana-pro',
  })
  const [research, setResearch] = useState([])
  const [storyboard, setStoryboard] = useState([])
  const [characters, setCharacters] = useState([])
  const [logs, setLogs] = useState([])
  const [generating, setGenerating] = useState(false)
  const [completedSteps, setCompletedSteps] = useState(new Set())

  const addLog = useCallback((type, message) => {
    setLogs(prev => [{
      id: Date.now(),
      type,
      message,
      time: new Date().toLocaleTimeString(),
    }, ...prev])
  }, [])

  const completeStep = useCallback((stepId) => {
    setCompletedSteps(prev => new Set([...prev, stepId]))
  }, [])

  const simulateDelay = (ms) => new Promise(r => setTimeout(r, ms))

  const startResearch = useCallback(async () => {
    if (!project.topic.trim()) return
    setGenerating(true)
    setCurrentStep('research')
    addLog('info', `Starting research on "${project.topic}"...`)
    completeStep('topic')

    await simulateDelay(1200)
    addLog('info', 'Querying Gemini 2.5 Pro for topic analysis...')
    await simulateDelay(1800)
    addLog('success', 'Topic analysis complete')
    await simulateDelay(800)
    addLog('info', 'Gathering audience insights...')
    await simulateDelay(1500)
    addLog('success', 'Audience research compiled')

    setResearch(sampleResearch)
    completeStep('research')
    setGenerating(false)
    addLog('success', 'Research phase complete — 4 sections generated')
  }, [project.topic, addLog, completeStep])

  const generateStoryboard = useCallback(async () => {
    setGenerating(true)
    setCurrentStep('storyboard')
    addLog('info', 'Generating storyboard from research...')

    await simulateDelay(1500)
    addLog('info', 'Building narrative structure...')
    await simulateDelay(2000)
    addLog('info', 'Creating scene descriptions and image prompts...')
    await simulateDelay(1200)

    setStoryboard(sampleStoryboard)
    completeStep('storyboard')
    setGenerating(false)
    addLog('success', `Storyboard generated — ${sampleStoryboard.length} scenes`)
  }, [addLog, completeStep])

  const generateCharacters = useCallback(async () => {
    setGenerating(true)
    setCurrentStep('characters')
    addLog('info', 'Designing character sheets...')

    await simulateDelay(1200)
    addLog('info', 'Defining character archetypes...')
    await simulateDelay(1500)
    addLog('info', 'Generating character prompts for Nano Banana Pro...')
    await simulateDelay(1000)

    setCharacters(sampleCharacters)
    completeStep('characters')
    setGenerating(false)
    addLog('success', `${sampleCharacters.length} character sheets created`)
  }, [addLog, completeStep])

  const generateImages = useCallback(async () => {
    setGenerating(true)
    setCurrentStep('images')
    addLog('info', `Starting image generation via ${project.imageModel}...`)

    const total = storyboard.length + characters.length
    for (let i = 0; i < storyboard.length; i++) {
      addLog('info', `Generating scene ${i + 1}/${storyboard.length}: "${storyboard[i].title}"...`)
      await simulateDelay(2000 + Math.random() * 1000)

      setStoryboard(prev => prev.map((s, idx) =>
        idx === i ? { ...s, status: 'generated', imageUrl: `https://picsum.photos/seed/scene${i}/800/450` } : s
      ))
      addLog('success', `Scene ${i + 1} image generated (${((i + 1) / total * 100).toFixed(0)}%)`)
    }

    for (let i = 0; i < characters.length; i++) {
      addLog('info', `Generating character "${characters[i].name}"...`)
      await simulateDelay(1800 + Math.random() * 800)
      setCharacters(prev => prev.map((c, idx) =>
        idx === i ? { ...c, imageUrl: `https://picsum.photos/seed/char${i}/400/400` } : c
      ))
      addLog('success', `Character ${i + 1} generated`)
    }

    completeStep('images')
    setGenerating(false)
    addLog('success', `All ${total} images generated via Nano Banana Pro`)
  }, [project.imageModel, storyboard, characters, addLog, completeStep])

  const assembleVideo = useCallback(async () => {
    setGenerating(true)
    setCurrentStep('video')
    addLog('info', 'Starting video assembly pipeline...')

    await simulateDelay(1500)
    addLog('info', 'Sequencing scenes...')
    await simulateDelay(2000)
    addLog('info', 'Adding transitions and motion...')
    await simulateDelay(1800)
    addLog('info', 'Rendering narration audio via Gemini...')
    await simulateDelay(2500)
    addLog('info', 'Compositing final output...')
    await simulateDelay(2000)
    addLog('info', 'Encoding to MP4 (H.264)...')
    await simulateDelay(1500)

    completeStep('video')
    setGenerating(false)
    addLog('success', '✦ Video assembled — ready for preview and export')
  }, [addLog, completeStep])

  const stepStatus = useCallback((stepId) => {
    if (completedSteps.has(stepId)) return 'completed'
    if (currentStep === stepId && generating) return 'active'
    if (currentStep === stepId) return 'active'
    return 'pending'
  }, [completedSteps, currentStep, generating])

  return {
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
  }
}
