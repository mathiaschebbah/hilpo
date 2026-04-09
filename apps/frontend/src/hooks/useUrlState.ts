import { useCallback, useEffect, useState } from 'react'

/**
 * Hook générique pour persister une valeur d'état dans URLSearchParams.
 *
 * - Lit la valeur initiale depuis l'URL courante (sinon `defaultValue`).
 * - Chaque `set` pousse un `history.pushState` pour que le back/forward du
 *   navigateur restaure l'état précédent.
 * - Écoute `popstate` pour synchroniser l'état React quand l'utilisateur
 *   navigue avec les flèches du navigateur.
 * - Supporte un `serialize`/`deserialize` optionnel pour les types non-string.
 *
 * Les valeurs égales à `defaultValue` sont retirées de l'URL pour garder
 * celle-ci propre.
 */
export function useUrlState<T>(
  key: string,
  defaultValue: T,
  options?: {
    serialize?: (value: T) => string
    deserialize?: (raw: string) => T
  },
): [T, (value: T) => void] {
  const serialize = options?.serialize ?? ((v: T) => String(v))
  const deserialize =
    options?.deserialize ?? ((raw: string) => raw as unknown as T)

  const read = useCallback((): T => {
    if (typeof window === 'undefined') return defaultValue
    const params = new URLSearchParams(window.location.search)
    const raw = params.get(key)
    if (raw === null) return defaultValue
    try {
      return deserialize(raw)
    } catch {
      return defaultValue
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const [state, setState] = useState<T>(read)

  useEffect(() => {
    const handler = () => setState(read())
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [read])

  const update = useCallback(
    (value: T) => {
      setState(value)
      const params = new URLSearchParams(window.location.search)
      const isDefault =
        value === defaultValue ||
        value === '' ||
        value === null ||
        value === undefined
      if (isDefault) {
        params.delete(key)
      } else {
        params.set(key, serialize(value))
      }
      const qs = params.toString()
      const url =
        (qs ? `?${qs}` : window.location.pathname) + window.location.hash
      window.history.pushState(null, '', url)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, defaultValue],
  )

  return [state, update]
}
