# Runtime verification follow-up — 1.4.2

Baseline: the delivered 1.4.1 source at `dec4a8dc0dbf614d3851f852d729e661d4545236`. This pass targets low-coverage runtime paths and real failure behavior. It does not repeat or replace external payment, inbox, platform, legal or customer-acceptance checks.

## Findings and resolutions

| ID | Finding | Resolution | Main files |
|---|---|---|---|
| RX-01 | Non-object setup-state JSON could crash a normal launch check; the marker did not detect missing/changed installed dependencies. | Schema-2 checks handle malformed state, bind the interpreter environment and compare installed versions. Ordinary checks never invoke pip. | `app/setup_env.py` |
| RX-02 | The setup marker used a shared temporary filename; setup could be recorded without a dependency-consistency check. | Unique temporary file, flush/fsync + atomic replacement; explicit installation runs `pip check` before recording success. | `app/setup_env.py` |
| RX-03 | Settings writes could partially update credentials/configuration, or report success after failed persistence. | Validate all settings first, write a private undo journal, atomically replace each file, and update runtime state only after completion. Startup recovers an interrupted pair. Failed recovery blocks generation rather than using uncertain settings. | `app/modules/settings_store.py`, `app/engines/ai_engine.py`, `app/server.py` |
| RX-04 | CLI cancellation could claim Offline while leaving an existing online provider active; settings prompts exposed typed keys and could ignore save failure. | Masked key prompts, shared validated settings flow, explicit unchanged-provider messages, and no false Saved message. No blanket claims about free provider accounts or setup duration. | `app/brandforge.py` |
| RX-05 | CLI chat/memory did not consistently use the active brand; Unicode brand creation bypassed the safe identifier path. | Capture the active brand for chat/campaign generation and persistence, filter memory by that brand, and reuse atomic named-brand creation. | `app/brandforge.py` |
| RX-06 | CLI server startup could accept a foreign listener as readiness, ignore a provider override, permit misleading public-host options, or leave onboarding's thread running after Enter. | Managed loopback Uvicorn lifecycle, readiness from the actual server, explicit engine injection, validated bind options and shutdown confirmation. | `app/modules/desktop_launcher.py`, `app/brandforge.py` |
| RX-07 | Launch wrappers could use a different Python environment; the Windows browser opener used an arbitrary three-second delay. | Prefer the prepared virtual environment and open the browser only after successful Desktop startup. | `START-HERE.bat`, `app/brandforge.bat`, `app/brandforge.sh` |
| RX-08 | Spend parsing could turn negative or malformed input into a positive number; inspection failures could look like a clean result. | Reject invalid monetary input; make failed/incomplete website checks explicit; report actual saved files and configured data paths. | `app/brandforge.py` |
| RX-09 | Unreadable approval/performance JSON could be treated as an empty dataset and overwritten on the next write. | Bounded, shape-checked reads raise a controlled state error. Existing data remains untouched; HTTP surfaces a service/storage error. | `app/modules/state_io.py`, approval/performance managers, `app/server.py` |
| RX-10 | Memory writes could fail silently while the tool claimed success; chat history and accepted notes could be shortened without notice. | Explicit save outcomes, complete bounded chat storage, full accepted note text and visible UI/CLI warnings. Large memory reads use bounded tail access. | memory manager, engine, tool registry, chat UI |
| RX-11 | Maintenance could append indefinitely after failed log rotation, claim completion despite errors, or initialize an AI engine merely to save a daily summary. | Direct local managers, bounded rotation behavior, checked results and explicit opt-in retention; no provider calls for daily maintenance. | `app/daemon.py` |
| RX-12 | Invalid public-fetch limits and port zero could be accepted or coerced. | Validate size/time options before DNS and reject port zero; no exchange starts after the lookup exhausts its budget. | `app/modules/public_http.py` |
| RX-13 | A failed update-preference save hid the question as if saved; the chat's scroll region was not keyboard-focusable in the expanded failure-state test. | UI changes consent only after success, shows errors and keeps retry controls; conversation log is focusable and labelled. | `app/web-modern/src/App.svelte`, `app/web-modern/src/lib/Chat.svelte` |

## Verification

- **87 added parameterized/runtime regression cases** use real temporary files, SQLite, a real loopback server and fault injection. Provider APIs, prompts and scheduling clocks are controlled fixtures where stated.
- Full Desktop suite: **412 passed**. Cloud suite: **185 passed**. Full website/Cloud/Desktop browser suite: **99 records**, with zero selected axe violations, horizontal overflow or page errors.
- Four additional Desktop browser scenarios exercise failed preference persistence and failed memory saving at mobile/desktop widths in dark/light themes. The HTTP failures are explicit fixtures, not actual provider sessions.
- A clean temporary environment completed real explicit setup and a subsequent local readiness check. That is Linux verification, not native Windows/macOS certification.
- Measured Desktop production Python statement coverage increased from **72.59% to 80.25%**: **4,747 of 5,915 statements**, excluding test files. Coverage is execution evidence, not proof of correctness; remaining unexecuted paths are not hidden.

The source still defaults to disabled paid checkout. No account credentials, legal identity, live purchase/refund, email delivery or native-device evidence was invented. The prior audit and owner guide remain applicable, with the runtime update notes appended.

## Recovery/compatibility notes

- Older setup markers intentionally require explicit setup/repair once after updating; ordinary launch never installs packages automatically.
- `.settings-transaction.json` can contain previous credentials. Keep it private and in protected backups. It is excluded from Git and customer packaging. Process-interruption recovery is not a promise against hardware/filesystem loss or concurrent external edits.
- API/CLI attempts that cannot confirm persistence report failure. Do not delete an unreadable state file or recovery journal merely to suppress an error; preserve it and restore a valid backup.
- The maintenance history cap remains opt-in. A missing, zero, negative or invalid cap does not authorize deletion.
- Public and Desktop price points, clean marketing routes, Cloud/Desktop separation and visual identity are unchanged.
