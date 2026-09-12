<script>
  import { onMount } from 'svelte'
  let canvas
  let ctx
  
  // 6 stages — like the creative image: gold, blue, emerald, purple, orange, red
  const agents = [
    { name: 'Strategist', color: '#E8B54A', x: 0, y: 0, angle: 0, radius: 80, speed: 0.008, size: 6 },
    { name: 'Copywriter', color: '#3B82F6', x: 0, y: 0, angle: 60, radius: 110, speed: 0.012, size: 5 },
    { name: 'Quality', color: '#10B981', x: 0, y: 0, angle: 120, radius: 95, speed: 0.01, size: 5 },
    { name: 'Visual', color: '#8B5CF6', x: 0, y: 0, angle: 180, radius: 125, speed: 0.007, size: 6 },
    { name: 'Researcher', color: '#F97316', x: 0, y: 0, angle: 240, radius: 100, speed: 0.015, size: 4 },
    { name: 'SEO', color: '#EC4899', x: 0, y: 0, angle: 300, radius: 85, speed: 0.009, size: 5 }
  ]
  
  let trails = []
  
  onMount(() => {
    ctx = canvas.getContext('2d')
    let fade = 'rgba(8, 10, 15, 0.12)'
    let light = false
    const refreshTheme = () => {
      const t = document.documentElement.getAttribute('data-theme')
      light = t === 'light'
      // The fade must match the CARD surface (--inset), not --bg: painting a
      // different tone each frame is what left a grey/washed film over the
      // constellation in light mode.
      fade = light ? 'rgba(240, 237, 230, 0.16)' : 'rgba(8, 10, 15, 0.12)'
    }
    refreshTheme()
    const themeObserver = typeof MutationObserver !== 'undefined'
      ? new MutationObserver(refreshTheme)
      : null
    if (themeObserver) themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    const rect = canvas.getBoundingClientRect()
    let w = rect.width, h = rect.height
    let dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    const onResize = () => {
      w = canvas.getBoundingClientRect().width
      h = canvas.getBoundingClientRect().height
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      trails = []
    }
    window.addEventListener('resize', onResize)
    
    let animationId = 0
    let visible = true
    // `reduced` (prefers-reduced-motion) is declared below with the static
    // frame path; the loop guard inside animate() uses it.
    const animate = () => {
      animationId = 0
      if (!visible) return
      const cx = w / 2
      const cy = h / 2
      
      // Fade trail
      ctx.fillStyle = fade
      ctx.fillRect(0, 0, w, h)
      
      // Center brand glow
      // Center brand glow — final stop must be the SAME hue at alpha 0,
      // not 'transparent' (rgba(0,0,0,0)): interpolating toward transparent
      // BLACK is what smeared grey halos over the light theme.
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60)
      gradient.addColorStop(0, 'rgba(232, 181, 74, 0.16)')
      gradient.addColorStop(1, 'rgba(232, 181, 74, 0)')
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(cx, cy, 60, 0, Math.PI * 2)
      ctx.fill()
      
      // Center brand mark
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--gold').trim() || '#E8B54A'
      ctx.font = 'bold 32px Inter, sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('B', cx, cy)
      
      // Draw trails
      trails.forEach((t, i) => {
        if (t.life <= 0) return
        ctx.beginPath()
        ctx.strokeStyle = t.color + Math.floor(t.life * 100).toString(16).padStart(2, '0')
        ctx.lineWidth = 1
        ctx.moveTo(t.x1, t.y1)
        ctx.lineTo(t.x2, t.y2)
        ctx.stroke()
        t.life -= 0.02
      })
      trails = trails.filter(t => t.life > 0)
      
      // Update and draw agents
      agents.forEach(agent => {
        agent.angle += agent.speed * 60
        const newX = cx + Math.cos(agent.angle * Math.PI / 180) * agent.radius
        const newY = cy + Math.sin(agent.angle * Math.PI / 180) * agent.radius
        
        // Add trail
        if (Math.random() > 0.3) {
          trails.push({
            x1: agent.x || newX,
            y1: agent.y || newY,
            x2: newX,
            y2: newY,
            color: agent.color,
            life: 1
          })
        }
        
        agent.x = newX
        agent.y = newY
        
        // Orb glow
        // Orb glow — same-hue alpha-0 end stop (see center-glow note above).
        // Light theme gets a tighter, softer halo so cream stays clean.
        const glowR = agent.size * (light ? 2.2 : 3)
        const orbGradient = ctx.createRadialGradient(newX, newY, 0, newX, newY, glowR)
        orbGradient.addColorStop(0, agent.color + (light ? '40' : '60'))
        orbGradient.addColorStop(1, agent.color + '00')
        ctx.fillStyle = orbGradient
        ctx.beginPath()
        ctx.arc(newX, newY, glowR, 0, Math.PI * 2)
        ctx.fill()
        
        // Orb
        ctx.fillStyle = agent.color
        ctx.beginPath()
        ctx.arc(newX, newY, agent.size, 0, Math.PI * 2)
        ctx.fill()
        
        // Inner highlight
        ctx.fillStyle = 'rgba(255,255,255,0.8)'
        ctx.beginPath()
        ctx.arc(newX - 1, newY - 1, agent.size * 0.3, 0, Math.PI * 2)
        ctx.fill()
      })
      
      // Draw connections (brand gold, not retired amber #F59E0B)
      ctx.strokeStyle = 'rgba(232, 181, 74, 0.10)'
      ctx.lineWidth = 0.5
      for (let i = 0; i < agents.length; i++) {
        for (let j = i + 1; j < agents.length; j++) {
          const dist = Math.hypot(agents[i].x - agents[j].x, agents[i].y - agents[j].y)
          if (dist < 180) {
            ctx.beginPath()
            ctx.moveTo(agents[i].x, agents[i].y)
            ctx.lineTo(agents[j].x, agents[j].y)
            ctx.globalAlpha = (1 - dist / 180) * 0.3
            ctx.stroke()
            ctx.globalAlpha = 1
          }
        }
      }
      
      if (!reduced) animationId = requestAnimationFrame(animate)
    }

    // Pause off-screen — no wasted frames when the hero is scrolled away
    const io = typeof IntersectionObserver !== 'undefined'
      ? new IntersectionObserver((entries) => {
          const nowVisible = entries[0]?.isIntersecting !== false
          if (nowVisible && !visible) {
            visible = true
            if (!animationId) animate()
          } else if (!nowVisible) {
            visible = false
            if (animationId) { cancelAnimationFrame(animationId); animationId = 0 }
          }
        }, { threshold: 0.05 })
      : null
    if (io) io.observe(canvas)

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduced) animate()
    else {
      // Static frame for reduced-motion users
      const cx = w / 2, cy = h / 2
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--gold').trim() || '#E8B54A'
      ctx.font = 'bold 32px system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('B', cx, cy)
      agents.forEach((agent, i) => {
        const a = (i / agents.length) * Math.PI * 2
        const x = cx + Math.cos(a) * agent.radius
        const y = cy + Math.sin(a) * agent.radius
        ctx.fillStyle = agent.color
        ctx.beginPath(); ctx.arc(x, y, agent.size, 0, Math.PI * 2); ctx.fill()
      })
    }
    
    return () => {
      visible = false
      if (animationId) cancelAnimationFrame(animationId)
      window.removeEventListener('resize', onResize)
      if (io) io.disconnect()
      if (themeObserver) themeObserver.disconnect()
    }
  })
