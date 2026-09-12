<script>
  import { onMount } from 'svelte'
  import SwarmStudio from './lib/SwarmStudio.svelte'
  import Chat from './lib/Chat.svelte'
  import Campaigns from './lib/Campaigns.svelte'
  import Settings from './lib/Settings.svelte'
  import Status from './lib/Status.svelte'
  import SwarmConstellation from './lib/SwarmConstellation.svelte'
  import { Rocket, MessageSquare, FolderOpen, Settings2, Command, Sun, Moon } from '@lucide/svelte'

  let health = { provider: 'offline', campaigns: 0, tools_count: 21, active_client: 'Default Studio', license: { mode: 'local', licensed: true } }
  let activeTab = 'swarm'
  let showCommandPalette = false
  let pendingCampaign = null
  let campaignsKey = 0
  let theme = 'dark'
  let onboarding = { brand: false, template: false, campaign: false, review: false, export: false }
  function initTheme() {
    try {
      theme = localStorage.getItem('vg-theme') || 'dark'
    } catch (e) { theme = 'dark' }
    if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light')
    else document.documentElement.removeAttribute('data-theme')
  }
  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark'
    if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light')
    else document.documentElement.removeAttribute('data-theme')
    try { localStorage.setItem('vg-theme', theme) } catch (e) {}
  }
  let paletteQuery = ''
  let paletteRef

  const paletteActions = [
    { label: 'Create New Campaign', id: 'swarm', icon: 'swarm' },
    { label: 'Ask BrandForge', id: 'chat', icon: 'chat' },
    { label: 'View My Campaigns', id: 'campaigns', icon: 'campaigns' },
    { label: 'Settings', id: 'settings', icon: 'settings' },
  ]
  const filteredActions = () => paletteQuery
    ? paletteActions.filter(a => a.label.toLowerCase().includes(paletteQuery.toLowerCase()))
    : paletteActions

  function focusCampaignForm() {
    activeTab = 'swarm'
    setTimeout(() => {
      const el = document.getElementById('product-name-input')
      if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.focus() }
    }, 60)
  }

  function runPalette(id) {
    activeTab = id
    showCommandPalette = false
    paletteQuery = ''
  }

  // Open the palette and move focus into its input — keyboard users open
  // with Ctrl/Cmd+K and must be able to type immediately.
  function openPalette() {
    showCommandPalette = true
    requestAnimationFrame(() => paletteRef && paletteRef.focus())
  }

  async function loadHealth() {
    try {
      const res = await fetch('/health')
      health = await res.json()
    } catch {}
  }

  // ---- Phase 3: privacy proof (network ledger) + update check ----
  let netAudit = { total_requests: 0, external_requests: 0, failed: 0, by_host: {}, recent: [] }
  let showNetPanel = false
  let updateInfo = null

  async function loadNetAudit() {
    try {
      const res = await fetch('/api/network-audit')
      netAudit = await res.json()
    } catch {}
  }

  async function loadUpdateInfo() {
    try {
      // first call kicks off the lazy background check; second gets the result
      await fetch('/api/update-check')
      setTimeout(async () => {
        try { updateInfo = await (await fetch('/api/update-check')).json() } catch {}
      }, 3500)
    } catch {}
  }

  // Opt-in update checks: null = never asked -> one-time prompt; the app must
  // not make its only automatic network call before the user agrees.
  let updateConsent = 'off'
  let updateConsentError = ''
  let updateConsentSaving = false
  async function loadConsent() {
    try {
      const d = await (await fetch('/api/update-consent')).json()
      updateConsent = d.env_disabled ? 'off' : d.env_forced ? 'on' : (d.consent === 'on' || d.consent === 'off' ? d.consent : null)
      if (updateConsent === 'on') loadUpdateInfo()
    } catch {}
  }
  async function setUpdateConsent(v) {
    if (updateConsentSaving) return
    updateConsentSaving = true
    updateConsentError = ''
    try {
      const response = await fetch('/api/update-consent', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: v === 'on' }) })
      if (!response.ok) throw new Error('Preference was not saved')
      const data = await response.json()
      updateConsent = data.consent
      if (updateConsent === 'on') loadUpdateInfo()
    } catch {
      updateConsentError = 'The preference was not saved. Check local storage and try again.'
    } finally { updateConsentSaving = false }
  }

  function licenseBadge() {
    const lic = health.license || {}
    if (lic.mode === 'local') return 'Local • Full features • Owned forever'
    if (lic.licensed) return `Licensed: ${lic.tier}`
    return `Free tier: ${lic.limit || 3} campaign${(lic.limit || 3) === 1 ? '' : 's'}`
  }

  function toggleOnboarding(key) {
    onboarding = { ...onboarding, [key]: !onboarding[key] }
    try { localStorage.setItem('vg-onboarding', JSON.stringify(onboarding)) } catch {}
  }

  function onCampaignCreated() {
    loadHealth()
    campaignsKey++
  }

  function onOpenCampaign(e) {
    activeTab = 'campaigns'
    pendingCampaign = e.detail
    setTimeout(() => { pendingCampaign = null }, 800)
  }

  onMount(() => {
    try { onboarding = { ...onboarding, ...JSON.parse(localStorage.getItem('vg-onboarding') || '{}') } } catch {}
    initTheme()
    loadHealth()
    loadNetAudit()
    loadConsent()
    window.addEventListener('vg:open-campaign', onOpenCampaign)
    const interval = setInterval(() => { loadHealth(); loadNetAudit() }, 10000)
    const handleKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (showCommandPalette) {
          showCommandPalette = false
          paletteQuery = ''
        } else {
          openPalette()
        }
      }
      if (e.key === 'Escape') {
        if (showCommandPalette) {
          showCommandPalette = false
          paletteQuery = ''
        }
        // The ledger panel used to trap Escape: it stayed open over the nav
        // and swallowed clicks on the tabs underneath.
        if (showNetPanel) showNetPanel = false
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => {
      clearInterval(interval)
      window.removeEventListener('keydown', handleKey)
      window.removeEventListener('vg:open-campaign', onOpenCampaign)
    }
  })
