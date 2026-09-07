<script>
  import { Target, Wallet, Megaphone, CalendarDays, ImageIcon } from '@lucide/svelte'
  import { mdToHtml } from './markdown.js'

  let messages = [
    { role: 'bot', text: 'Welcome to BrandForge. Start with your brand, audience and approved benefits. Use local text templates or your configured provider, review the draft, then export your work. Agent Discussion compares strategy, copy and critique; connected tools may make network requests.' }
  ]
  let input = ''
  let loading = false
  // Persist the mode: founders who switched Agent Discussion ON expect it to
  // stay ON across tab switches (it used to silently reset — confusing).
  let councilMode = false
  try { councilMode = localStorage.getItem('bf-council') === '1' } catch {}
  function toggleCouncil() {
    councilMode = !councilMode
    try { localStorage.setItem('bf-council', councilMode ? '1' : '0') } catch {}
  }

  async function send() {
    const text = input.trim()
    // Keep the UI ceiling in sync with the server's 2000-char cap
    // (was 1000 — messages the UI allowed the server to reject).
    if (!text || text.length > 2000 || loading) return
    messages = [...messages, { role: 'user', text }]
    input = ''
    loading = true
    try {
      if (councilMode) {
        // Live debate: each agent's turn streams in as it finishes, with a
        // "thinking…" bubble while the next agent works. Falls back to the
        // batch endpoint if streaming is unavailable.
        await streamCouncil(text)
      } else {
        const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) })
        const data = await res.json()
        const resp = data.brandforge_response || data.vanguard_response || (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) || 'No response'
        messages = [...messages, { role: 'bot', text: resp }]
        if (data.memory_saved === false) messages = [...messages, {role:'bot',text:'This response could not be completely saved to local memory. Copy it before leaving and check local storage.'}]
      }
    } catch (e) {
      messages = [...messages, { role: 'bot', text: '❌ Server offline — start it from the app folder: `python server.py` (or `python brandforge.py --server`), or connect a provider in Settings.' }]
    }
    loading = false
    setTimeout(() => {
      const box = document.getElementById('chatBox')
      if (box) box.scrollTop = box.scrollHeight
    }, 50)
  }

  function scrollChat() {
    setTimeout(() => {
      const box = document.getElementById('chatBox')
      if (box) box.scrollTop = box.scrollHeight
    }, 50)
  }

  function replaceThinking(textContent) {
    let replaced = false
    messages = messages.map(m => {
      if (m.thinking && !replaced) { replaced = true; return { role: 'bot', text: textContent } }
      return m
    })
    if (!replaced) messages = [...messages, { role: 'bot', text: textContent }]
    scrollChat()
  }

  async function streamCouncil(text) {
    try {
      const res = await fetch('/api/swarm/chat/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      })
      if (!res.ok || !res.body) throw new Error('stream unavailable')
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      let finalSeen = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        if (buf.length > 500000) throw new Error('Stream exceeded the safe buffer')
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const chunk = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const line = chunk.trim()
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (payload === '[DONE]') continue
          let ev
          try { ev = JSON.parse(payload) } catch { continue }
          if (ev.type === 'thinking') {
            messages = [...messages, { role: 'bot', thinking: true, text: `${ev.icon} **${ev.label}** is thinking…` }]
            scrollChat()
          } else if (ev.type === 'turn') {
            replaceThinking(`${ev.icon} **${ev.label}**\n${ev.text}`)
          } else if (ev.type === 'final') {
            finalSeen = true
            replaceThinking(`✅ **FINAL PLAN (council verdict)**\n${ev.final || ''}`)
          }
        }
      }
      if (!finalSeen) throw new Error('Discussion ended before confirmation')
    } catch (e) {
      messages = messages.filter(m => !m.thinking)
      messages = [...messages, {role:'bot',text:'The discussion was interrupted or could not be confirmed. Completed responses are kept above. No second generation was started automatically; check the result before retrying.'}]

    }
  }

  function quick(t) { input = t; send() }
</script>

