import { useState, useEffect, useRef } from 'react'

type Media = {
  media_url: string | null
  thumbnail_url: string | null
  media_type: string
  media_order: number
}

export function MediaViewer({ media }: { media: Media[] }) {
  const [index, setIndex] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    setIndex(0)
    setLoaded(false)
  }, [media])

  // Pause vidéo au changement de slide
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.currentTime = 0
    }
  }, [index])

  if (!media || media.length === 0) {
    return (
      <div className="flex items-center justify-center h-[40vh] bg-neutral-100 rounded-lg text-neutral-400 text-sm">
        Pas de média
      </div>
    )
  }

  const safeIndex = Math.min(index, media.length - 1)
  const item = media[safeIndex]
  if (!item) return null
  const isVideo = item.media_type === 'VIDEO'

  const navigate = (newIndex: number) => {
    setIndex(newIndex)
    setLoaded(false)
  }

  return (
    <div className="relative bg-black rounded-lg overflow-hidden group">
      {isVideo ? (
        // Lecteur vidéo natif
        <video
          ref={videoRef}
          src={item.media_url ?? undefined}
          poster={item.thumbnail_url ?? undefined}
          controls
          playsInline
          preload="metadata"
          className="w-full max-h-[65vh] object-contain"
          onLoadedData={() => setLoaded(true)}
        />
      ) : item.media_url ? (
        // Image
        <>
          {!loaded && (
            <div className="absolute inset-0 bg-neutral-900 animate-pulse" />
          )}
          <img
            src={item.media_url}
            alt={`Média ${index + 1}/${media.length}`}
            className={`w-full max-h-[65vh] object-contain transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
            loading="lazy"
            decoding="async"
            onLoad={() => setLoaded(true)}
          />
        </>
      ) : (
        <div className="flex items-center justify-center h-[40vh] bg-neutral-100 text-neutral-400 text-sm">
          Média non disponible
        </div>
      )}

      {/* Carousel */}
      {media.length > 1 && (
        <>
          <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1 z-10">
            {media.map((_, i) => (
              <button
                key={i}
                onClick={() => navigate(i)}
                className={`h-1.5 rounded-full transition-all duration-200 ${
                  i === index ? 'bg-white w-4' : 'bg-white/40 w-1.5 hover:bg-white/60'
                }`}
              />
            ))}
          </div>

          <button
            onClick={() => navigate(Math.max(0, index - 1))}
            disabled={index === 0}
            className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-0 hover:bg-black/60 z-10"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
          </button>
          <button
            onClick={() => navigate(Math.min(media.length - 1, index + 1))}
            disabled={index === media.length - 1}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/40 backdrop-blur-sm text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-0 hover:bg-black/60 z-10"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
          </button>

          <div className="absolute top-3 right-3 bg-black/50 backdrop-blur-sm text-white text-[10px] font-mono px-2 py-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity z-10">
            {index + 1}/{media.length}
          </div>
        </>
      )}
    </div>
  )
}
