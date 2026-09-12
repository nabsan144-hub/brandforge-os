# BrandForge OS Desktop — start here

**Cloud and Desktop are separate products.** This folder runs locally; a Cloud login or subscription is not required. Keep your purchase email and the license files as proof of your tier. The Python runtime is readable source; rights are contractual, not online activation locks.

## First setup (internet required)

1. Unzip the **entire** archive into a writable folder. Do not run it inside the ZIP.
2. Install Python **3.10 or newer**. Python 3.13 is used by the automated Linux suite. Windows users should enable “Add Python to PATH.”
3. **Windows:** double-click `SETUP-WINDOWS.bat` and wait for “Setup complete.”
4. **macOS / Linux:** open a terminal in this folder and run:
   ```sh
   python3 app/setup_env.py --install
   ```

Dependencies and licensed fonts are included/configured for portable SVG and Unicode PDF output. Setup downloads dependencies; it is not an offline installer. Read the error if installation fails—do not assume a partial install is complete.

## Normal launch (no package-manager network work)

- Windows: double-click **`START-HERE.bat`**.
- macOS / Linux:
  ```sh
  app/.venv/bin/python app/setup_env.py --check
  app/.venv/bin/python app/brandforge.py --server
  ```
- Open **http://127.0.0.1:8000**. Keep the terminal open while working.
- The server should bind to loopback. **Do not expose this local app as a public authenticated service.** See `docs/NETWORK-PRIVACY.md`.
- In Settings, keep **Offline** selected for templates without provider calls. Connected text/image providers and research are opt-in and may cost money. A requests log is not a complete network monitor.

## A useful first campaign

Select/create the client, set their voice and proof, upload a logo you have permission to use, then write a specific brief. Set the offer, CTA and destination. Create a pack; review its claims and completeness. Edit a section into a new draft revision without overwriting the original. Export ZIP, PDF or DOCX.

SVG typography is outlined so Urdu/Hindi shaping survives export. Copy remains editable in text and Word files. For consistent **DOCX** layout, install the bundled Noto fonts in `app/brandforge_assets/fonts`; PDF embeds its fonts. Unsupported letter scripts produce an explicit PDF error rather than missing-glyph boxes.

## Update / repair

Back up your local data before replacing application files. Keep `BRANDFORGE_DATA_DIR` outside the application folder if you want clean upgrades. By default runtime data is under `app/` (campaigns, client profiles, memory/config).

Replace application files from an authorized release, **preserving your data**. Run explicit setup again. The requirements fingerprint blocks an outdated environment; ordinary launch never silently runs pip. Optional integrations in `requirements-full.txt` need a separate install and review; ChromaDB is no longer included.

## Support and refund requests

Contact **support@brandforge-os.com** with the version, OS, error and purchase transaction ID—never API keys. The published 14-day refund policy and applicable consumer rights apply. A refund/cancellation does not make already-downloaded files disappear. License and redistribution rights are described in `LICENSE`, `RESALE-LICENSE.md` and `docs/RIGHTS-MATRIX.md`.
