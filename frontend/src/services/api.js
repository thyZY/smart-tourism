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

function isApiUnavailable(error) {
  // A failed endpoint can still prove the API is reachable. Treat network
  // failures and gateway/service-availability responses as global outages;
  // ordinary 4xx/5xx responses belong to the calling feature's error state.
  if (!error.response) return true
  return [502, 503, 504].includes(error.response.status)
}

api.interceptors.response.use(
  response => {
    reportApiAvailability(true)
    return response
  },
  error => {
    reportApiAvailability(!isApiUnavailable(error))
    return Promise.reject(error)
  }
)
