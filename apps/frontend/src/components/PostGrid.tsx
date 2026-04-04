import { useState, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'
import { fetchPostGrid, fetchCategories } from '@/lib/api'

type GridItem = {
  ig_media_id: number
  shortcode: string | null
  media_type: string
  media_product_type: string
  thumbnail_url: string | null
  category: string | null
  visual_format: string | null
  strategy: string | null
  annotation_category: string | null
  annotation_visual_format: string | null
  annotation_strategy: string | null
  is_annotated: boolean
}

type Lookup = { id: number; name: string }

const PAGE_SIZE = 50

export function PostGrid() {
  const [items, setItems] = useState<GridItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [categories, setCategories] = useState<Lookup[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchCategories().then(setCategories)
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchPostGrid({
      offset,
      limit: PAGE_SIZE,
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
    }).then(data => {
      setItems(data.items)
      setTotal(data.total)
      setLoading(false)
    })
  }, [offset, statusFilter, categoryFilter])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="space-y-4">
      {/* Filtres */}
      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={v => { setStatusFilter(v === 'all' ? '' : v); setOffset(0) }}>
          <SelectTrigger className="w-36 h-8 text-xs">
            {statusFilter === 'annotated' ? 'Annotés' : statusFilter === 'pending' ? 'En attente' : 'Tous'}
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous</SelectItem>
            <SelectItem value="annotated">Annotés</SelectItem>
            <SelectItem value="pending">En attente</SelectItem>
          </SelectContent>
        </Select>

        <Select value={categoryFilter} onValueChange={v => { setCategoryFilter(v === 'all' ? '' : v); setOffset(0) }}>
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

        <span className="ml-auto text-xs font-mono text-neutral-400 tabular-nums">
          {total} posts
        </span>
      </div>

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
              className="group relative rounded-lg overflow-hidden bg-neutral-100"
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
                    <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                        <path d="M20 6L9 17l-5-5"/>
                      </svg>
                    </div>
                  </div>
                )}

                {/* Badge type */}
                <div className="absolute bottom-1.5 left-1.5">
                  <span className="text-[9px] font-mono uppercase bg-black/60 text-white px-1.5 py-0.5 rounded-full">
                    {item.media_product_type}
                  </span>
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
