# Desktop user guide

## Setup

Python 3.10 or newer is required. Extract the complete ZIP; do not run from inside the archive viewer. On Windows run SETUP-WINDOWS.bat for installation or repair and START-HERE.bat for subsequent launches. On macOS/Linux follow START-HERE.md. Initial dependency installation needs internet. Ordinary launch does not run pip.

The Python wheel also includes the dashboard and licensed runtime fonts. Its data defaults to the current user's application-data folder. A portable source/ZIP install keeps the existing app-folder layout for backward compatibility. BRANDFORGE_DATA_DIR overrides both locations.

## Workflow

Add a brand, enter its actual audience/benefits and choose a text engine. Offline means text/templates run locally; optional providers, image generation, research and update checks have their own network behavior. Read provider policies before entering sensitive data. An explicit image provider is not silently replaced by a public service; public image fallback is an advanced opt-in.

Create a campaign, review its strategy/copy/visuals, edit text as a new draft, then export PDF, Word or ZIP. Text edits keep existing visuals unchanged. Create a new campaign to regenerate visual content. The editable Word file uses Noto fonts included under app/brandforge_assets/fonts; installing those fonts improves cross-device layout. PDFs embed supported fonts.

Generated content is a draft, not proof of legal/platform approval, trademark clearance or marketing performance. Tools and readiness scores are limited checks. Local approval pages are local review workflows, not a public client-sharing service; share reviewed exported files when the recipient does not have access to your computer.

## Backup and privacy

Back up the configured data folder while the app is stopped: campaigns, agency_clients, memory, brandforge_memory.db and your configuration. Provider keys are stored in local configuration files; protect backups accordingly. Account export in Cloud excludes saved provider-key material, but exported campaign content remains your responsibility.

The Desktop request counter tracks requests-library and bounded public-fetch calls. It does not monitor every process or packet. Localhost model calls, browser requests, installation traffic and optional integrations have different transport paths.

## Optional Telegram

Install app/requirements-full.txt, set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS in your local environment, start Desktop, then run `python -m gateway.telegram_bot` from app/. Only allowlisted chats may use /campaign, /campaigns, /status or /chat. The gateway connects only to the local Desktop API. Telegram receives messages you send through it. Do not paste provider keys into chats.

## Troubleshooting

- Missing setup or changed requirements: rerun the explicit setup/repair script while online.
- Provider unavailable: check Settings, model availability, account limits and billing. No provider can guarantee every prompt or image will be accepted.
- Save/export failure: check disk space, write permission and documented size/script limits. Do not publish an incomplete draft.
- Existing campaign: create a new revision instead of replacing its history.
- Update checks: saved consent works when the environment has not disabled checks. An explicit BRANDFORGE_UPDATE_CHECK=0 takes priority.

Support: support@brandforge-os.com. Include the app version and a redacted error description; never send passwords or API keys.

## 1.4.2 setup and recovery

Run explicit setup/repair once after updating an older installation: the setup record now checks the virtual environment and installed dependency versions as well as the requirements fingerprint. Normal launch still makes no package-manager requests. The Windows launcher opens the browser only after this Desktop server starts; an occupied port is not treated as successful startup.

Settings updates use a private undo journal, `.settings-transaction.json`, inside the data folder. After a process interruption, startup restores the previous file pair before loading keys. If recovery itself fails, preserve the whole data folder and restore a verified backup; do not publish or send the journal because it can contain old credentials. Hardware/filesystem failure still requires backups.

Unreadable approval/performance files are not replaced with empty data. A response that cannot be saved to chat memory is explicitly identified; copy it before closing the window. CLI provider selection and memory views follow the active brand, and cancelled settings do not pretend to switch to Offline.
