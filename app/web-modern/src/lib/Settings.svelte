<script>
  import { onMount } from 'svelte'
  import { Settings2 } from '@lucide/svelte'

  let providers = ['offline', 'ollama', 'groq', 'gemini', 'anthropic', 'openrouter', 'deepseek', 'kimi', 'xai_grok']
  // Premium models matter: the better the model, the better the campaign copy.
  // Curated, currently-valid IDs per provider + "Custom…" for anything else
  // (the API accepts any model string the provider recognizes).
  // Curated against live provider catalogs on 27 Aug 2026 (retired IDs like
  // gemini-2.5-flash / deepseek-chat / moonshot-v1-8k are auto-migrated by the
  // engine and deliberately absent from the picker).
  const MODEL_PRESETS = {
    anthropic: ['claude-sonnet-5', 'claude-opus-5', 'claude-fable-5', 'claude-haiku-4-5', 'claude-sonnet-4-6', 'claude-opus-4-8'],
    gemini: ['gemini-3.6-flash', 'gemini-3.7-flash', 'gemini-3.5-flash', 'gemini-3.1-pro-preview', 'gemini-2.5-pro'],
    groq: ['qwen/qwen3.8-27b', 'openai/gpt-oss-120b', 'qwen/qwen3.6-27b', 'groq/compound'],
    openrouter: ['deepseek/deepseek-r1:free', 'anthropic/claude-sonnet-5', 'google/gemini-3.6-flash', 'openai/gpt-4o'],
    deepseek: ['deepseek-v4-flash', 'deepseek-v4-pro'],
    kimi: ['kimi-k2.5', 'kimi-k2'],
    xai_grok: ['grok-4.6', 'grok-4.5', 'grok-4.3'],
  }
  const PROVIDER_LABEL = { anthropic: 'anthropic (Claude)', groq: 'groq', gemini: 'gemini', openrouter: 'openrouter', deepseek: 'deepseek', kimi: 'kimi', xai_grok: 'xai_grok' }
  let modelChoice = 'default'
  let provider = 'offline'
  let model = ''
  let hasKey = false
  // AI image design (separate engine — Gemini / Grok / OpenAI image keys)
  const IMAGE_PROVIDERS_UI = ['auto', 'gemini', 'xai_grok', 'openai', 'off']
  const IMAGE_PROVIDER_LABEL = { auto: 'Auto: one keyed provider when online', gemini: 'Gemini (Nano Banana)', xai_grok: 'Grok Imagine', openai: 'OpenAI (gpt-image)', off: 'Basic layouts (no image provider)' }
  let imageProvider = 'auto'
  let imageModel = ''
  let imageKey = ''
  let imageKeyStatus = {}
  let apiKey = ''
  let clients = []
  let activeClient = null
  let license = null
  let busy = false
  let msg = null
  let showAdd = false
  let newClient = { name: '', industry: 'General', tone: 'Direct, confident', audience: '', primary: '#E8B54A', secondary: '#0F172A' }
  let adding = false
  let brainOpen = false
  let brain = { brand_promise: '', proof_points: '', prohibited_claims: '', agency_footer: '', show_brandforge_branding: true }
  let brainSaving = false
  let logoBusy = false
  let logoInput = null

  async function addClient() {
    if (!newClient.name.trim()) return
    adding = true
    msg = null
    try {
      const res = await fetch('/api/clients', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_name: newClient.name.trim(),
          industry: newClient.industry,
          tone_of_voice: newClient.tone,
          target_audience: newClient.audience,
          primary_color: newClient.primary,
          secondary_color: newClient.secondary,
        })
      })
      const d = await res.json()
      if (!res.ok) throw new Error((d.detail && (typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail))) || 'Failed')
      newClient = { name: '', industry: 'General', tone: 'Direct, confident', audience: '', primary: '#E8B54A', secondary: '#0F172A' }
      showAdd = false
      msg = { ok: true, text: 'Brand added' }
      await load()
    } catch (e) {
      msg = { ok: false, text: e.message }
    }
    adding = false
  }

  async function load() {
    try {
      const res = await fetch('/api/settings')
      const d = await res.json()
      providers = d.providers || providers
      provider = d.provider || 'offline'
      model = d.model || ''
      modelChoice = model ? ((MODEL_PRESETS[provider] || []).includes(model) ? model : 'custom') : 'default'
      hasKey = !!d.has_api_key
      license = d.license || null
      if (d.image) {
        imageProvider = d.image.provider || 'auto'
        imageModel = d.image.model || ''
        imageKeyStatus = d.image.key_status || {}
      }
    } catch { /* server offline */ }
    try {
      const res = await fetch('/api/clients')
      const d = await res.json()
      clients = d.clients || []
      activeClient = d.active || null
      brain = {
        brand_promise: activeClient?.brand_promise || '',
        proof_points: activeClient?.proof_points || '',
        prohibited_claims: activeClient?.prohibited_claims || '',
        agency_footer: activeClient?.agency_footer || '',
        show_brandforge_branding: activeClient?.show_brandforge_branding !== false,
      }
    } catch { /* ignore */ }
  }

  async function selectProvider(selected) {
    const previous = provider
    provider = selected
    if (selected !== previous) {
      apiKey = ''
      model = ''
      modelChoice = 'default'
      hasKey = ['offline', 'ollama'].includes(selected)
      await loadKeyStatus(selected)
    }
  }

  function applyModelChoice() {
    // 'default' = provider's recommended model (server picks it);
    // 'custom' = whatever the user types; anything else is a preset ID.
    model = modelChoice === 'default' || modelChoice === 'custom' ? (modelChoice === 'default' ? '' : model) : modelChoice
  }

  async function loadKeyStatus(selected) {
    if (['offline', 'ollama'].includes(selected)) {
      if (provider === selected) hasKey = true
      return
    }
    try {
      const res = await fetch(`/api/settings/key-status?provider=${encodeURIComponent(selected)}`)
      const data = await res.json()
      // A fast second click can make an older response arrive last; only apply
      // a result to the provider the user is still viewing.
      if (provider === selected && res.ok) hasKey = !!data.has_api_key
    } catch {
      if (provider === selected) hasKey = false
    }
  }

  async function save() {
    busy = true
    msg = null
    try {
      const payload = { provider, image_provider: imageProvider }
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      if (model.trim()) payload.model = model.trim()
      if (imageKey.trim()) payload.image_api_key = imageKey.trim()
      payload.image_model = imageModel.trim()
      const res = await fetch('/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      })
      const d = await res.json()
      if (!res.ok || d.error) {
        const detail = typeof d.detail === 'string' ? d.detail : d.detail ? JSON.stringify(d.detail) : d.error
        throw new Error(detail || 'Failed to save settings')
      }
      hasKey = d.has_api_key
      apiKey = ''
      imageKey = ''
      msg = { ok: true, text: `Saved · Provider: ${provider} · Image design: ${IMAGE_PROVIDER_LABEL[imageProvider] || imageProvider}` }
      await load()  // refresh key-saved indicators from the server
    } catch (e) {
      msg = { ok: false, text: e.message }
    }
    busy = false
  }

  async function activate(clientId) {
    try {
      const response = await fetch(`/api/clients/${encodeURIComponent(clientId)}/activate`, { method: 'POST' })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not activate brand')
      }
      await load()
    } catch (error) {
      msg = { ok: false, text: error.message }
    }
  }

  async function uploadLogo(event) {
    const file = event.target.files && event.target.files[0]
    if (!file || !activeClient || logoBusy) return
    logoBusy = true
    msg = null
    try {
      const form = new FormData()
      form.append('logo', file)
      const res = await fetch(`/api/clients/${encodeURIComponent(activeClient.client_id)}/logo`, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Logo upload failed')
      msg = { ok: true, text: 'Logo saved to this brand profile.' }
      await load()
    } catch (error) {
      msg = { ok: false, text: error.message }
    }
    logoBusy = false
    if (logoInput) logoInput.value = ''
  }

  async function saveBrandBrain() {
    if (!activeClient) return
    brainSaving = true
    msg = null
    try {
      const payload = {
        client_name: activeClient.client_name,
        industry: activeClient.industry || 'General',
        tone_of_voice: activeClient.tone_of_voice || 'Clear, professional',
        target_audience: activeClient.target_audience || '',
        primary_color: activeClient.primary_color || '#E8B54A',
        secondary_color: activeClient.secondary_color || '#0F172A',
        agency_brand: activeClient.agency_brand || activeClient.client_name,
        ...brain,
      }
      const response = await fetch(`/api/clients/${encodeURIComponent(activeClient.client_id)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not save Brand Brain')
      msg = { ok: true, text: 'Brand Brain saved. Future campaigns will use these guardrails.' }
      await load()
    } catch (error) {
      msg = { ok: false, text: error.message }
    }
    brainSaving = false
  }

  onMount(load)
</script>

<div class="rounded-card bg-card border border-line overflow-hidden">
  <div class="p-5 border-b border-line">
    <h2 class="font-bold text-[14px] flex items-center gap-2"><Settings2 class="w-4 h-4 text-gold" /> Settings</h2>
    <p class="text-[11px] text-faint">AI provider, keys & active brand</p>
  </div>

  <div class="p-5 space-y-5">
    <!-- license -->
    <div class="p-3 rounded-xl bg-inset border border-line text-[12px]">
      {#if license}
        <div class="flex items-center gap-2 mb-1">
          <span class="w-2 h-2 rounded-full {license.licensed ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
          <b class="text-ink">
            {#if license.mode === 'local'}Local install — full features, owned forever{:else if license.licensed}Licensed: {license.tier}{:else}Free tier — {license.limit || 3} campaign{(license.limit || 3) === 1 ? '' : 's'}{/if}
          </b>
        </div>
        <p class="text-faint leading-relaxed">{license.note}</p>
      {/if}
    </div>

    <!-- provider -->
    <div>
      <span class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">AI Provider</span>
      <div class="grid grid-cols-2 gap-2">
        {#each providers as p}
          <button on:click={() => selectProvider(p)}
            class="px-3 py-2 rounded-xl text-[12px] font-medium text-left transition border {provider === p ? 'bg-ink text-bg border-white' : 'bg-inset text-mut border-line hover:border-zinc-600'}">
            {PROVIDER_LABEL[p] || p}
          </button>
        {/each}
      </div>
      {#if provider === 'offline'}
        <p class="text-[11px] text-faint mt-2">Offline text uses local templates without a model charge. Image and connected-tool settings are separate.</p>
      {/if}
      {#if provider === 'ollama'}
        <p class="text-[11px] text-faint mt-2">Uses Ollama at localhost:11434 (fully offline models).</p>
      {/if}
    </div>

    {#if !['offline', 'ollama'].includes(provider)}
      <div>
        <label for="apikey" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">
          API Key for {provider}{hasKey ? ' (key on file for current provider)' : ''}
        </label>
        <input id="apikey" bind:value={apiKey} type="password" autocomplete="off"
          placeholder={hasKey ? '•••••••• (leave blank to keep existing key)' : 'Paste API key — free: console.groq.com/keys or aistudio.google.com'}
          class="w-full px-4 py-2.5 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50" />
        <p class="text-[11px] text-faint mt-1.5">Keys are kept in your local <code class="text-[11px]">.env</code>, not config.json. Restrict access to your user account and folder; never share this file. POSIX file permissions and Windows access controls differ.</p>
        <p class="text-[11px] text-faint mt-1">Get a key from the provider: <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer" class="text-gold underline">Groq ↗</a> · <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" class="text-gold underline">Gemini ↗</a> — text access does not prove image access or free image generation. Also available: <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" class="text-gold underline">Claude ↗</a> (provider fees may apply).</p>
        <label for="model" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block mt-3">Text model — choose a supported model ID</label>
        <select id="model" bind:value={modelChoice} on:change={applyModelChoice}
          class="w-full px-4 py-2.5 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50">
          <option value="default">Recommended default (best value)</option>
          {#each MODEL_PRESETS[provider] || [] as m}
            <option value={m}>{m}</option>
          {/each}
          <option value="custom">Custom… (type any model ID)</option>
        </select>
        {#if modelChoice === 'custom'}
          <input bind:value={model} placeholder="e.g. claude-opus-4-8 or gemini-2.5-pro"
            class="w-full mt-2 px-4 py-2.5 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50" />
        {/if}
        <p class="text-[11px] text-faint mt-1.5">Provider access, quotas and pricing vary by account and model. Check availability and review the resulting copy; model choice does not guarantee quality.</p>
      </div>
    {/if}

    <!-- AI image design -->
    <p class="text-[11px] text-faint">With a configured image key, campaigns request three complete AI advertisements. Three provider requests can incur fees. No automatic provider/model switch. Review product details, spelling and claims; AI lettering is raster, not editable text. Basic layouts remain a deliberate no-image-provider option.</p>
    <div class="p-4 rounded-xl bg-inset border border-line">
      <h3 class="text-[12px] font-bold text-ink flex items-center gap-2">AI Image Design</h3>
      <p class="text-[11px] text-faint mt-0.5 mb-3">Hero, square and story advertisements are generated as complete artwork. Auto selects one keyed provider only when text generation is connected. An explicitly selected image provider may run even with offline text. No key means basic layouts; no paid provider failure silently switches to another service. Use the per-campaign no-AI checkbox to disable all provider calls.</p>
      <div class="grid grid-cols-1 gap-1.5 mb-3">
        {#each IMAGE_PROVIDERS_UI as ip}
          <button on:click={() => { imageProvider = ip; imageKey = '' }}
            class="px-3 py-2 rounded-xl text-[12px] font-medium text-left transition border flex items-center justify-between {imageProvider === ip ? 'bg-ink text-bg border-white' : 'bg-card text-mut border-line hover:border-zinc-600'}">
            <span>{IMAGE_PROVIDER_LABEL[ip] || ip}</span>
            {#if ip !== 'auto' && ip !== 'off' && imageKeyStatus[ip]}
              <span class="w-2 h-2 rounded-full {imageProvider === ip ? 'bg-emerald-400' : 'bg-emerald-500'}" title="Key saved"></span>
            {/if}
          </button>
        {/each}
      </div>
      {#if ['gemini', 'xai_grok', 'openai'].includes(imageProvider)}
        <input type="password" bind:value={imageKey} placeholder="{imageProvider === 'gemini' ? 'GEMINI_API_KEY' : imageProvider === 'xai_grok' ? 'XAI_API_KEY' : 'OPENAI_API_KEY'} (leave blank to keep saved key)"
          class="w-full px-4 py-2.5 rounded-xl border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50" />
        <input bind:value={imageModel} placeholder="Model (optional — recommended default used otherwise)"
          class="w-full mt-2 px-4 py-2.5 rounded-xl border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50" />
        <p class="text-[11px] text-faint mt-1.5">The key is stored locally in this install's .env file; only the design prompt travels to the provider.</p>
      {/if}
    </div>

    {#if msg}
      <div role={msg.ok ? 'status' : 'alert'} class="p-3 rounded-xl text-[12px] bg-card border border-line {msg.ok ? 'text-emerald-300' : 'text-red-300'}">{msg.text}</div>
    {/if}

    <button on:click={save} disabled={busy} class="w-full py-3 rounded-full bg-ink text-bg font-bold text-[13px] disabled:cursor-wait enabled:hover:opacity-90 transition">
      {busy ? 'Saving...' : 'Save Settings'}
    </button>

    <!-- Brand Brain -->
    <div class="p-4 rounded-xl bg-inset border border-line">
      <div class="flex items-start gap-2">
        <div>
          <h3 class="text-[12px] font-bold text-ink">Brand Brain</h3>
          <p class="text-[11px] text-faint mt-0.5">Set approved proof and phrases BrandForge must flag before a campaign is used.</p>
        </div>
        <button on:click={() => brainOpen = !brainOpen} class="ml-auto text-[11px] font-bold text-gold hover:underline">{brainOpen ? 'Close' : 'Edit'}</button>
      </div>
      {#if brainOpen && activeClient}
        <div class="mt-3 space-y-3">
          <div>
            <label for="brain-promise" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Brand promise</label>
            <input id="brain-promise" bind:value={brain.brand_promise} maxlength="240" placeholder="The value the client can honestly promise" class="w-full px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none focus:border-gold/50" />
          </div>
          <div>
            <label for="brain-proof" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Approved proof points</label>
            <textarea id="brain-proof" bind:value={brain.proof_points} maxlength="500" placeholder="e.g. Established in 2018; delivery within Karachi; 4.8 average rating from verified customers" class="w-full min-h-[66px] px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none focus:border-gold/50 resize-y"></textarea>
          </div>
          <div>
            <label for="brain-prohibited" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Prohibited claims or phrases</label>
            <textarea id="brain-prohibited" bind:value={brain.prohibited_claims} maxlength="300" placeholder="Comma-separated, e.g. guaranteed, best in Pakistan, cure" class="w-full min-h-[58px] px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none focus:border-gold/50 resize-y"></textarea>
          </div>
          <div>
            <label for="brain-footer" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Client-facing export footer</label>
            <input id="brain-footer" bind:value={brain.agency_footer} maxlength="180" placeholder="e.g. Prepared by Apex Growth Studio · hello@example.com" class="w-full px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none focus:border-gold/50" />
          </div>
          <label class="flex items-center gap-2 text-[11px] text-ink cursor-pointer"><input type="checkbox" bind:checked={brain.show_brandforge_branding} class="accent-[var(--gold)]" /> Include “Prepared with BrandForge OS” in client-facing exports</label>
          <p class="text-[10.5px] text-faint">The Claim Guard highlights matches; it does not replace legal, platform, or factual review.</p>
          <button on:click={saveBrandBrain} disabled={brainSaving} class="w-full py-2.5 rounded-full bg-ink text-bg text-[12px] font-bold disabled:cursor-wait">{brainSaving ? 'Saving…' : 'Save Brand Brain'}</button>
        </div>
      {:else if activeClient}
        <p class="text-[11px] text-faint mt-3">{brain.proof_points || brain.prohibited_claims ? 'Guardrails configured for this active brand.' : 'No guardrails configured yet.'}</p>
      {/if}
    </div>

    <!-- clients -->
    <div>
      <div class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-2">Active Brand {clients.length > 1 ? `(${clients.length})` : ''}</div>
      {#if activeClient}
        <div class="mb-3 p-3 rounded-xl bg-inset border border-line">
          <div class="flex items-center gap-3">
            {#if activeClient.logo_path}
              <img src={`/api/clients/${encodeURIComponent(activeClient.client_id)}/logo`} alt={`${activeClient.client_name} logo`} class="w-10 h-10 rounded-lg border border-line object-contain bg-card" />
            {:else}
              <span class="w-10 h-10 rounded-lg border border-line bg-card flex items-center justify-center text-[11px] text-faint">none</span>
            {/if}
            <div class="min-w-0">
              <p class="text-[11px] text-ink">Brand logo (PNG or JPEG, max 5 MB)</p>
              <p class="text-[10.5px] text-faint">Stored locally with this brand's profile.</p>
            </div>
          </div>
          <input aria-label="Upload approved brand logo" type="file" accept="image/png,image/jpeg" bind:this={logoInput} on:change={uploadLogo} class="mt-2 w-full text-[11px] text-mut file:mr-2 file:px-3 file:py-1.5 file:rounded-full file:border-0 file:bg-ink file:text-bg file:text-[11px] file:font-bold cursor-pointer" />
        </div>
      {/if}
      {#each clients as c}
        <button on:click={() => activate(c.client_id)}
          class="w-full flex items-center gap-3 px-3 py-2.5 mb-2 rounded-xl border transition text-left {activeClient && activeClient.client_id === c.client_id ? 'border-gold/60 bg-gold/5' : 'border-line bg-inset hover:border-zinc-600'}">
          <span class="w-6 h-6 rounded-md flex items-center justify-center text-[11px] font-bold text-bg" style="background:{c.primary_color || '#E8B54A'}">{(c.client_name || '?')[0]}</span>
          <span class="min-w-0">
            <span class="block text-[13px] text-ink font-medium truncate">{c.client_name}</span>
            <span class="block text-[11px] text-faint truncate">{c.industry} • {c.tone_of_voice}</span>
          </span>
          {#if activeClient && activeClient.client_id === c.client_id}<span class="ml-auto text-[11px] text-gold font-bold">ACTIVE</span>{/if}
        </button>
      {/each}
      <button on:click={() => showAdd = !showAdd} class="w-full mt-1 py-2.5 rounded-xl border border-line text-[12px] font-semibold text-mut hover:text-ink hover:border-zinc-500 transition">
        {showAdd ? '− Close' : '+ Add a brand'}
      </button>
      {#if showAdd}
        <div class="p-4 rounded-xl bg-inset border border-line space-y-3">
          <div>
            <label for="nc-name" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Brand name</label>
            <input id="nc-name" bind:value={newClient.name} placeholder="e.g. Apex Coffee" class="w-full px-3 py-2 rounded-lg border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="nc-ind" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Industry</label>
              <input id="nc-ind" bind:value={newClient.industry} class="w-full px-3 py-2 rounded-lg border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50" />
            </div>
            <div>
              <label for="nc-tone" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Tone of voice</label>
              <input id="nc-tone" bind:value={newClient.tone} class="w-full px-3 py-2 rounded-lg border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50" />
            </div>
          </div>
          <div>
            <label for="nc-aud" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Target audience</label>
            <input id="nc-aud" bind:value={newClient.audience} placeholder="e.g. Busy professionals" class="w-full px-3 py-2 rounded-lg border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="nc-p" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Primary color</label>
              <input id="nc-p" type="color" bind:value={newClient.primary} class="w-full h-9 rounded-lg border border-line bg-card cursor-pointer" />
            </div>
            <div>
              <label for="nc-s" class="text-[11px] font-semibold text-mut uppercase tracking-wide block mb-1">Secondary color</label>
              <input id="nc-s" type="color" bind:value={newClient.secondary} class="w-full h-9 rounded-lg border border-line bg-card cursor-pointer" />
            </div>
          </div>
          <button on:click={addClient} disabled={adding} class="w-full py-2.5 rounded-full bg-ink text-bg text-[12px] font-bold disabled:cursor-wait enabled:hover:opacity-90 transition">
            {adding ? 'Adding…' : 'Add brand'}
          </button>
        </div>
      {/if}
      <p class="text-[11px] text-faint mt-2">Each brand gets its own campaigns, memory and colors.</p>
    </div>
  </div>
</div>
