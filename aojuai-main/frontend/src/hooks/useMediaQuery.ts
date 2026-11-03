'use client'

import { useEffect, useState } from 'react'

export function useMediaQuery(query: string, defaultState = false) {
  const [matches, setMatches] = useState(defaultState)

  useEffect(() => {
    const mql = window.matchMedia(query)

    const onChange = () => setMatches(mql.matches)
    onChange()

    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    }

    mql.addListener(onChange)
    return () => mql.removeListener(onChange)
  }, [query])

  return matches
}

export function useIsMobile() {
  return useMediaQuery('(max-width: 767px)')
}

