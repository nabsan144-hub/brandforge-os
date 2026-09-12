<script>
  import { prepareCampaignReference } from './campaign-reference.js'
  import { createEventDispatcher, onMount } from 'svelte'
  import { Rocket, Check, Download, Sparkles, Palette, Ruler } from '@lucide/svelte'
  const dispatch = createEventDispatcher()

  let campaignName = 'My First Campaign'
  let productName = ''
  let industry = ''
  let audience = ''
  let benefits = ''
  let lang = 'en'
  let offer = '', cta = '', destination = ''
  let generateNewLogo = false
  let templates = []
  let selectedTemplate = 'blank'
  let referenceImage = '', shareImageReferences = false, referenceBusy = false, referenceLoad = 0
  async function loadReference(event) {
    const request = ++referenceLoad
    referenceImage = ''; shareImageReferences = false; referenceBusy = true
    try { const file = event.target.files?.[0]; if (file) { const prepared = await prepareCampaignReference(file); if (request === referenceLoad) referenceImage = prepared } }
    catch (e) { if (request === referenceLoad) error = e.message }
    finally { if (request === referenceLoad) referenceBusy = false }
  }
  let noAI = false
  let loading = false
  let result = null
  let error = null
  let progressText = ''

  // NEW: Custom sizes + Branding kit
  let showAdvanced = false
  let customSizes = [] // [{width,height,preset}]
  let selectedPreset = ''
  let customWidth = 300
  let customHeight = 250
  const adPresets = [
    { id: 'medium_rectangle', label: 'Medium Rectangle 300×250 — All devices', w: 300, h: 250 },
    { id: 'leaderboard', label: 'Leaderboard 728×90 — Desktop header', w: 728, h: 90 },
    { id: 'half_page', label: 'Half Page 300×600 — Sidebar high-impact', w: 300, h: 600 },
    { id: 'mobile_banner', label: 'Mobile Banner 320×50 — Mobile', w: 320, h: 50 },
    { id: 'large_rectangle', label: 'Large Rectangle 336×280', w: 336, h: 280 },
    { id: 'wide_skyscraper', label: 'Wide Skyscraper 160×600', w: 160, h: 600 },
    { id: 'billboard', label: 'Billboard 970×250 — Premium', w: 970, h: 250 },
    { id: 'fb_feed', label: 'Facebook Feed 1200×628', w: 1200, h: 628 },
    { id: 'fb_square', label: 'FB/IG Square 1080×1080', w: 1080, h: 1080 },
    { id: 'fb_story', label: 'FB/IG Story 1080×1920 9:16', w: 1080, h: 1920 },
    { id: 'linkedin_feed', label: 'LinkedIn Feed 1200×627', w: 1200, h: 627 },
    { id: 'youtube_thumbnail', label: 'YouTube Thumbnail 1280×720', w: 1280, h: 720 },
    { id: 'logo_square', label: 'Logo Square 1024×1024', w: 1024, h: 1024 },
  ]

  function applyTemplate(id) {
    selectedTemplate = id
    const template = templates.find((item) => item.id === id)
    if (!template || id === 'blank') return
    campaignName = template.campaign_name || campaignName
    productName = template.product_name || productName
    industry = template.industry || industry
    audience = template.target_audience || audience
    benefits = template.key_benefits ?? ''
  }

  function addPreset() {
    if (!selectedPreset) return
    if (customSizes.length >= 21) { error = 'Max 21 requested sizes per run'; return; }
    const p = adPresets.find(x => x.id === selectedPreset)
    if (!p) return
    if (customSizes.find(x => x.preset === p.id)) return
    customSizes = [...customSizes, { width: p.w, height: p.h, preset: p.id }]
  }

  function addCustomSize() {
    const w = parseInt(customWidth,10) || 0
    const h = parseInt(customHeight,10) || 0
    if (w < 50 || w > 5000 || h < 50 || h > 5000) { error = 'Custom size must be 50-5000 px'; return; }
    if (customSizes.length >= 21) { error = 'Max 21 requested sizes per run'; return; }
    customSizes = [...customSizes, { width: w, height: h, preset: '' }]
  }

  function removeSize(idx) {
    customSizes = customSizes.filter((_,i)=>i!==idx)
  }

  onMount(async () => {
    try {
      const response = await fetch('/api/campaign-templates')
      const data = await response.json()
      if (response.ok && Array.isArray(data.templates)) templates = data.templates
    } catch {}
  })

  async function runSwarm() {
    if (!productName.trim()) {
      error = 'Please enter your product or brand name'
      return
    }
    loading = true
    result = null
    error = null
    const requestId = crypto.randomUUID()
    let stopped = false, timer
    const controller = new AbortController()
    async function poll() {
      try {
        const response = await fetch('/api/swarm/progress/' + requestId, {signal: controller.signal})
        if(response.ok && !stopped) {
          const data = await response.json()
          if(!stopped) progressText = Object.entries(data.stages || {}).map(([key, value]) => key + ': ' + value).join(' · ')
        }
      } catch { /* Generation may still be running. */ }
      if(!stopped) timer = setTimeout(poll, 2000)
    }
    progressText = 'Waiting for local engine progress. Reference: ' + requestId
    timer = setTimeout(poll, 500)
    try {
      const payload = { request_id: requestId, no_ai: noAI, 
        campaign_name: campaignName || `${productName} Campaign`, 
        product_name: productName, 
        industry: industry || 'General', 
        target_audience: audience || 'your customers',
        key_benefits: benefits.trim(),
        lang,
        reference_image: referenceImage, share_image_references: shareImageReferences,
        custom_sizes: customSizes, offer, cta, url: destination, generate_new_logo: generateNewLogo
      }
      const res = await fetch('/api/swarm/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.detail || data.error) {
        const detail = typeof data.detail === 'string' ? data.detail : data.detail?.error || data.error
        throw new Error(detail || 'Campaign failed — see the server logs')
      }
      result = data
      dispatch('campaignCreated')
    } catch (e) {
      error = e.message + ' · Reference: ' + requestId + '. Check History before creating another pack.'
    } finally {
      stopped = true; clearTimeout(timer); controller.abort()
    }
    if(result) progressText = 'Saved. Review the result before publishing. Reference: ' + requestId
    loading = false
  }
