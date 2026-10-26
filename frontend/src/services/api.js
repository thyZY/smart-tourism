import axios from 'axios'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''

export const api = axios.create({
  baseURL: configuredBaseUrl.replace(/\/+$/, '')
})

function reportApiAvailability(available) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('smart-tourism:api-status', {
    detail: { available }
  }))
}

api.interceptors.response.use(
  response => {
    reportApiAvailability(true)
    return response
  },
  error => {
    // A validation/auth/client response proves the API was reachable. Only network
    // failures and server/proxy errors should surface the API-unavailable notice.
    reportApiAvailability(Boolean(error.response && error.response.status < 500))
    return Promise.reject(error)
  }
)
