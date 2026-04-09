import { useState, useEffect, useMemo } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'
import {
  fetchPostGrid,
  fetchCategories,
  fetchVisualFormats,
  submitAnnotationsBulk,
  type BulkAnnotationItem,
} from '@/lib/api'
import { useUrlState } from '@/hooks/useUrlState'

type GridItem = {
  ig_media_id: string
  shortcode: string | null
  media_type: string
  media_product_type: string
  split: string | null
  thumbnail_url: string | null
  category: string | null
  visual_format: string | null
  strategy: string | null
  annotation_category: string | null
  annotation_visual_format: string | null
  annotation_strategy: string | null
  annotation_doubtful: boolean
  is_annotated: boolean
}

type Lookup = { id: number; name: string }

const PAGE_SIZE = 20

type Props = {
  onOpenPost?: (igMediaId: string) => void
}

export function PostGrid({ onOpenPost }: Props) {
  const [items, setItems] = useState<GridItem[]>([])
  const [total, setTotal] = useState(0)
  // Filtres persistés en URL (préfixe "g_" pour éviter les collisions avec
  // d'autres vues qui pourraient aussi utiliser useUrlState)
  const [offset, setOffset] = useUrlState<number>('g_offset', 0, {
    serialize: (v) => String(v),
    deserialize: (raw) => {
      const n = parseInt(raw, 10)
      return Number.isFinite(n) && n >= 0 ? n : 0
    },
  })
  const [statusFilter, setStatusFilter] = useUrlState<string>('g_status', '')
  const [categoryFilter, setCategoryFilter] = useUrlState<string>('g_category', '')
  const [splitFilter, setSplitFilter] = useUrlState<string>('g_split', '')
  const [formatFilter, setFormatFilter] = useUrlState<string>('g_format', '')
  const [categories, setCategories] = useState<Lookup[]>([])
  const [visualFormats, setVisualFormats] = useState<Lookup[]>([])
  const [loading, setLoading] = useState(true)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [bulkMessage, setBulkMessage] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    fetchCategories().then(setCategories)
    fetchVisualFormats().then(setVisualFormats)
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchPostGrid({
      offset,
      limit: PAGE_SIZE,
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
      split: splitFilter || undefined,
      visual_format: formatFilter || undefined,
    }).then(data => {
      setItems(data.items)
      setTotal(data.total)
      setLoading(false)
    })
  }, [offset, statusFilter, categoryFilter, splitFilter, formatFilter, reloadToken])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  // Lookups name → id pour construire le payload bulk à partir des items visibles
  const categoryIdByName = useMemo(
    () => new Map(categories.map(c => [c.name, c.id])),
    [categories],
  )
  const visualFormatIdByName = useMemo(
    () => new Map(visualFormats.map(vf => [vf.name, vf.id])),
    [visualFormats],
  )

  // Items éligibles au bulk : non-annotés, heuristique complète, IDs résolvables
  const bulkCandidates: BulkAnnotationItem[] = useMemo(() => {
    const out: BulkAnnotationItem[] = []
    for (const it of items) {
      if (it.is_annotated) continue
      if (!it.category || !it.visual_format || !it.strategy) continue
      if (it.strategy !== 'Organic' && it.strategy !== 'Brand Content') continue
      const cat_id = categoryIdByName.get(it.category)
      const vf_id = visualFormatIdByName.get(it.visual_format)
      if (cat_id === undefined || vf_id === undefined) continue
      out.push({
        ig_media_id: it.ig_media_id,
        category_id: cat_id,
        visual_format_id: vf_id,
        strategy: it.strategy,
        doubtful: false,
      })
    }
    return out
  }, [items, categoryIdByName, visualFormatIdByName])

  const bulkCount = bulkCandidates.length
  const bulkSkipped = items.filter(it => !it.is_annotated).length - bulkCount

  const handleValidatePage = async () => {
    if (bulkCount === 0) return
    const ok = window.confirm(
      `Valider ${bulkCount} post${bulkCount > 1 ? 's' : ''} avec leurs heuristiques ?` +
        (bulkSkipped > 0
          ? `\n\n${bulkSkipped} post${bulkSkipped > 1 ? 's' : ''} ignoré${
              bulkSkipped > 1 ? 's' : ''
            } (heuristique incomplète).`
          : ''),
    )
    if (!ok) return
    setBulkLoading(true)
    setBulkMessage(null)
    try {
      const res = await submitAnnotationsBulk(bulkCandidates)
      setBulkMessage(`${res.count} post${res.count > 1 ? 's' : ''} annoté${res.count > 1 ? 's' : ''}`)
      setReloadToken(t => t + 1)
    } catch (err) {
      console.error('[bulk] failed', err)
      setBulkMessage(`Erreur: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBulkLoading(false)
      setTimeout(() => setBulkMessage(null), 4000)
    }
  }

  return (
    <div className="space-y-4">
      {/* Filtres */}
      <div className="flex items-center gap-3">
        <Select value={statusFilter || 'all'} onValueChange={v => {
          const next = v ?? ''
          setStatusFilter(next === 'all' ? '' : next)
          setOffset(0)
        }}>
          <SelectTrigger className="w-36 h-8 text-xs">
            {statusFilter === 'annotated' ? 'Annotés' : statusFilter === 'pending' ? 'En attente' : statusFilter === 'doubtful' ? 'Pas sûr' : 'Tous'}
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous</SelectItem>
            <SelectItem value="annotated">Annotés</SelectItem>
            <SelectItem value="pending">En attente</SelectItem>
            <SelectItem value="doubtful">Pas sur</SelectItem>
          </SelectContent>
        </Select>

        <Select value={categoryFilter || 'all'} onValueChange={v => {
          const next = v ?? ''
          setCategoryFilter(next === 'all' ? '' : next)
          setOffset(0)
        }}>
          <SelectTrigger className="w-44 h-8 text-xs">
            {categoryFilter || 'Toutes catégories'}
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes catégories</SelectItem>
            {categories.map(c => (
              <SelectItem key={c.id} value={c.name}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={splitFilter || 'all'} onValueChange={v => {
          const next = v ?? ''
          setSplitFilter(next === 'all' ? '' : next)
          setOffset(0)
        }}>
          <SelectTrigger className="w-28 h-8 text-xs">
            {splitFilter === 'test' ? 'Test' : splitFilter === 'dev' ? 'Dev' : 'Tous splits'}
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous splits</SelectItem>
            <SelectItem value="test">Test</SelectItem>
            <SelectItem value="dev">Dev</SelectItem>
          </SelectContent>
        </Select>

        <Select value={formatFilter || 'all'} onValueChange={v => {
          const next = v ?? ''
          setFormatFilter(next === 'all' ? '' : next)
          setOffset(0)
        }}>
          <SelectTrigger className="w-48 h-8 text-xs">
            {formatFilter || 'Tous formats'}
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous formats</SelectItem>
            {visualFormats.map(vf => (
              <SelectItem key={vf.id} value={vf.name}>{vf.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="ml-auto flex items-center gap-3">
          <span className="hidden text-xs text-neutral-400 md:inline">
            Cliquer sur un post pour l'ouvrir ou le réannoter
          </span>
          <span className="text-xs font-mono text-neutral-400 tabular-nums">
            {total} posts
          </span>
          <Button
            size="sm"
            onClick={handleValidatePage}
            disabled={bulkCount === 0 || bulkLoading}
            className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white disabled:bg-neutral-200 disabled:text-neutral-400"
            title={
              bulkCount === 0
                ? 'Aucun post à valider sur cette page'
                : `Annote ${bulkCount} post${bulkCount > 1 ? 's' : ''} non-annoté${
                    bulkCount > 1 ? 's' : ''
                  } avec leurs heuristiques`
            }
          >
            {bulkLoading
              ? 'Validation…'
              : `Valider ${bulkCount} post${bulkCount > 1 ? 's' : ''}`}
          </Button>
        </div>
      </div>

      {bulkMessage && (
        <div className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">
          {bulkMessage}
        </div>
      )}

      {/* Grille */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <div key={i} className="aspect-[4/5] bg-neutral-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {items.map(item => (
            <div
              key={item.ig_media_id}
              onClick={() => onOpenPost?.(item.ig_media_id)}
              className={`group relative rounded-lg overflow-hidden bg-neutral-100 ${onOpenPost ? 'cursor-pointer hover:ring-2 hover:ring-amber-300 transition-shadow' : ''}`}
            >
              {/* Image */}
              <div className="aspect-[4/5] relative">
                {item.thumbnail_url ? (
                  <img
                    src={item.thumbnail_url}
                    alt=""
                    className="w-full h-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                ) : (
                  <div className="w-full h-full bg-neutral-200 flex items-center justify-center text-neutral-400 text-xs">
                    ?
                  </div>
                )}

                {/* Overlay statut */}
                {item.is_annotated && (
                  <div className="absolute top-1.5 right-1.5">
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                      item.annotation_doubtful ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}>
                      {item.annotation_doubtful ? (
                        <span className="text-white text-[10px] font-bold">?</span>
                      ) : (
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                          <path d="M20 6L9 17l-5-5"/>
                        </svg>
                      )}
                    </div>
                  </div>
                )}

                {/* Badges type + split */}
                <div className="absolute bottom-1.5 left-1.5 flex gap-1">
                  <span className="text-[9px] font-mono uppercase bg-black/60 text-white px-1.5 py-0.5 rounded-full">
                    {item.media_product_type}
                  </span>
                  {item.split && (
                    <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full ${
                      item.split === 'test'
                        ? 'bg-amber-500/80 text-white'
                        : 'bg-blue-500/60 text-white'
                    }`}>
                      {item.split}
                    </span>
                  )}
                </div>
              </div>

              {/* Infos sous l'image */}
              <div className="p-2 bg-white">
                <div className="flex items-center gap-1 flex-wrap">
                  {item.is_annotated ? (
                    <>
                      <Badge variant="secondary" className="text-[9px] font-mono bg-emerald-50 text-emerald-700 hover:bg-emerald-50">
                        {item.annotation_category}
                      </Badge>
                      <Badge variant="outline" className="text-[9px] font-mono border-emerald-200 text-emerald-600 hover:bg-transparent">
                        {item.annotation_strategy}
                      </Badge>
                    </>
                  ) : (
                    <>
                      {item.category && (
                        <Badge variant="secondary" className="text-[9px] font-mono bg-neutral-100 text-neutral-500 hover:bg-neutral-100">
                          {item.category}
                        </Badge>
                      )}
                      {item.strategy && (
                        <Badge variant="outline" className="text-[9px] font-mono text-neutral-400 border-neutral-200 hover:bg-transparent">
                          {item.strategy}
                        </Badge>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            className="text-xs h-8"
          >
            &larr; Précédent
          </Button>
          <span className="text-xs font-mono text-neutral-500 tabular-nums">
            {currentPage} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={currentPage >= totalPages}
            className="text-xs h-8"
          >
            Suivant &rarr;
          </Button>
        </div>
      )}
    </div>
  )
}