</script>

<nav class="sticky top-0 z-50 bg-inset/80 backdrop-blur-2xl border-b border-line">
  <div class="max-w-[1280px] mx-auto px-6 min-h-[64px] py-3 flex flex-wrap items-center gap-3">
    <div class="flex items-center gap-3">
      <img src="logo-mark.svg" alt="BrandForge OS" class="w-9 h-9 rounded-xl">
      <div>
        <div class="font-extrabold text-[15px] tracking-tight leading-none text-ink">BRANDFORGE<span style="color:var(--gold)">OS</span></div>
        <div class="text-[11px] tracking-[0.18em] text-faint font-semibold leading-none mt-[2px]">THE MARKETING OS</div>
      </div>
    </div>

    <div class="desktop-status flex flex-wrap items-center gap-2 min-w-0">
      <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-card border border-line text-[11px]">
        <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#10B981]" title="Server reachable"></span>
        <span class="text-mut">{health.provider}</span>
        <span class="text-faint hidden sm:inline">•</span>
        <span class="text-ink font-medium hidden sm:inline">{health.campaigns} campaign{health.campaigns === 1 ? '' : 's'}</span>
      </div>
      <div class="relative">
        <button on:click={() => { showNetPanel = !showNetPanel; loadNetAudit() }}
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[11px] font-medium transition {netAudit.external_requests === 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-amber-500/10 border-amber-500/30 text-amber-300'}"
                aria-expanded={showNetPanel} aria-controls="network-ledger" title="Tracked requests-library calls this session — not a complete network monitor">
          <span class="w-2 h-2 rounded-full {netAudit.external_requests === 0 ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
          {netAudit.external_requests === 0 ? '0 tracked requests' : `${netAudit.external_requests} tracked`}
        </button>
        {#if showNetPanel}
          <div id="network-ledger" class="network-panel absolute left-0 top-[calc(100%+8px)] z-50 w-[320px] p-4 rounded-xl bg-card border border-line shadow-2xl text-[11px]">
            <div class="flex items-center justify-between mb-2">
              <b class="text-ink text-[12px]">Tracked request activity — this session</b>
              <button on:click={() => showNetPanel = false} class="text-faint hover:text-ink" aria-label="Close network ledger">✕</button>
            </div>
            <p class="text-faint leading-relaxed mb-2">Tracked requests-library calls since launch. Hosts only — not URLs, keys or content. Other transports, browser traffic and other processes are not included; zero is not proof of zero network traffic.</p>
            <div class="grid grid-cols-3 gap-2 mb-2 text-center">
              <div class="p-2 rounded-lg bg-inset"><div class="text-[15px] font-extrabold text-ink">{netAudit.total_requests}</div><div class="text-faint">total</div></div>
              <div class="p-2 rounded-lg bg-inset"><div class="text-[15px] font-extrabold text-ink">{netAudit.external_requests}</div><div class="text-faint">external</div></div>
              <div class="p-2 rounded-lg bg-inset"><div class="text-[15px] font-extrabold text-ink">{netAudit.failed || 0}</div><div class="text-faint">failed</div></div>
            </div>
            {#if Object.keys(netAudit.by_host || {}).length}
              <div class="text-faint mb-1">By host:</div>
              {#each Object.entries(netAudit.by_host) as [host, count]}
                <div class="flex justify-between py-0.5"><span class="text-ink">{host}</span><span class="text-faint">×{count}</span></div>
              {/each}
            {:else}
              <div class="text-emerald-300 py-1">No external requests-library calls recorded. ✓</div>
            {/if}
            {#if (netAudit.recent || []).length}
              <div class="text-faint mt-2 mb-1">Recent:</div>
              <div class="max-h-[120px] overflow-auto">
                {#each netAudit.recent.slice(-6).reverse() as e}
                  <div class="flex justify-between py-0.5 text-faint"><span>{e.method} {e.host}</span><span>{e.status || e.error || '—'}</span></div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>
      {#if updateInfo && updateInfo.update_available}
        <a href="https://github.com/nabsan144-hub/brandforge-os/releases" target="_blank" rel="noopener noreferrer"
           class="px-3 py-1.5 rounded-full bg-gold/10 border border-gold/30 text-[11px] text-gold font-medium"
           title="A newer version is available">▲ {updateInfo.latest} available</a>
      {/if}
      <div class="hidden lg:block px-3 py-1.5 rounded-full bg-gold/10 border border-gold/30 text-[11px] text-gold font-medium">{licenseBadge()}</div>
    </div>

    <div class="desktop-actions ml-auto flex shrink-0 items-center gap-2">
      <button on:click={toggleTheme} class="w-8 h-8 rounded-full bg-card border border-line text-mut hover:text-ink hover:border-line transition flex items-center justify-center" title="Toggle light / dark" aria-label="Toggle light or dark theme">
        {#if theme === 'dark'}<Sun class="w-4 h-4" />{:else}<Moon class="w-4 h-4" />{/if}
      </button>
      <!-- mobile affordance for the command palette (was keyboard/⌘K + desktop-only button) -->
      <button on:click={openPalette} class="md:hidden w-8 h-8 rounded-full bg-card border border-line text-mut hover:text-ink transition flex items-center justify-center" aria-label="Open command palette">
        <Command class="w-3.5 h-3.5" />
      </button>
      <button on:click={openPalette} class="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-card border border-line text-[11px] text-mut hover:border-gold/50 transition">
        <Command class="w-3.5 h-3.5" />
        <span class="text-faint">⌘</span><span>K</span>
        <span class="text-faint">Command</span>
      </button>
      <a href="/docs" target="_blank" rel="noopener noreferrer" class="hidden sm:inline-flex px-4 py-2 rounded-full border border-line bg-card text-[13px] font-medium hover:border-white/20 transition">API Docs</a>
    </div>
  </div>
</nav>

<main class="max-w-[1280px] mx-auto px-6">
  {#if updateConsent === null}
    <div class="mt-6 p-4 rounded-xl bg-card border border-line text-[12px] text-mut flex flex-wrap items-center gap-3 justify-center">
      <span>Allow optional GitHub release checks? This controls update checks only; other connected features keep their own settings.</span>
      <button disabled={updateConsentSaving} on:click={() => setUpdateConsent('on')} class="px-3 py-1.5 rounded-full bg-ink text-bg font-bold hover:opacity-90">Yes, check for updates</button>
      <button disabled={updateConsentSaving} on:click={() => setUpdateConsent('off')} class="px-3 py-1.5 rounded-full border border-line font-bold hover:border-gold/50">No update checks</button>
    </div>
  {/if}
  {#if updateConsentError}<p role="alert" class="text-[12px] text-mut my-3">{updateConsentError}</p>{/if}
  <div class="relative py-[72px] text-center overflow-hidden">
    <div class="absolute inset-0 bg-[linear-gradient(to_right,var(--line)_1px,transparent_1px),linear-gradient(to_bottom,var(--line)_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_70%,transparent_110%)] opacity-20"></div>
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-to-b from-gold/10 to-transparent blur-[100px] pointer-events-none"></div>

    <div class="relative">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-card border border-line text-[11px] tracking-wide text-mut mb-6">
        <span class="w-2 h-2 rounded-full bg-gold"></span>
        NO SUBSCRIPTIONS • PRIVATE • OWN FOREVER • OFFLINE
      </div>
      
      <h1 class="text-[clamp(32px,6vw,64px)] leading-[0.92] tracking-[-0.035em] font-[800] mb-5 text-ink">
        Your Local<br>
        <span class="serif font-normal" style="color:var(--gold)">Campaign Workspace.</span>
      </h1>
      
      <p class="text-mut text-[17px] leading-[1.6] max-w-[640px] mx-auto mb-8">
        Draft strategy, copy and visuals <span class="text-ink">in a local review workflow.</span>
        Start with offline templates or connect a supported provider. Review before publishing.
      </p>

      <div class="flex gap-3 justify-center flex-wrap mb-10">
        <button on:click={focusCampaignForm} class="px-6 py-3 rounded-full bg-gold text-bg font-bold text-[14px] hover:opacity-90 transition flex items-center gap-2 hover:-translate-y-px">
          <Rocket class="w-4 h-4" />
          Launch Campaign
        </button>
        <button on:click={() => activeTab = 'chat'} class="px-6 py-3 rounded-full border border-line bg-card text-ink font-medium text-[14px] hover:border-white/20 transition flex items-center gap-2">
          <MessageSquare class="w-4 h-4" />
          Chat with BrandForge
        </button>
      </div>

      <Status {health} />
    </div>
  </div>

  <div class="max-w-[900px] mx-auto mb-8 p-4 rounded-2xl bg-card border border-line">
    <div class="flex items-center justify-between gap-3"><div><b class="text-[13px] text-ink">First campaign checklist</b><p class="text-[11px] text-faint">Complete these steps before delivering work to a client.</p></div><span class="text-[12px] text-gold font-bold">{Object.values(onboarding).filter(Boolean).length}/5</span></div>
    <div class="mt-3 grid sm:grid-cols-5 gap-2">{#each [['brand','Add a brand'],['template','Choose a template'],['campaign','Generate campaign'],['review','Review claims'],['export','Export delivery pack']] as [key,label]}<button on:click={() => toggleOnboarding(key)} class="text-left px-3 py-2 rounded-xl border text-[11px] {onboarding[key] ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-inset border-line text-faint hover:text-ink'}">{onboarding[key] ? '✓ ' : '○ '}{label}</button>{/each}</div>
  </div>

  <div class="max-w-[900px] mx-auto mb-10 hidden md:block">
    <SwarmConstellation />
  </div>

  <div class="flex gap-2 mb-8 p-1 rounded-full bg-card border border-line w-fit mx-auto flex-wrap justify-center max-w-full">
    <button class="px-5 py-2 rounded-full text-[13px] font-semibold transition-all flex items-center gap-1.5 {activeTab === 'swarm' ? 'bg-ink text-bg shadow-lg' : 'text-faint hover:text-ink'}" on:click={() => activeTab = 'swarm'}><Rocket class="w-3.5 h-3.5" /> Create Campaign</button>
    <button class="px-5 py-2 rounded-full text-[13px] font-semibold transition-all flex items-center gap-1.5 {activeTab === 'chat' ? 'bg-ink text-bg shadow-lg' : 'text-faint hover:text-ink'}" on:click={() => activeTab = 'chat'}><MessageSquare class="w-3.5 h-3.5" /> Ask BrandForge</button>
    <button class="px-5 py-2 rounded-full text-[13px] font-semibold transition-all flex items-center gap-1.5 {activeTab === 'campaigns' ? 'bg-ink text-bg shadow-lg' : 'text-faint hover:text-ink'}" on:click={() => activeTab = 'campaigns'}><FolderOpen class="w-3.5 h-3.5" /> My Campaigns</button>
    <button class="px-5 py-2 rounded-full text-[13px] font-semibold transition-all flex items-center gap-1.5 {activeTab === 'settings' ? 'bg-ink text-bg shadow-lg' : 'text-faint hover:text-ink'}" on:click={() => activeTab = 'settings'}><Settings2 class="w-3.5 h-3.5" /> Settings</button>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-[1.3fr_0.7fr] gap-6">
    <div>
      {#if activeTab === 'swarm'}
        <SwarmStudio on:campaignCreated={onCampaignCreated} />
      {:else if activeTab === 'chat'}
        <Chat />
      {:else if activeTab === 'settings'}
        <Settings />
      {:else}
        <Campaigns pending={pendingCampaign} refresh={campaignsKey} />
      {/if}
    </div>
    <div class="space-y-6">
      {#if activeTab === 'swarm'}
        <Chat />
        <Campaigns refresh={campaignsKey} />
      {:else if activeTab === 'chat'}
        <Campaigns refresh={campaignsKey} />
      {:else if activeTab === 'campaigns'}
        <Chat />
      {/if}
      
      <div class="p-5 rounded-2xl bg-card border border-line relative overflow-hidden">
        <div class="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-gold/10 to-transparent blur-2xl"></div>
        <h2 class="font-bold text-[13px] mb-3 flex items-center gap-2"><span class="w-5 h-5 rounded-full bg-gold text-bg flex items-center justify-center text-[11px] font-bold">✓</span> Your Local Workflow</h2>
        <ul class="space-y-2.5 text-[12px] text-ink">
          <li class="flex gap-2.5"><span class="text-emerald-400 mt-[2px]">✓</span> <span><b class="text-ink">Separate ownership</b> — Desktop is a one-time purchase; Cloud access and provider usage are separate</span></li>
          <li class="flex gap-2.5"><span class="text-emerald-400 mt-[2px]">✓</span> <span><b class="text-ink">Your data stays under your control</b> — local mode keeps work on your PC; cloud providers are optional</span></li>
          <li class="flex gap-2.5"><span class="text-emerald-400 mt-[2px]">✓</span> <span><b class="text-ink">Reviewable campaign packs</b> — strategy, copy, visuals and exportable documents</span></li>
          <li class="flex gap-2.5"><span class="text-emerald-400 mt-[2px]">✓</span> <span><b class="text-ink">Keep your local version</b> — review the license and maintenance scope; connected providers have their own costs</span></li>
        </ul>
      </div>
    </div>
  </div>
</main>

{#if showCommandPalette}
  <div class="fixed inset-0 z-[100] bg-black/60 backdrop-blur-xl flex items-start justify-center pt-[20vh]" role="dialog" aria-modal="true" aria-label="Command palette" tabindex="-1" on:click={(e) => { if (e.target === e.currentTarget) { showCommandPalette = false; paletteQuery = '' } }} on:keydown={(e) => e.key === 'Escape' && (showCommandPalette = false)}>
    <div class="w-full max-w-[560px] mx-4 rounded-2xl bg-card border border-line shadow-2xl overflow-hidden" role="document">
      <div class="p-4 border-b border-line flex items-center gap-3">
        <Command class="w-4 h-4 text-faint" />
        <input bind:value={paletteQuery} bind:this={paletteRef} on:keydown={(e) => e.key === 'Enter' && filteredActions()[0] && runPalette(filteredActions()[0].id)} placeholder="Jump to: campaign, chat, settings..." class="flex-1 bg-transparent outline-none text-ink placeholder:text-faint text-[14px]" />
      </div>
      <div class="p-2">
        {#each filteredActions() as a}
          <button type="button" class="w-full text-left px-3 py-2.5 rounded-xl hover:bg-line/40 cursor-pointer text-[13px] text-ink" on:click={() => runPalette(a.id)}>{a.label}</button>
        {/each}
        {#if filteredActions().length === 0}
          <div class="px-3 py-4 text-center text-[12px] text-faint">No matching command</div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<footer class="mt-[80px] border-t border-line py-12">
  <div class="max-w-[1280px] mx-auto px-6 flex flex-col md:flex-row justify-between gap-6 text-[11px] text-faint">
    <div>
      <div class="flex items-center gap-2 mb-2"><img src="logo-mark.svg" alt="" class="w-6 h-6 rounded-lg"><span class="font-bold text-ink">BRANDFORGE OS</span><span class="text-faint ml-2">• The Marketing OS</span></div>
      Your offline marketing department • One-time, from $199 • Own forever • Private
    </div>
    <div class="flex gap-3">
      <span class="px-3 py-1.5 rounded-full bg-card border border-line">No Subscriptions</span>
      <span class="px-3 py-1.5 rounded-full bg-card border border-line">Private & Offline</span>
      <span class="px-3 py-1.5 rounded-full bg-card border border-line">Own Forever</span>
    </div>
  </div>
</footer>
