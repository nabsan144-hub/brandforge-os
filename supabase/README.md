# Database setup

Use [the owner guide](../docs/OWNER-GUIDE.md) and [launch runbook](../docs/LAUNCH-RUNBOOK.md). Apply every migration in filename order through 0011. `cloud/schema.sql` is generated from them and is for new/manual setup, not an existing-project migration shortcut. Back up and test in staging first.

The old CHECK_FIRST and VERIFY_0001_0004 files inspect early schema components only; they are not full readiness certification. Native/PGlite regression suites exercise current RPCs and role boundaries.
