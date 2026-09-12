import './app.css'
import './semantic-tokens.css'
import App from './App.svelte'
import { mount } from 'svelte'

// Establish the local write capability before mounting. Never persist it or
// attach it to a remote URL. A failed handshake must not leave a blank page.
const nativeFetch = window.fetch.bind(window)
let app
try {
  const response = await nativeFetch('/api/session', {cache:'no-store', signal:AbortSignal.timeout(10000)})
  if (!response.ok) throw new Error('Local session unavailable')
  const {capability} = await response.json()
  if (typeof capability !== 'string' || !/^[A-Za-z0-9_-]{40,100}$/.test(capability)) throw new Error('Invalid local session')
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
  app = mount(App, {target: document.getElementById('app')})
} catch {
  window.fetch = nativeFetch
  const main = document.createElement('main')
  main.className = 'startup-error'
  const title = document.createElement('h1')
  title.textContent = 'The local workspace could not connect.'
  const message = document.createElement('p')
  message.textContent = 'Make sure BrandForge is running, then reload. If setup changed, close the app and run SETUP-WINDOWS.bat on Windows, or follow START-HERE.md on macOS/Linux. Your saved work has not been deleted.'
  const retry = document.createElement('button')
  retry.type = 'button'
  retry.textContent = 'Reload workspace'
  retry.addEventListener('click', () => location.reload())
  main.append(title, message, retry)
  document.getElementById('app').replaceChildren(main)
}
export default app
