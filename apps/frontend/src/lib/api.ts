const API_BASE = 'http://localhost:8000/v1'

export async function fetchNextPost(annotator = 'mathias') {
  const res = await fetch(`${API_BASE}/posts/next?annotator=${annotator}`)
  return res.json()
}

export async function fetchProgress(annotator = 'mathias') {
  const res = await fetch(`${API_BASE}/posts/progress?annotator=${annotator}`)
  return res.json()
}

export async function fetchCategories() {
  const res = await fetch(`${API_BASE}/posts/categories`)
  return res.json()
}

export async function fetchVisualFormats() {
  const res = await fetch(`${API_BASE}/posts/visual-formats`)
  return res.json()
}

export async function fetchPostGrid(params: {
  offset?: number
  limit?: number
  status?: string
  category?: string
  annotator?: string
} = {}) {
  const qs = new URLSearchParams()
  if (params.offset) qs.set('offset', String(params.offset))
  if (params.limit) qs.set('limit', String(params.limit))
  if (params.status) qs.set('status', params.status)
  if (params.category) qs.set('category', params.category)
  qs.set('annotator', params.annotator ?? 'mathias')
  const res = await fetch(`${API_BASE}/posts/?${qs}`)
  return res.json()
}

export async function submitAnnotation(data: {
  ig_media_id: number
  category_id: number
  visual_format_id: number
  strategy: 'Organic' | 'Brand Content'
}, annotator = 'mathias') {
  const res = await fetch(`${API_BASE}/annotations/?annotator=${annotator}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return res.json()
}
