import { useState, useEffect } from 'react'

type Media = {
  media_url: string | null
  thumbnail_url: string | null
  media_type: string
  media_order: number
}

export function MediaViewer({ media }: { media: Media[] }) {
  const [index, setIndex] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    setIndex(0)
    setLoaded(false)
  }, [media])

  if (media.length === 0) {
    return (
      <div className="flex items-center justify-center h-[40vh] bg-neutral-100 rounded-lg text-neutral-400 text-sm">
        Pas de média
      </div>
    )
  }

  const item = media[index]
  const url = item.media_type === 'VIDEO' ? item.thumbnail_url : item.media_url

  return (
    <div className="relative bg-black rounded-lg overflow-hidden group">
      {url ? (
        <>
          {!loaded && (
            <div className="absolute inset-0 bg-neutral-900 animate-pulse" />
          )}
          <img
            src={url}
            alt={`Média ${index + 1}/${media.length}`}
            className={`w-full max-h-[65vh] object-contain transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
            loading="lazy"
            decoding="async"
            onLoad={() => setLoaded(true)}
          />
          {item.media_type === 'VIDEO' && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                <div className="w-0 h-0 border-l-[16px] border-l-white border-y-[10px] border-y-transparent ml-1" />
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="flex items-center justify-center h-[40vh] bg-neutral-100 text-neutral-400 text-sm">
          Média non disponible
        </div>
      )}

      {/* Carousel indicators */}
      {media.length > 1 && (
        <>
          <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1">
            {media.map((_, i) => (
              <button
                key={i}
                onClick={() => { setIndex(i); setLoaded(false) }}
                className={`h-1.5 rounded-full transition-all duration-200 ${
                  i === index ? 'bg-white w-4' : 'bg-white/40 w-1.5 hover:bg-white/60'
                }`}
              />
            ))}
          </div>

          {/* Arrow navigation */}
          <button
            onClick={() => { setIndex(i => Math.max(0, i - 1)); setLoaded(false) }}
            disabled={index === 0}
            className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-0 hover:bg-black/60"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
          </button>
          <button
            onClick={() => { setIndex(i => Math.min(media.length - 1, i + 1)); setLoaded(false) }}
            disabled={index === media.length - 1}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-0 hover:bg-black/60"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
          </button>

          {/* Counter */}
          <div className="absolute top-3 right-3 bg-black/50 backdrop-blur-sm text-white text-[10px] font-mono px-2 py-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
            {index + 1}/{media.length}
          </div>
        </>
      )}
    </div>
  )
}
