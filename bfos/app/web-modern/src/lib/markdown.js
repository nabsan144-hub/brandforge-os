// Minimal, safe Markdown → HTML for chat bubbles.
// Everything is HTML-escaped FIRST, then structural tags are added.
// No raw HTML from the model ever reaches the DOM.

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function inline(text) {
  let t = escapeHtml(text);
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
  t = t.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  t = t.replace(/(^|\W)\*([^*\n]+)\*/g, '$1<i>$2</i>');
  // Images: same-origin /api/ routes or https image links only. Model output
  // is escaped before this runs, so only these two URL shapes become <img>.
  t = t.replace(/!\[([^\]]*)\]\((\/api\/[A-Za-z0-9_\-./]+)\)/g,
    '<img src="$2" alt="$1" loading="lazy" style="max-width:100%;border-radius:10px;margin:6px 0" />');
  t = t.replace(/!\[([^\]]*)\]\((https:[^)\s]+\.(?:jpg|jpeg|png))\)/gi,
    '<img src="$2" alt="$1" loading="lazy" style="max-width:100%;border-radius:10px;margin:6px 0" />');
  t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return t;
}

export function mdToHtml(md) {
  if (!md) return '';
  const lines = String(md).split(/\r?\n/);
  const out = [];
  let inList = false;
  let inCode = false;
  let codeBuf = [];

  for (const raw of lines) {
    if (raw.trim().startsWith('```')) {
      if (inCode) {
        out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>');
        codeBuf = [];
        inCode = false;
      } else {
        if (inList) { out.push('</ul>'); inList = false; }
        inCode = true;
      }
      continue;
    }
    if (inCode) { codeBuf.push(raw); continue; }

    const line = raw;
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    const li = line.match(/^\s*[-*]\s+(.*)$/);
    const num = line.match(/^\s*\d+[.)]\s+(.*)$/);

    if (h) {
      if (inList) { out.push('</ul>'); inList = false; }
      const lvl = Math.min(h[1].length + 2, 6);
      out.push(`<h${lvl}>` + inline(h[2]) + `</h${lvl}>`);
    } else if (li || num) {
      if (!inList) { out.push('<ul>'); inList = true; }
      out.push('<li>' + inline((li || num)[1]) + '</li>');
    } else if (line.trim() === '') {
      if (inList) { out.push('</ul>'); inList = false; }
    } else {
      if (inList) { out.push('</ul>'); inList = false; }
      out.push('<p>' + inline(line) + '</p>');
    }
  }
  if (inCode) out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>');
  if (inList) out.push('</ul>');
  return out.join('');
}
