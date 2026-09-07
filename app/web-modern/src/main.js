import './app.css'
import App from './App.svelte'
import { mount } from 'svelte'

// Bootstrap a same-origin local capability before mounting. Never attach it
// to remote/provider requests, URLs, localStorage or telemetry.
const nativeFetch = window.fetch.bind(window)
const response = await nativeFetch('/api/session', {cache:'no-store'})
if (!response.ok) throw new Error('Could not establish the local desktop session. Reload the app.')
const {capability} = await response.json()
window.fetch = (input, init = {}) => {
  const url = new URL(typeof input === 'string' ? input : input.url, location.href)
  const method = (init.method || input.method || 'GET').toUpperCase()
  if (url.origin === location.origin && url.pathname.startsWith('/api/') && ['POST','PUT','PATCH','DELETE'].includes(method)) {
    const headers = new Headers(init.headers || input.headers)
    headers.set('X-BrandForge-Token', capability)
    return nativeFetch(input, {...init, headers})
  }
  return nativeFetch(input, init)
}
const app = mount(App, {target: document.getElementById('app')})
export default app