</script>

<div class="rounded-card bg-card border border-line overflow-hidden">
  <div class="p-6 border-b border-line">
    <div class="flex items-center gap-3 mb-1">
      <div class="w-8 h-8 rounded-full bg-gold text-bg flex items-center justify-center"><Rocket class="w-4 h-4" /></div>
      <h2 class="font-bold text-[15px]">Create Your Campaign</h2>
      <span class="ml-auto px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-bold">6 STAGES • DRAFTS</span>
    </div>
    <p class="text-[12px] text-faint">Start with a clear brief, then receive strategy, copy, visual direction, <b class="text-ink">branding kit (logos)</b> and SEO suggestions in one reviewable campaign pack.</p>
  </div>

  <div class="p-6 space-y-4">
    <div class="p-3 rounded-xl bg-inset border border-line">
      <label for="campaign-template" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 flex items-center gap-1.5"><Sparkles class="w-3.5 h-3.5 text-gold" /> Choose a starter brief</label>
      <select id="campaign-template" bind:value={selectedTemplate} on:change={(event) => applyTemplate(event.currentTarget.value)} class="w-full px-3 py-2.5 rounded-lg border border-line bg-card text-ink text-[13px] outline-none focus:border-gold/50">
        {#each templates as template}
          <option value={template.id}>{template.name} — {template.description}</option>
        {/each}
        {#if templates.length === 0}
          <option value="blank">Start from scratch</option>
        {/if}
      </select>
      <p class="text-[11px] text-faint mt-1.5">Templates are editable starting points. Replace every placeholder with approved client facts before you generate.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="campaign-name-input" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">Campaign Name</label>
        <input id="campaign-name-input" bind:value={campaignName} placeholder="e.g. Summer Launch 2026" class="w-full px-4 py-3 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50 focus:ring-1 focus:ring-gold/20 transition" />
      </div>
      <div>
        <label for="product-name-input" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">Product / Brand Name *</label>
        <input id="product-name-input" bind:value={productName} placeholder="e.g. Apex Coffee, BrandForge OS" class="w-full px-4 py-3 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50 transition" />
      </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="industry-input" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">Industry / Niche</label>
        <input id="industry-input" bind:value={industry} placeholder="e.g. Coffee Shop, SaaS, Retail" class="w-full px-4 py-3 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50 transition" />
      </div>
      <div>
        <label for="audience-input" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">Target Audience</label>
        <input id="audience-input" bind:value={audience} placeholder="e.g. Busy professionals, Store owners" class="w-full px-4 py-3 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50 transition" />
      </div>
      <div>
        <label for="lang-select" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">Campaign Language</label>
        <select id="lang-select" bind:value={lang} class="w-full px-4 py-3 rounded-xl border border-line bg-inset text-ink text-[13px] outline-none focus:border-gold/50 transition">
          <option value="en">English</option>
          <option value="ur">اردو — Urdu</option>
          <option value="hi">हिन्दी — Hindi</option>
          <option value="es">Español</option>
          <option value="pt">Português</option>
        </select>
      </div>
    </div>
    
    <div>
      <label for="benefits-textarea" class="text-[11px] font-semibold text-mut tracking-wide uppercase mb-1.5 block">Key Benefits — What makes you different?</label>
      <textarea id="benefits-textarea" bind:value={benefits} placeholder="e.g. Organic beans, same-day delivery, family-owned since 1990, no monthly fees" class="w-full px-4 py-3 rounded-xl border border-line bg-inset text-ink text-[13px] min-h-[84px] outline-none focus:border-gold/50 transition resize-none"></textarea>
      <p class="text-[11px] text-faint mt-1.5">Separate with commas. Example: Fast, Private, One-time price, Own forever</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div><label for="campaign-offer" class="text-[11px] text-mut">Offer and terms</label><input id="campaign-offer" bind:value={offer} maxlength="200" class="w-full px-4 py-3 rounded-xl bg-inset border border-line" placeholder="Only an offer you can fulfill" /></div>
      <div><label for="campaign-cta" class="text-[11px] text-mut">Call to action</label><input id="campaign-cta" bind:value={cta} maxlength="40" class="w-full px-4 py-3 rounded-xl bg-inset border border-line" placeholder="e.g. See the coffee selection" /></div>
      <div><label for="campaign-url" class="text-[11px] text-mut">Destination URL</label><input id="campaign-url" type="url" bind:value={destination} maxlength="500" class="w-full px-4 py-3 rounded-xl bg-inset border border-line" placeholder="https://your-business.example/offer" /></div>
      <label class="text-[12px] text-mut flex gap-2 items-center"><input type="checkbox" bind:checked={generateNewLogo} /> Also create separate logo concepts, even if this client has an approved logo</label>
    </div>
    <p class="text-[11px] text-faint">Select the client and upload their logo in Settings. The approved logo is used in banners, landing pages and native documents. Template structures support five languages; your supplied fields remain as entered.</p>
    <!-- Advanced: Branding Kit + Custom Sizes -->
    <div class="p-4 rounded-xl bg-inset border border-line">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <Palette class="w-4 h-4 text-gold" />
          <b class="text-[12px] text-ink">Branding Kit + Custom Sizes</b>
          <span class="px-2 py-0.5 rounded-full bg-gold/10 border border-gold/20 text-[10px] text-gold font-bold">PORTABLE SVG + PNG</span>
        </div>
        <button on:click={() => showAdvanced = !showAdvanced} class="text-[11px] font-bold text-gold hover:underline">{showAdvanced ? 'Hide' : 'Show'} options</button>
      </div>
      <p class="text-[11px] text-faint mt-1">Existing client logos stay authoritative. With no approved logo, separate geometric logo concepts are included. SVG type is outlined for portability; copy remains editable. Up to 21 validated extra sizes per run.</p>
      
      {#if showAdvanced}
        <div class="mt-4 space-y-4">
          <div>
            <label class="text-[11px] font-semibold text-mut uppercase tracking-wide flex items-center gap-1.5"><Ruler class="w-3.5 h-3.5" /> Add Preset Ad Size — Google, FB, IG, LinkedIn, YouTube</label>
            <div class="flex gap-2 mt-1.5">
              <select bind:value={selectedPreset} class="flex-1 px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none focus:border-gold/50">
                <option value="">Choose preset...</option>
                {#each adPresets as p}
                  <option value={p.id}>{p.label}</option>
                {/each}
              </select>
              <button on:click={addPreset} class="px-4 py-2 rounded-full bg-ink text-bg text-[11px] font-bold hover:opacity-90">Add preset</button>
            </div>
          </div>
          
          <div>
            <label for="custom-width-input" class="text-[11px] font-semibold text-mut uppercase tracking-wide">Custom Dimensions (50–5000 px)</label>
            <div class="flex gap-2 mt-1.5">
              <input id="custom-width-input" type="number" bind:value={customWidth} min="50" max="5000" placeholder="Width" aria-label="Custom banner width in pixels" class="w-24 px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none" />
              <span class="text-faint text-[12px] py-2">×</span>
              <input type="number" bind:value={customHeight} min="50" max="5000" placeholder="Height" aria-label="Custom banner height in pixels" class="w-24 px-3 py-2 rounded-lg border border-line bg-card text-ink text-[12px] outline-none" />
              <button on:click={addCustomSize} class="px-4 py-2 rounded-full border border-line text-[11px] font-bold hover:border-gold/50">Add custom</button>
            </div>
            <p class="text-[11px] text-faint mt-1">Choose up to 21 extra sizes in total using custom dimensions or the listed presets. Review each platform’s current requirements.</p>
          </div>

          {#if customSizes.length > 0}
            <div class="space-y-1.5">
              <b class="text-[11px] text-ink">Selected sizes ({customSizes.length}/21):</b>
              {#each customSizes as s, idx}
                <div class="flex items-center justify-between px-3 py-1.5 rounded-lg bg-card border border-line text-[11px]">
                  <span class="text-ink">{s.preset || 'custom'} — {s.width}×{s.height}</span>
                  <button on:click={() => removeSize(idx)} class="text-red-300 hover:underline">Remove</button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
    
    <div class="p-3 rounded-xl border border-line space-y-2">
      <label class="text-sm block" for="campaign-reference">Product reference (optional PNG/JPEG; Gemini or OpenAI)</label>
      <input id="campaign-reference" type="file" accept="image/png,image/jpeg" on:change={loadReference} disabled={loading || noAI} class="text-sm max-w-full" />
      {#if referenceImage}<img src={referenceImage} alt="Prepared product reference" class="max-w-full h-28 object-contain" /><button type="button" on:click={() => { referenceLoad++; referenceImage = ''; shareImageReferences = false; referenceBusy = false }} class="text-sm underline">Remove reference</button>{/if}
      <label class="flex gap-2 text-sm"><input type="checkbox" bind:checked={shareImageReferences} disabled={loading || noAI || referenceBusy}> I have permission to use these images and consent to sending this reference and my saved approved client logo, if present, to the image provider selected in Settings.</label>
      <p class="text-[11px] text-faint">Images are prepared locally first. Provider fees and terms apply. Review likeness, packaging, spelling and claims before publishing. Reference sharing is off for no-AI campaigns.</p>
    </div>
    <label class="flex items-center gap-2 text-sm"><input id="campaign-no-ai" type="checkbox" bind:checked={noAI} on:change={() => { if (noAI) { referenceLoad++; referenceImage = ''; shareImageReferences = false; referenceBusy = false } }}> Use no AI providers for this campaign (including images and live search)</label>
    <p class="text-[11px] text-faint">Otherwise, this campaign uses Settings: connected text providers receive the brief and brand context; configured keyed image providers receive design inputs for three AI advertisements. Failed AI artwork is not replaced silently with basic designs. Image lettering is raster; Canvas lets you add editable layers. Live search may share product/industry queries. Stored work remains local, but connected prompts leave this PC.</p>
    <p class="text-sm text-mut my-3 break-words" role="status" aria-live="polite">{progressText}</p>
    <button on:click={runSwarm} disabled={loading || referenceBusy} class="w-full py-3.5 rounded-full bg-ink text-bg font-bold text-[14px] disabled:opacity-50 hover:opacity-90 hover:translate-y-[-1px] transition-all flex items-center justify-center gap-2">
      {#if loading}
        <span class="w-4 h-4 border-2 border-bg/30 border-t-bg rounded-full animate-spin"></span>
        Creating your campaign...
      {:else}
        Create My Campaign →
      {/if}
    </button>

    <p class="text-[11px] text-center text-faint">Local-first • AI: three advertisement formats • Basic layouts: logo concepts and up to 21 extra sizes</p>

    {#if error}
      <div role="alert" class="p-3 rounded-xl bg-card border border-line text-[12px] text-red-300">{error}</div>
    {/if}

    {#if result}
      <div class="p-4 rounded-xl bg-inset border border-emerald-900/50">
        <div class="flex items-center gap-2 mb-3">
          <span class="w-7 h-7 rounded-full bg-emerald-500 flex items-center justify-center text-bg"><Check class="w-4 h-4" /></span>
          <div class="min-w-0">
            <b class="text-ink text-[13px] block truncate">{result.campaign_name} · Draft saved</b>
            <span class="text-[11px] text-faint">{result.deliverables?.length} files created — {result.meta?.ai_image ? 'three AI advertisement formats with portable Canvas source' : 'basic layouts and brand assets'}</span>
          </div>
          <span class="ml-auto px-2 py-1 rounded-full border text-[11px] font-bold {result.research_live ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-gold/10 border-gold/30 text-gold'}">
            {result.research_live ? 'LIVE RESEARCH' : 'NO LIVE RESEARCH'}
          </span>
        </div>
        {#if result.quality}
          <div class="flex items-center gap-3 mb-3 p-2.5 rounded-lg border {result.quality.status === 'ready_for_internal_review' ? 'bg-emerald-500/5 border-emerald-500/30' : 'bg-amber-500/5 border-amber-500/30'}">
            <span class="text-[22px] font-extrabold leading-none {result.quality.status === 'ready_for_internal_review' ? 'text-emerald-300' : 'text-amber-300'}">{result.quality.score}<span class="text-[11px] text-faint font-semibold">/100</span></span>
            <div class="text-[11px] leading-snug min-w-0">
              <b class="text-ink block">Automated draft checks {result.quality.status === 'ready_for_internal_review' ? '— ready for internal review' : '— needs revision before review'}</b>
              <span class="text-faint">{result.claim_review?.warning_count || 0} claim-guard warning{(result.claim_review?.warning_count || 0) === 1 ? '' : 's'} · review claims before publishing; not an aesthetic or sales-quality score</span>
            </div>
          </div>
        {/if}
        {#if result.provider === 'offline'}
          <p class="text-[11px] text-amber-300/90 bg-amber-500/5 border border-amber-500/20 rounded-lg p-2.5 mb-3 leading-relaxed">Offline template text is draft content without a text-model charge. Connected providers receive your brief and brand context; their terms and fees apply. Every result needs review. Text and image settings are separate.</p>
        {/if}
        <div class="grid grid-cols-3 gap-2 mb-3">
          {#each result.deliverables || [] as file}
            <div class="p-2 rounded-lg bg-card border border-line text-[11px] text-mut text-center truncate">{file}</div>
          {/each}
        </div>
        <div class="p-3 rounded-lg bg-card border border-line text-[11px] text-ink leading-relaxed mb-3">
          <b class="text-ink text-[11px] uppercase tracking-wide">Strategy Preview:</b><br>
          {result.strategy_preview?.slice(0, 400)}{result.strategy_preview?.length > 400 ? '…' : ''}
        </div>
        <div class="flex gap-2">
          <button on:click={() => window.dispatchEvent(new CustomEvent("vg:open-campaign", { detail: result.campaign_name }))} class="flex-1 text-center py-2 rounded-full bg-ink text-bg text-[12px] font-bold hover:opacity-90 transition">View Campaign</button>
          <a href={`/api/campaigns/${result.campaign_name}/download`} class="flex-1 text-center py-2 rounded-full border border-line text-[12px] font-bold hover:border-white/30 transition flex items-center justify-center gap-1.5"><Download class="w-3.5 h-3.5" /> Download ZIP</a>
        </div>
        <p class="text-[11px] text-faint text-center mt-2">Full report in "My Campaigns" tab — strategy, copy, SEO, visuals, branding kit (logos).</p>
      </div>
    {/if}
  </div>
</div>
