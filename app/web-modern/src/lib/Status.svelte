<script>
  import { Zap, FolderOpen, Wrench, Building2 } from '@lucide/svelte'
  export let health = { provider: 'offline', campaigns: 0, tools_count: 21, active_client: 'Default Studio' }
</script>

<div class="flex gap-2 flex-wrap justify-center">
  <div class="px-4 py-3 rounded-2xl bg-card border border-line flex items-center gap-3 min-w-[140px]">
    <div class="w-10 h-10 rounded-xl bg-inset border border-line flex items-center justify-center"><Zap class="w-4 h-4 text-gold" /></div>
    <div><b class="block text-[13px] text-ink leading-none capitalize">{health.provider || 'offline'}</b><span class="text-[11px] text-faint">{health.offline_mode ? (health.provider === 'ollama' ? 'Local text model' : 'Offline text templates') : 'Connected text provider'}</span></div>
  </div>
  <div class="px-4 py-3 rounded-2xl bg-card border border-line flex items-center gap-3 min-w-[140px]">
    <div class="w-10 h-10 rounded-xl bg-inset border border-line flex items-center justify-center"><FolderOpen class="w-4 h-4 text-ink" /></div>
    <div><b class="block text-[14px] text-ink leading-none">{health.campaigns || 0}</b><span class="text-[11px] text-faint">{(health.license && health.license.mode === 'hosted' && !health.license.licensed) ? `Campaigns • Free ${health.license.limit || 3} max` : 'Campaigns • On your PC'}</span></div>
  </div>
  <div class="px-4 py-3 rounded-2xl bg-card border border-line flex items-center gap-3 min-w-[140px]">
    <div class="w-10 h-10 rounded-xl bg-inset border border-line flex items-center justify-center"><Wrench class="w-4 h-4 text-ink" /></div>
    <div><b class="block text-[14px] text-ink leading-none">{health.tools_count || 21} Tools</b><span class="text-[11px] text-faint">Research, audit, visuals</span></div>
  </div>
  <div class="px-4 py-3 rounded-2xl bg-card border border-line flex items-center gap-3 min-w-[140px]">
    <div class="w-10 h-10 rounded-xl bg-ink text-bg flex items-center justify-center"><Building2 class="w-4 h-4" /></div>
    <!-- Was truncating "Default Studio" to "Default Stu…" — a paid product
         must show the buyer's brand name whole. -->
    <div><b class="block text-[12px] text-ink leading-none truncate max-w-[130px]" title={health.active_client || 'Default'}>{health.active_client || 'Default'}</b><span class="text-[11px] text-faint">Active Brand</span></div>
  </div>
</div>
