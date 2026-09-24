// Simulated Google AI Pro account stats
export const accountStats = {
  plan: 'Google AI Pro',
  email: 'user@studio.ai',
  apiCalls: { used: 1847, limit: 5000, label: 'API Calls' },
  tokens: { used: 2_340_000, limit: 10_000_000, label: 'Tokens' },
  imageCredits: { used: 312, limit: 1000, label: 'Image Credits' },
  videoMinutes: { used: 42, limit: 120, label: 'Video Minutes' },
  billingCycle: 'Sep 1 – Sep 30, 2026',
  monthlySpend: '$29.00',
  status: 'active',
}

export const sampleResearch = [
  { title: 'Core concept overview', content: 'Detailed research findings on the topic covering history, current trends, and key perspectives.' },
  { title: 'Target audience insights', content: 'Demographics, preferences, and engagement patterns for maximum impact.' },
  { title: 'Visual style references', content: 'Moodboard-ready references: cinematic lighting, color grading approaches, and compositional styles.' },
  { title: 'Narrative structure', content: 'Three-act structure adapted for short-form: hook (0-3s), develop (3-45s), payoff (45-60s).' },
]

export const sampleStoryboard = [
  {
    id: 1,
    title: 'Opening Hook',
    description: 'Wide establishing shot fading in from black. Text overlay introduces the topic with kinetic typography.',
    duration: '0:00 – 0:05',
    prompt: 'Cinematic wide shot, dramatic lighting, dark atmosphere, golden hour rays breaking through clouds, 8k photorealistic',
    imageUrl: null,
    status: 'pending',
  },
  {
    id: 2,
    title: 'Context Setup',
    description: 'Montage of relevant imagery establishing the world and setting. Camera slowly pushes in.',
    duration: '0:05 – 0:15',
    prompt: 'Detailed close-up montage, shallow depth of field, warm amber tones, professional documentary style, ultra detailed',
    imageUrl: null,
    status: 'pending',
  },
  {
    id: 3,
    title: 'Key Point 1',
    description: 'First major revelation or argument. Split-screen comparison with before/after or cause/effect.',
    duration: '0:15 – 0:25',
    prompt: 'Split composition, dramatic contrast, editorial photography style, clean modern aesthetic, high detail',
    imageUrl: null,
    status: 'pending',
  },
  {
    id: 4,
    title: 'Key Point 2',
    description: 'Second supporting argument with visual metaphor. Dynamic camera movement suggests energy.',
    duration: '0:25 – 0:35',
    prompt: 'Dynamic perspective, motion blur effect, vibrant saturated colors, professional cinematography, photorealistic',
    imageUrl: null,
    status: 'pending',
  },
  {
    id: 5,
    title: 'Climax',
    description: 'The big reveal or transformation moment. Visual crescendo with rapid cuts and building intensity.',
    duration: '0:35 – 0:48',
    prompt: 'Epic dramatic moment, volumetric lighting, cinematic color grading, anamorphic lens flare, 8k resolution',
    imageUrl: null,
    status: 'pending',
  },
  {
    id: 6,
    title: 'Resolution & CTA',
    description: 'Calm denouement. Logo/channel branding with subscribe call-to-action. Fade to styled end card.',
    duration: '0:48 – 1:00',
    prompt: 'Clean minimal end card, elegant typography, dark background with golden accents, professional branding',
    imageUrl: null,
    status: 'pending',
  },
]

export const sampleCharacters = [
  {
    id: 1,
    name: 'The Narrator',
    role: 'Primary Voice',
    description: 'Authoritative yet warm presence guiding the viewer through the story.',
    traits: ['Confident', 'Knowledgeable', 'Approachable'],
    prompt: 'Professional narrator portrait, warm studio lighting, clean background, confident expression, photorealistic',
  },
  {
    id: 2,
    name: 'The Expert',
    role: 'Subject Authority',
    description: 'Domain specialist providing credibility and depth to the narrative.',
    traits: ['Analytical', 'Precise', 'Trustworthy'],
    prompt: 'Expert portrait with office background, scholarly atmosphere, soft directional light, realistic detailed face',
  },
  {
    id: 3,
    name: 'The Audience Avatar',
    role: 'Relatable Figure',
    description: 'Represents the viewer — discovers and reacts to information alongside them.',
    traits: ['Curious', 'Expressive', 'Genuine'],
    prompt: 'Candid portrait, natural lighting, casual setting, genuine curious expression, lifestyle photography style',
  },
]

export const videoFormats = [
  { id: 'short', label: 'Short (< 60s)', aspect: '9:16', platform: 'Reels / Shorts / TikTok' },
  { id: 'standard', label: 'Standard (2-5 min)', aspect: '16:9', platform: 'YouTube' },
  { id: 'long', label: 'Long (5-15 min)', aspect: '16:9', platform: 'YouTube / Vimeo' },
]

export const imageModels = [
  { id: 'imagen-3', label: 'Imagen 3', desc: 'Google highest quality' },
  { id: 'nano-banana-pro', label: 'Nano Banana Pro', desc: 'Fast, stylized output' },
  { id: 'gemini-image', label: 'Gemini Native', desc: 'Built-in image gen' },
]
