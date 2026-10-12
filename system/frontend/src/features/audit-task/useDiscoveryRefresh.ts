import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
// Status polling can finish before the slower candidate/evidence polling tick.
export function useDiscoveryRefresh(
  entries: { key: string; auditId: string; status: string }[],
) {
  const cache = useQueryClient()
  const previous = useRef(new Map<string, string>())
  useEffect(() => {
    const changed = new Set<string>()
    for (const entry of entries) {
      const before = previous.current.get(entry.key)
      if (before !== undefined && before !== entry.status)
        changed.add(entry.auditId)
    }
    previous.current = new Map(
      entries.map((entry) => [entry.key, entry.status]),
    )
    for (const auditId of changed) {
      void cache.invalidateQueries({ queryKey: ["candidates", auditId] })
      void cache.invalidateQueries({ queryKey: ["evidence", auditId] })
      void cache.invalidateQueries({ queryKey: ["repairs", auditId] })
    }
    if (changed.size) void cache.invalidateQueries({ queryKey: ["rules"] })
  }, [cache, entries])
}
