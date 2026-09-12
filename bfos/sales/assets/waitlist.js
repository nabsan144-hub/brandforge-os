/* ============================================================================
   BRANDFORGE OS — Waitlist form handler (pricing.html)
   ============================================================================
   The form markup existed (email + tier + honeypot) but nothing submitted it —
   clicking "Notify Me" reloaded the page and every signup was silently lost.
   An earlier build wired it to FormSubmit.co with a placeholder inbox,
   which also never worked. This handler POSTs to the real cloud
   /api/waitlist backend (see assets/config.js `waitlistEndpoint()`).

   Behavior:
     - honeypot filled (bot)     → fake success, nothing sent
     - invalid email             → inline error, focus back
     - endpoint not configured   → honest "not configured" message + support email
     - backend unreachable       → honest failure message + support email
     - backend returns 501/error → the waitlist table isn't live yet → support email
     - success                   → inline confirmation, form reset
   ========================================================================== */
(function () {
  function init() {
    var form = document.getElementById('waitlist-form');
    if (!form) return;
    var emailEl = document.getElementById('wl-email');
    var tierEl = document.getElementById('wl-tier');
    var btn = document.getElementById('wl-btn');
    var msg = document.getElementById('wl-msg');

    function say(text, kind) {
      if (!msg) return;
      msg.textContent = text;
      msg.style.color = kind === 'ok' ? '#10B981'
        : kind === 'err' ? '#F87171'
        : 'var(--muted, #9AA3B5)';
    }

    function resetBtn() {
      if (btn) { btn.disabled = false; btn.textContent = 'Notify Me →'; }
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var cfg = window.BRANDFORGE_LAUNCH || {};
      var support = cfg.support_email || 'support@brandforge-os.com';

      // Honeypot: hidden field humans never fill. Pretend success, send nothing.
      var honey = form.querySelector('[name="_honey"]');
      if (honey && honey.value) { say('Thanks — you are on the list.', 'ok'); return; }

      var email = ((emailEl && emailEl.value) || '').trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        say('Please enter a valid email address.', 'err');
        if (emailEl) emailEl.focus();
        return;
      }

      var endpoint = cfg.waitlistEndpoint ? cfg.waitlistEndpoint() : '';
      if (!cfg.waitlistReady || !endpoint) {
        say('The signup inbox is not configured yet — email ' + support +
            ' and we will add you to the list.', '');
        return;
      }

      var tier = (tierEl && tierEl.value) || 'undecided';
      if (btn) { btn.disabled = true; btn.textContent = 'Adding you…'; }

      fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ email: email, tier: tier })
      })
        .then(function (r) {
          return r.json().then(function (d) { return { ok: r.ok, status: r.status, d: d }; })
            .catch(function () { return { ok: r.ok, status: r.status, d: null }; });
        })
        .then(function (res) {
          if (res.ok && res.d && res.d.ok) {
            say('You are on the list — we will email you the moment it is live. ✓', 'ok');
            if (btn) { btn.textContent = 'Added ✓'; }
            form.reset();
          } else {
            // Backend not live yet (waitlist table / Supabase not configured) or
            // a 5xx — surface an honest message instead of a silent drop.
            say((res.d && res.d.error) || ('Could not save your spot — email ' + support + ' to be added to the list.'), 'err');
            resetBtn();
          }
        })
        .catch(function () {
          say('Could not reach the signup service — email ' + support +
              ' to be added to the list.', 'err');
          resetBtn();
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
