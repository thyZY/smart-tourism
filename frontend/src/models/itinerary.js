export const ITINERARY_SCHEMA_VERSION = 1

/**
 * Create a serializable itinerary snapshot.
 *
 * This is intentionally independent from map layers, Valhalla geometry,
 * and DeepSeek responses. A saved itinerary stores the information required
 * to rebuild a route, not a stale route result.
 */
export function createItinerarySnapshot({
  title = '未命名行程',
  places = [],
  lockedPlaceIds = [],
  transportMode = 'pedestrian',
  budgetHours = 8,
  startTime = '09:00',
  source = 'manual',
  metadata = {},
} = {}) {
  return {
    schemaVersion: ITINERARY_SCHEMA_VERSION,
    id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    title,
    places,
    lockedPlaceIds,
    transportMode,
    budgetHours,
    startTime,
    source,
    metadata,
    createdAt: new Date().toISOString(),
  }
}

export function isValidItinerarySnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return false
  if (snapshot.schemaVersion !== ITINERARY_SCHEMA_VERSION) return false
  if (!Array.isArray(snapshot.places)) return false
  if (!Array.isArray(snapshot.lockedPlaceIds)) return false
  if (!['pedestrian', 'bicycle', 'auto'].includes(snapshot.transportMode)) return false
  return true
}