<div class="rounded-[20px] bg-card border border-line overflow-hidden flex flex-col">
  <div class="p-5 border-b border-line flex items-center gap-3">
    <div class="w-8 h-8 rounded-full bg-ink text-bg flex items-center justify-center font-bold text-[12px]">B</div>
    <div>
      <h3 class="font-bold text-[14px]">Ask BrandForge</h3>
      <p class="text-[11px] text-faint">Local-first • 21 tools • Cloud providers are optional</p>
    </div>
    <button on:click={toggleCouncil} title="3 agents (Strategist, Copywriter, Critic) discuss your question in turns" class="ml-auto px-3 py-1.5 rounded-full border text-[11px] font-medium transition flex items-center gap-1.5 {councilMode ? 'bg-gold text-ink border-gold' : 'bg-inset text-faint border-line hover:border-zinc-600'}" aria-pressed={councilMode}>
      <span class="w-1.5 h-1.5 rounded-full {councilMode ? 'bg-ink' : 'bg-zinc-600'}"></span> Agent Discussion {councilMode ? 'ON' : 'OFF'}
    </button>
  </div>

  <div id="chatBox" role="region" aria-label="Conversation history" aria-live="polite" class="h-[360px] overflow-y-auto p-4 space-y-3 bg-inset">
    {#each messages as m}
      <div class="flex {m.role === 'user' ? 'justify-end' : 'justify-start'}">
        <div class="max-w-[88%] px-4 py-2.5 rounded-2xl text-[13px] leading-[1.55] {m.role === 'user' ? 'bg-ink text-bg rounded-br-md' : 'bg-card border border-line text-ink rounded-bl-md markdown'}">
          {#if m.role === 'user'}{m.text}{:else}{@html mdToHtml(m.text)}{/if}
        </div>
      </div>
    {/each}
    {#if loading}
      <div class="flex gap-1 px-2"><span class="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-bounce"></span><span class="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-bounce delay-100"></span><span class="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-bounce delay-200"></span></div>
    {/if}
  </div>

  <div class="p-4 border-t border-line bg-card">
    <div class="flex gap-2">
      <input bind:value={input} aria-label="Message BrandForge" on:keydown={(e) => e.key === 'Enter' && send()} placeholder="Ask: audit example.com, ROI $200/mo vs $199 once, copy for my brand..." class="flex-1 px-4 py-2.5 rounded-full border border-line bg-inset text-ink text-[13px] outline-none focus:border-white/20 placeholder:text-faint" />
      <button on:click={send} disabled={loading} class="w-10 h-10 rounded-full bg-ink text-bg flex items-center justify-center font-bold hover:opacity-90 disabled:opacity-50 transition">↑</button>
    </div>
    <div class="flex gap-1.5 flex-wrap mt-3">
      <button on:click={() => quick('Audit https://example.com — give SEO score and recommendations')} class="px-3 py-1 rounded-full bg-inset border border-line text-[11px] text-faint hover:text-ink hover:border-zinc-600 transition flex items-center gap-1.5"><Target class="w-3 h-3" /> Audit Website</button>
      <button on:click={() => quick('ROI calculator: I pay $200/month for tools, calculate my 3-year saving vs $199 once')} class="px-3 py-1 rounded-full bg-inset border border-line text-[11px] text-faint hover:text-ink hover:border-zinc-600 transition flex items-center gap-1.5"><Wallet class="w-3 h-3" /> ROI Calculator</button>
      <button on:click={() => quick('Generate AIDA ad for my coffee shop — organic, fast delivery, family-owned')} class="px-3 py-1 rounded-full bg-inset border border-line text-[11px] text-faint hover:text-ink hover:border-zinc-600 transition flex items-center gap-1.5"><Megaphone class="w-3 h-3" /> Generate Copy</button>
      <button on:click={() => quick('Give me a 30-day social calendar for my retail brand')} class="px-3 py-1 rounded-full bg-inset border border-line text-[11px] text-faint hover:text-ink hover:border-zinc-600 transition flex items-center gap-1.5"><CalendarDays class="w-3 h-3" /> Social Calendar</button>
      <button on:click={() => quick('Use the generate_image tool to create a premium marketing hero image for my coffee shop — warm tones, modern minimal style, no text')} class="px-3 py-1 rounded-full bg-inset border border-line text-[11px] text-faint hover:text-ink hover:border-zinc-600 transition flex items-center gap-1.5"><ImageIcon class="w-3 h-3" /> Generate AI Image</button>
    </div>
  </div>
</div>

<style>
  :global(.markdown p) { margin: 4px 0; color: var(--ink); }
  :global(.markdown h3), :global(.markdown h4), :global(.markdown h5) { font-size: 13px; font-weight: 700; margin: 8px 0 4px; color: var(--ink); }
  :global(.markdown ul) { margin: 4px 0 4px 16px; list-style: disc; }
  :global(.markdown li) { margin: 2px 0; }
  :global(.markdown b) { color: var(--ink); }
  :global(.markdown code) { background: var(--inset); padding: 1px 4px; border-radius: 4px; font-size: 12px; }
  :global(.markdown a) { color: var(--gold); }
  :global(.markdown pre) { background: var(--inset); padding: 10px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
</style>