</script>

<div class="relative w-full h-[400px] rounded-[24px] bg-inset border border-line overflow-hidden">
  <canvas bind:this={canvas} class="w-full h-full" aria-hidden="true"></canvas>
  
  <!-- Overlay UI — factual labels, no fake "LIVE/ACTIVE" theater -->
  <div class="absolute top-4 left-4 right-4 z-10 flex justify-between items-start pointer-events-none">
    <div class="px-3 py-1.5 rounded-full bg-black/60 backdrop-blur-xl border border-white/10 text-[11px] font-bold tracking-wide text-white flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
      6-AGENT SWARM
    </div>
    <div class="px-3 py-1.5 rounded-full bg-black/60 backdrop-blur-xl border border-white/10 text-[11px] text-white/80">
      LOCAL • PRIVATE
    </div>
  </div>
  
  <div class="absolute bottom-4 left-4 right-4 z-10 pointer-events-none">
    <div class="flex gap-2 flex-wrap">
      {#each agents as agent}
        <div class="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-xl border border-white/10 text-[11px] flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full" style="background:{agent.color}"></span>
          <span class="text-white font-medium">{agent.name}</span>
        </div>
      {/each}
    </div>
  </div>
  
  <div class="absolute inset-0 pointer-events-none bg-gradient-to-t from-inset via-transparent to-transparent"></div>
</div>
