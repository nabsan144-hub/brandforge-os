<script>
  import { onMount } from 'svelte'
  import { FolderOpen } from '@lucide/svelte'
  import { mdToHtml } from './markdown.js'

  let campaigns = []
  let loading = true
  let selected = null
  let detail = null
  let detailTab = 'strategy'
  let detailLoading = false
  let editSection = '', editText = '', editMessage = '', textSaving = false

  // Phase 4 export gate: offline-generated campaigns are draft quality;
  // exports unlock per-campaign after an explicit "I reviewed this" click.
  let exportAcked = {}
  try { exportAcked = JSON.parse(localStorage.getItem('bf-export-ack') || '{}') || {} } catch { exportAcked = {} }
  function ackExport() {
    exportAcked = { ...exportAcked, [selected]: true }
    try { localStorage.setItem('bf-export-ack', JSON.stringify(exportAcked)) } catch {}
  }
  $: needsReview = !!detail && !!selected && (detail.provider || 'offline') === 'offline' && !exportAcked[selected]

  // Phase 6: manual performance loop + approval inbox
  let perf = { entries: [], summary: null }
  let perfForm = { spend: '', clicks: '', leads: '', revenue: '', note: '' }
  let perfMsg = ''
  let approvals = []
  async function loadPerformance() {
    if (!selected) return
    try { perf = await (await fetch(`/api/campaigns/${encodeURIComponent(selected)}/performance`)).json() } catch {}
  }
  async function submitPerformance() {
    perfMsg = ''
    try {
      const res = await fetch(`/api/campaigns/${encodeURIComponent(selected)}/performance`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          spend: Number(perfForm.spend) || 0, clicks: Number(perfForm.clicks) || 0,
          leads: Number(perfForm.leads) || 0, revenue: Number(perfForm.revenue) || 0,
          note: perfForm.note }) })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) { perfMsg = data.detail?.[0]?.msg || data.detail || 'Could not save entry'; return }
      perfForm = { spend: '', clicks: '', leads: '', revenue: '', note: '' }
      perfMsg = 'Saved ✓'
      loadPerformance()
    } catch { perfMsg = 'Could not save entry' }
  }
  async function loadApprovals() {
    try { approvals = (await (await fetch('/api/approvals')).json()).approvals || [] } catch { approvals = [] }
  }
  let statusSaving = false
  let approvalLink = ''
  const statuses = [
    ['draft', 'Draft'], ['internal_review', 'Internal Review'], ['ready_for_client', 'Ready for Client'],
    ['changes_requested', 'Changes Requested'], ['approved', 'Approved'], ['delivered', 'Delivered'],
  ]
  export let pending = null
  export let refresh = 0
  $: if (refresh) load()
  $: if (pending) open(pending)

  let listError = ''
  let openRequest = 0
  const messageFrom = (data, fallback) => {
    if (typeof data?.detail === 'string') return data.detail
    if (data?.detail && typeof data.detail === 'object') return data.detail.error || data.detail.message || fallback
    return data?.error || fallback
  }

  async function load() {
    loading = true
    listError = ''
    try {
      const res = await fetch('/api/campaigns')
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(messageFrom(data, 'Could not load campaigns'))
      campaigns = data.campaigns || []
    } catch (error) {
      campaigns = []
      listError = error.message
    }
    loading = false
  }

  async function open(name) {
    const requestId = ++openRequest
    selected = name
    detail = null
    detailLoading = true
    detailTab = 'strategy'
    editSection = ''
    try {
      const res = await fetch(`/api/campaigns/${encodeURIComponent(name)}`)
      const data = await res.json().catch(() => ({}))
      if (requestId !== openRequest) return
      if (!res.ok) throw new Error(messageFrom(data, 'Campaign not found'))
      detail = data
      loadPerformance()
      loadApprovals()
    } catch (e) {
      if (requestId !== openRequest) return
      detail = { error: e.message }
    }
    if (requestId === openRequest) detailLoading = false
  }

  function hasFile(name) {
    if (!detail) return false
    return (detail.files || []).some(f => f.name === name || f.name.endsWith(name))
  }

  function downloadUrl(name) {
    return `/api/campaigns/${encodeURIComponent(name)}/download`
  }

  function fileUrl(name, fname) {
    return `/api/campaigns/${encodeURIComponent(name)}/files/${encodeURIComponent(fname)}`
  }

  async function createApprovalLink() {
    if (!selected || statusSaving) return
    statusSaving = true
    try {
      const response = await fetch(`/api/campaigns/${encodeURIComponent(selected)}/approval-links`, { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(messageFrom(data, 'Could not create an approval link'))
      approvalLink = data.url
      loadApprovals()
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(data.url)
    } catch (error) {
      detail = { ...detail, status_error: error.message }
    }
    statusSaving = false
  }

  function statusLabel(status) {
    return (statuses.find(([value]) => value === status) || ['draft', 'Draft'])[1]
  }

  async function updateStatus(status) {
    if (!selected || statusSaving) return
    statusSaving = true
    try {
      const response = await fetch(`/api/campaigns/${encodeURIComponent(selected)}/status`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(messageFrom(data, 'Could not update status'))
      detail = { ...detail, status: data.status, status_history: data.status_history }
      campaigns = campaigns.map((campaign) => campaign.name === selected ? { ...campaign, status: data.status } : campaign)
    } catch (error) {
      detail = { ...detail, status_error: error.message }
    }
    statusSaving = false
  }

  async function createRevision() {
    if (!selected || statusSaving) return
    statusSaving = true
    try {
      const response = await fetch(`/api/campaigns/${encodeURIComponent(selected)}/revisions`, { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(messageFrom(data, 'Could not create revision'))
      await load()
      await open(data.name)
    } catch (error) {
      detail = { ...detail, status_error: error.message }
    }
    statusSaving = false
  }

  function timeAgo(iso) {
    if (!iso) return ''
    const d = new Date(iso)
    const mins = Math.floor((Date.now() - d.getTime()) / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return d.toLocaleDateString()
  }

  function brandingFiles() {
    if (!detail) return []
    return (detail.files || []).filter(f => f.name.startsWith('branding/') || f.name.includes('logo'))
  }

  function customBanners() {
    if (!detail) return []
    return (detail.files || []).filter(f => f.name.startsWith('banner_') && f.name.endsWith('.svg'))
  }

  function beginEdit(section) {
    editSection=section
    editText=section==='strategy'?(detail.strategy?.strategy_text||''):section==='copy'?(detail.copy?.copy_text||''):(detail.analysis?.seo_analysis||'')
    editMessage=''
  }
  async function saveTextRevision() {
    textSaving=true; editMessage=''
    try {
      const r=await fetch(`/api/campaigns/${encodeURIComponent(selected)}/text-revision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({[editSection]:editText})})
      const d=await r.json();if(!r.ok)throw new Error(messageFrom(d,'Could not save text'))
      editSection='';await load();await open(d.name);editMessage='Saved as a new draft. The original and its approvals are unchanged; visuals were not regenerated.'
    } catch(e) {editMessage=e.message} finally {textSaving=false}
  }
  async function copySection() {
    const text=detailTab==='strategy'?detail.strategy?.strategy_text:detailTab==='copy'?detail.copy?.copy_text:detail.analysis?.seo_analysis
    try {await navigator.clipboard.writeText(text||'');editMessage='Section copied.'}catch{editMessage='Clipboard access blocked; select and copy the text manually.'}
  }

  onMount(load)
</script>

<div class="rounded-[20px] bg-card border border-line overflow-hidden">
  <div class="p-5 border-b border-line flex justify-between items-center">
    <div class="flex items-center gap-2.5">
      <div class="w-8 h-8 rounded-xl bg-ink text-bg flex items-center justify-center"><FolderOpen class="w-4 h-4" /></div>
      <div><h3 class="font-bold text-[14px]">My Campaigns</h3><p class="text-[11px] text-faint">All private, on your machine — includes branding kit</p></div>
    </div>
    <div class="flex items-center gap-2">
      {#if selected}<button on:click={() => { openRequest += 1; selected = null; detail = null; detailLoading = false }} class="px-3 py-1.5 rounded-full bg-inset border border-line text-[11px] text-mut hover:text-ink transition">← All</button>{/if}
      <button on:click={load} aria-label="Refresh campaigns" title="Refresh" class="w-8 h-8 rounded-full bg-inset border border-line flex items-center justify-center hover:border-white/20 transition text-[12px]">↻</button>
    </div>
  </div>

  {#if !selected}
    <div class="p-3">
      {#if loading}
        <div class="p-8 text-center"><div class="w-5 h-5 border-2 border-line border-t-ink rounded-full animate-spin mx-auto mb-2"></div><div class="text-[12px] text-faint">Loading...</div></div>
      {:else if listError}
        <div class="p-8 text-center text-[12px] text-red-300">{listError}</div>
      {:else if campaigns.length === 0}
        <div class="p-8 text-center">
          <div class="w-12 h-12 rounded-2xl bg-inset border border-line flex items-center justify-center mx-auto mb-3"><FolderOpen class="w-5 h-5 text-faint" /></div>
          <div class="text-[13px] text-ink font-medium mb-1">No campaigns yet</div>
          <div class="text-[11px] text-faint leading-relaxed max-w-[320px] mx-auto">Create your first — 6 stages build strategy, copy, banners, landing page, branding kit (logos), custom sizes & conversion suggestions. Local-first and yours to export.</div>
        </div>
      {:else}
        <div class="space-y-2">
          {#each campaigns as c}
            <button on:click={() => open(c.name)} class="w-full group p-3 rounded-xl bg-inset border border-line hover:border-gold/40 hover:bg-card transition text-left">
              <div class="flex justify-between items-start gap-3">
                <div class="flex gap-3 min-w-0">
                  <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-gold flex items-center justify-center text-bg font-bold text-[12px] flex-shrink-0">{(c.product || c.name || '?')[0]?.toUpperCase()}</div>
                  <div class="min-w-0">
                    <b class="text-[13px] text-ink group-hover:text-gold transition truncate block">{c.product || c.name}</b>
                    <span class="text-[11px] text-faint truncate block">{c.name} • v{c.revision_number || 1} • {c.files} files — branding kit ✓</span>
                    <span class="text-[11px] text-faint block">{timeAgo(c.created)}{c.client_id && c.client_id !== 'default' ? ` • ${c.client_id}` : ''}</span>
                  </div>
                </div>
                <span class="text-[11px] px-2 py-1 rounded-full border flex-shrink-0 {c.status === 'approved' || c.status === 'delivered' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : c.status === 'changes_requested' ? 'bg-red-500/10 border-red-500/20 text-red-300' : 'bg-gold/10 border-gold/20 text-gold'}">{statusLabel(c.status)}</span>
              </div>
            </button>
          {/each}
        </div>
        <div class="mt-3 p-2.5 rounded-xl bg-inset border border-line text-[11px] text-faint text-center">
          {campaigns.length} campaign{campaigns.length !== 1 ? 's' : ''} • stored in output/campaigns/ • branding kit + custom sizes included
        </div>
      {/if}
    </div>
  {:else}
    <div class="p-4">
      {#if detailLoading}
        <div class="p-8 text-center"><div class="w-5 h-5 border-2 border-line border-t-ink rounded-full animate-spin mx-auto"></div></div>
      {:else if detail && detail.error}
        <div class="p-6 text-center text-[12px] text-red-300">Could not load campaign: {detail.error}</div>
      {:else if detail}
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <span class="px-2.5 py-1 rounded-full bg-inset border border-line text-[11px] text-mut">{(detail.strategy || {}).industry || '—'}</span>
          <span class="px-2.5 py-1 rounded-full bg-inset border border-line text-[11px] text-mut">engine: {(detail.provider || 'offline')}</span>
          <span class="px-2.5 py-1 rounded-full border text-[11px] {(detail.research_live) ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-gold/10 border-gold/20 text-amber-400'}">
            {(detail.research_live) ? 'live research' : 'no live research'}
          </span>
          <span class="text-[11px] text-faint">v{detail.revision_number || 1}</span>
          <span class="px-2 py-1 rounded-full bg-gold/10 border border-gold/20 text-[10px] text-gold font-bold">BRANDING KIT ✓</span>
          <button on:click={createRevision} disabled={statusSaving} class="px-3 py-1.5 rounded-full border border-line text-[11px] font-semibold text-mut hover:text-ink hover:border-gold/50 disabled:opacity-50">Duplicate as revision</button>
          <button on:click={createApprovalLink} disabled={statusSaving} class="px-3 py-1.5 rounded-full border border-line text-[11px] font-semibold text-mut hover:text-ink hover:border-gold/50 disabled:opacity-50">Create approval link</button>
          <label class="flex items-center gap-2 text-[11px] text-faint">Status
            <select value={detail.status || 'draft'} disabled={statusSaving} on:change={(event) => updateStatus(event.currentTarget.value)} class="px-2 py-1.5 rounded-full border border-line bg-inset text-ink text-[11px] outline-none focus:border-gold/50 disabled:opacity-50">
              {#each statuses as [value, label]}<option value={value}>{label}</option>{/each}
            </select>
          </label>
          {#if needsReview}
            <!-- Phase 4: offline mode is draft-quality by design; exporting
                 requires an explicit per-campaign review acknowledgment so
                 raw template output never ships unreviewed. -->
            <button on:click={ackExport} title="Offline template output can contain rough claims — one click confirms a human read it"
                    class="px-3 py-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 text-[11px] font-bold text-amber-300 hover:border-amber-400 transition">
              ✓ I reviewed this content — enable exports
            </button>
          {:else}
            <a href={`/api/campaigns/${encodeURIComponent(selected)}/export.pdf`} class="px-3 py-1.5 rounded-full border border-line text-[11px] font-bold hover:border-gold/50">PDF</a>
            <a href={`/api/campaigns/${encodeURIComponent(selected)}/export.docx`} class="px-3 py-1.5 rounded-full border border-line text-[11px] font-bold hover:border-gold/50">DOCX</a>
            <a href={downloadUrl(selected)} class="px-3 py-1.5 rounded-full bg-ink text-bg text-[11px] font-bold hover:opacity-90 transition">⬇ ZIP</a>
          {/if}
        </div>

        {#if detail.status_error}<p class="mb-3 text-[11px] text-red-300">{detail.status_error}</p>{/if}
        {#if approvalLink}<div class="mb-3 p-2.5 rounded-xl bg-emerald-500/5 border border-emerald-500/30 text-[11px] text-emerald-200 break-all">Approval link copied: <a class="underline" href={approvalLink} target="_blank" rel="noopener noreferrer">{approvalLink}</a></div>{/if}

        <div class="flex gap-2 mb-4 p-1 rounded-full bg-inset border border-line w-fit flex-wrap">
          {#each ['strategy', 'copy', 'seo', 'results', 'visuals', 'branding', 'custom'] as t}
            <button class="px-4 py-1.5 rounded-full text-[12px] font-semibold transition-all {detailTab === t ? 'bg-ink text-bg' : 'text-faint hover:text-ink'}" on:click={() => detailTab = t}>{t}</button>
          {/each}
        </div>

        {#if ['strategy','copy','seo'].includes(detailTab)}
          <div class="flex flex-wrap gap-2 mb-3"><button class="px-3 py-2 rounded-full border border-line text-[12px]" on:click={copySection}>Copy section</button><button class="px-3 py-2 rounded-full bg-gold text-bg text-[12px] font-bold" on:click={() => beginEdit(detailTab)}>Edit as new revision</button></div>
        {/if}
        {#if editMessage}<p role="status" class="text-[12px] text-mut mb-3">{editMessage}</p>{/if}
        {#if editSection}
          <label for="draft-editor" class="text-[12px] text-mut">Edit {editSection} (up to 20,000 characters)</label>
          <textarea id="draft-editor" bind:value={editText} maxlength="20000" rows="14" dir={detail.lang==='ur'?'rtl':'auto'} class="w-full p-4 rounded-xl bg-inset border border-line text-ink"></textarea>
          <p class="text-[11px] text-faint">A new draft revision will be created. Visuals stay unchanged; generate again to redesign them.</p>
          <div class="flex gap-2 my-3"><button disabled={textSaving} on:click={saveTextRevision} class="px-4 py-2 bg-gold text-bg rounded-full font-bold">Save new draft</button><button on:click={() => editSection=''} class="px-4 py-2 border border-line rounded-full">Discard edits</button></div>
        {/if}
        {#if detailTab === 'strategy'}
          <div class="space-y-3">
            <div class="p-4 rounded-xl bg-inset border border-line text-[13px] leading-[1.7] text-ink markdown">
              {@html mdToHtml((detail.strategy || {}).strategy_text || 'No strategy text')}
            </div>
            <div class="p-4 rounded-xl bg-inset border border-line">
              <b class="text-[11px] uppercase tracking-wide text-faint">Market research</b>
              <p class="text-[12px] text-ink mt-1.5 whitespace-pre-wrap leading-relaxed">{(detail.strategy || {}).market_research || 'None'}</p>
            </div>
          </div>
        {:else if detailTab === 'copy'}
          <div class="p-4 rounded-xl bg-inset border border-line text-[13px] leading-[1.7] text-ink markdown">
            {@html mdToHtml((detail.copy || {}).copy_text || 'No copy')}
          </div>
        {:else if detailTab === 'seo'}
          <div class="space-y-3">
            <div class="p-4 rounded-xl bg-inset border border-line text-[13px] leading-[1.7] text-ink markdown">
              {@html mdToHtml(((detail.analysis || {}).seo_analysis || (detail.copy || {}).seo_analysis || (detail.strategy || {}).seo_analysis || 'No SEO analysis'))}
            </div>
            {#if (detail.analysis || {}).quality_score}
              {@const quality = (detail.analysis || {}).quality_score}
              <div class="p-4 rounded-xl border {quality.status === 'ready_for_internal_review' ? 'bg-emerald-500/5 border-emerald-500/30' : 'bg-amber-500/5 border-amber-500/30'}">
                <div class="flex items-center justify-between gap-3">
                  <div><b class="text-[12px] text-ink">Campaign Quality Score</b><p class="text-[10.5px] text-faint mt-0.5">{quality.status === 'ready_for_internal_review' ? 'Ready for internal review' : 'Needs revision before review'}</p></div>
                  <span class="text-[22px] font-extrabold {quality.status === 'ready_for_internal_review' ? 'text-emerald-300' : 'text-amber-300'}">{quality.score}/100</span>
                </div>
                {#if quality.next_steps?.length}
                  <ul class="mt-3 space-y-1 text-[11px] text-ink">{#each quality.next_steps as step}<li>• {step}</li>{/each}</ul>
                {/if}
              </div>
            {/if}
          </div>
        {:else if detailTab === 'results'}
          <div class="space-y-4">
            <div class="p-3 rounded-xl bg-inset border border-line text-[11px] text-faint leading-relaxed">
              Enter what actually happened after publishing (spend, clicks, leads, revenue).
              Manual by design — no pixels, nothing leaves your machine. The app shows the real
              ROI next to the AI's quality score so you can see whether the output earned its keep.
            </div>
            {#if perf.summary && perf.summary.entries}
              {@const s = perf.summary}
              <div class="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
                <div class="p-2.5 rounded-xl bg-inset border border-line"><div class="text-[15px] font-extrabold text-ink">${s.spend}</div><div class="text-[10px] text-faint">spend</div></div>
                <div class="p-2.5 rounded-xl bg-inset border border-line"><div class="text-[15px] font-extrabold text-ink">${s.revenue}</div><div class="text-[10px] text-faint">revenue</div></div>
                <div class="p-2.5 rounded-xl bg-inset border border-line"><div class="text-[15px] font-extrabold {s.profit >= 0 ? 'text-emerald-300' : 'text-red-300'}">${s.profit}</div><div class="text-[10px] text-faint">profit</div></div>
                <div class="p-2.5 rounded-xl bg-inset border border-line"><div class="text-[15px] font-extrabold text-ink">{s.roas ?? '—'}×</div><div class="text-[10px] text-faint">ROAS</div></div>
                <div class="p-2.5 rounded-xl bg-inset border border-line"><div class="text-[15px] font-extrabold text-ink">{s.roi_pct ?? '—'}%</div><div class="text-[10px] text-faint">ROI</div></div>
                <div class="p-2.5 rounded-xl bg-inset border border-line"><div class="text-[15px] font-extrabold text-ink">{s.cpl ?? '—'}</div><div class="text-[10px] text-faint">cost/lead</div></div>
              </div>
              {#if (perf.quality)}<p class="text-[11px] text-faint">Generated with engine <b class="text-mut">{perf.provider}</b> · AI quality score <b class="text-mut">{perf.quality.score}/100</b> — compare against the numbers above.</p>{/if}
            {:else}
              <p class="text-[12px] text-faint">No results recorded yet.</p>
            {/if}
            <form on:submit={(e) => { e.preventDefault(); submitPerformance() }} class="grid grid-cols-2 sm:grid-cols-5 gap-2">
              <input bind:value={perfForm.spend} type="number" min="0" step="0.01" placeholder="Spend $" class="px-3 py-2 rounded-lg border border-line bg-inset text-ink text-[12px] outline-none focus:border-gold/50" />
              <input bind:value={perfForm.clicks} type="number" min="0" placeholder="Clicks" class="px-3 py-2 rounded-lg border border-line bg-inset text-ink text-[12px] outline-none focus:border-gold/50" />
              <input bind:value={perfForm.leads} type="number" min="0" placeholder="Leads" class="px-3 py-2 rounded-lg border border-line bg-inset text-ink text-[12px] outline-none focus:border-gold/50" />
              <input bind:value={perfForm.revenue} type="number" min="0" step="0.01" placeholder="Revenue $" class="px-3 py-2 rounded-lg border border-line bg-inset text-ink text-[12px] outline-none focus:border-gold/50" />
              <button class="px-3 py-2 rounded-lg bg-ink text-bg text-[12px] font-bold hover:opacity-90">Add entry</button>
              <input bind:value={perfForm.note} placeholder="Note (optional)" class="col-span-2 sm:col-span-4 px-3 py-2 rounded-lg border border-line bg-inset text-ink text-[12px] outline-none focus:border-gold/50" />
              {#if perfMsg}<span class="text-[11px] {perfMsg.includes('✓') ? 'text-emerald-300' : 'text-red-300'} self-center">{perfMsg}</span>{/if}
            </form>
            {#if perf.entries?.length}
              <div class="space-y-1.5">
                {#each [...perf.entries].reverse() as e}
                  <div class="flex flex-wrap gap-2 p-2 rounded-lg bg-inset border border-line text-[11px] text-mut">
                    <span>{String(e.at).slice(0, 10)}</span>
                    <span>${e.spend} → ${e.revenue}</span>
                    <span>{e.clicks} clicks · {e.leads} leads</span>
                    {#if e.note}<span class="text-faint">“{e.note}”</span>{/if}
                  </div>
                {/each}
              </div>
            {/if}
            {#if approvals.filter(a => a.campaign === selected).length}
              <div>
                <b class="text-[12px] text-ink block mb-2">Client review links for this campaign</b>
                <div class="space-y-1.5">
                  {#each approvals.filter(a => a.campaign === selected) as a}
                    <div class="flex flex-wrap items-center gap-2 p-2 rounded-lg bg-inset border border-line text-[11px]">
                      <span class="px-2 py-0.5 rounded-full border {a.decision === 'approved' ? 'border-emerald-500/30 text-emerald-300' : a.decision === 'changes_requested' ? 'border-red-400/30 text-red-300' : 'border-gold/30 text-gold'}">{String(a.decision).replace('_', ' ')}</span>
                      <span class="text-faint">{String(a.created).slice(0, 10)} · {a.comment_count} comment{a.comment_count === 1 ? '' : 's'}</span>
                      {#if a.last_comment}<span class="text-mut truncate">“{a.last_comment}”</span>{/if}
                      {#if a.token}<a href={`/approval/${a.token}`} target="_blank" rel="noopener noreferrer" class="ml-auto text-gold hover:underline">Open portal</a>{/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {:else if detailTab === 'branding'}
          <div class="space-y-4">
            <div class="p-3 rounded-xl bg-gold/5 border border-gold/20 text-[11px] text-ink">
              <b class="text-gold">Branding Kit — High-End Design — Logos etc.</b> — Every campaign includes full branding kit: primary logo (combination), reversed (white on dark), icon-only (lettermark), wordmark, lettermark, abstract, emblem, favicon 512, social avatar 500, color_palette.json, brand_guidelines.md, logo_usage.md — offline, no API key, custom colors, review before publishing. Convert SVG to PNG for favicon 32x32, 16x16, avatar PNG as needed.
            </div>
            {#each brandingFiles() as f}
              <div>
                <div class="flex items-center justify-between mb-2">
                  <b class="text-[11px] uppercase tracking-wide text-faint">{f.name}</b>
                  <a href={fileUrl(selected, f.name)} target="_blank" rel="noopener noreferrer" class="text-[11px] text-gold hover:underline">open</a>
                </div>
                {#if f.name.endsWith('.svg')}
                  <div class="rounded-xl overflow-hidden border border-line bg-inset p-4 flex items-center justify-center">
                    <img src={fileUrl(selected, f.name)} alt={f.name} class="max-w-[240px] h-auto" />
                  </div>
                {:else}
                  <div class="p-3 rounded-xl bg-inset border border-line text-[11px] text-ink whitespace-pre-wrap max-h-[300px] overflow-auto">{f.content?.slice(0,2000)}</div>
                {/if}
              </div>
            {/each}
            {#if brandingFiles().length === 0}
              <p class="text-[11px] text-faint">No branding files — generate a new campaign to include branding kit.</p>
            {/if}
          </div>
        {:else if detailTab === 'custom'}
          <div class="space-y-4">
            <div class="p-3 rounded-xl bg-inset border border-line text-[11px] text-faint">
              Custom sizes — when a campaign needs a different ad size. Supports 50–5000 px + presets: medium_rectangle 300×250 (80% inventory), leaderboard 728×90, half_page 300×600, mobile_banner 320×50, fb_feed 1200×628, fb_square 1080×1080, fb_story 1080×1920 9:16, linkedin 1200×627, youtube 1280×720, plus any custom.
            </div>
            {#each customBanners() as f}
              <div>
                <div class="flex items-center justify-between mb-2">
                  <b class="text-[11px] uppercase tracking-wide text-faint">{f.name}</b>
                  <a href={fileUrl(selected, f.name)} target="_blank" rel="noopener noreferrer" class="text-[11px] text-gold hover:underline">open</a>
                </div>
                <div class="rounded-xl overflow-hidden border border-line bg-inset">
                  <img src={fileUrl(selected, f.name)} alt={f.name} class="w-full h-auto" />
                </div>
              </div>
            {/each}
            {#if customBanners().length === 0}
              <p class="text-[11px] text-faint">No custom sizes in this campaign — add presets or custom width×height in Create tab Advanced options. Every campaign still includes default hero 1200×630 + instagram 1080×1080.</p>
            {/if}
          </div>
        {:else}
          <div class="space-y-4">
            {#each ['hero_ai.png', 'hero_ai.jpg', 'hero_banner.svg', 'hero_image.jpg', 'instagram_ai.png', 'instagram_ai.jpg', 'instagram_square.svg', 'instagram_image.jpg'] as fname}
              {#if hasFile(fname)}
                <div>
                  <div class="flex items-center justify-between mb-2">
                    <b class="text-[11px] uppercase tracking-wide text-faint">{fname}</b>
                    <a href={fileUrl(selected, fname)} target="_blank" rel="noopener noreferrer" class="text-[11px] text-gold hover:underline">open</a>
                  </div>
                  <div class="rounded-xl overflow-hidden border border-line bg-inset">
                    <img src={fileUrl(selected, fname)} alt={fname} class="w-full h-auto" />
                  </div>
                </div>
              {/if}
            {/each}
            {#each (detail.files || []).filter(f => f.name && f.name.endsWith('.html')) as f}
              <div>
                <div class="flex items-center justify-between mb-2">
                  <b class="text-[11px] uppercase tracking-wide text-faint">{f.name}</b>
                  <a href={fileUrl(selected, f.name)} target="_blank" rel="noopener noreferrer" class="text-[11px] text-gold hover:underline">open in new tab</a>
                </div>
                <p class="text-[11px] text-faint">Open the file to preview. Download ZIP for full file.</p>
              </div>
            {/each}
            <div class="p-3 rounded-xl bg-inset border border-line text-[11px] text-faint">
              Files: {(detail.files || []).map(f => f.name).join(', ')}
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  :global(.markdown h3) { font-size: 14px; font-weight: 700; margin: 14px 0 6px; color: var(--ink); }
  :global(.markdown h4), :global(.markdown h5), :global(.markdown h6) { font-size: 13px; font-weight: 700; margin: 12px 0 4px; color: var(--ink); }
  :global(.markdown p) { margin: 6px 0; }
  :global(.markdown ul) { margin: 6px 0 6px 18px; list-style: disc; }
  :global(.markdown li) { margin: 3px 0; }
  :global(.markdown b) { color: var(--ink); }
  :global(.markdown code) { background: var(--inset); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
  :global(.markdown pre) { background: var(--inset); padding: 10px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
  :global(.markdown a) { color: var(--gold); }
</style>
