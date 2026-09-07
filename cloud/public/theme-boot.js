/* Anti-FOUC theme bootstrap: read the site-wide cookie (so a choice made on
   www.brandforge-os.com also applies here on app.brandforge-os.com), then
   localStorage, and default to DARK — matching the marketing site, which
   ships dark-first (light is the opt-in there too). Must run before first
   paint so there is no flash of the wrong theme. */
(function(){try{var t=null;var m=document.cookie.match(/(?:^|;\s*)brandforge-theme=([^;]+)/);if(m){try{t=decodeURIComponent(m[1]);}catch(e){}}if(!t){try{t=localStorage.getItem('brandforge-theme');}catch(e){}}if(t==='light')document.documentElement.setAttribute('data-theme','light');}catch(e){}})();
