#!/usr/bin/env python3
"""Distinct gates: prelaunch-safe source vs owner-verified revenue readiness.
Never prints credential values, calls payment APIs or changes a deployment.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CHECKS=['paddle_sandbox','live_purchase_refund','guest_owner_download','guest_source_download','all_subscription_transitions','deletion_outage','refund_disputes','email_inbox','private_assets','windows_install_offline','macos_install','provider_quality','legal_approval','commercial_hosting','monitoring_alerts']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prelaunch',action='store_true')
    parser.add_argument('--sales-public-dir',default=os.environ.get('SALES_PUBLIC_DIR',''),help='Published static output to verify for revenue readiness')
    parser.add_argument('--strict-sales',action='store_true',help='Legacy alias for the prelaunch-safe source gate')
    parser.add_argument('--strict',action='store_true',help='Legacy alias for revenue-ready')
    parser.add_argument('--revenue-ready',action='store_true')
    args=parser.parse_args();revenue=args.revenue_ready or args.strict
    errors=[]
    config_path=(Path(args.sales_public_dir)/'assets/config.js') if revenue and args.sales_public_dir else ROOT/'sales/assets/config.js'
    config=config_path.read_text(encoding='utf-8')
    flag=bool(re.search(r'desktop_checkout_enabled\s*:\s*true',config))
    for path in ['docs/LAUNCH-RUNBOOK.md','docs/RIGHTS-MATRIX.md','START-HERE.md','supabase/migrations/0011_delivery_integrity.sql','cloud/api/index.js','cloud/api/_lib/routes/bill-checkout.js','cloud/api/_lib/routes/desk-download.js']:
        if not (ROOT/path).exists():errors.append('Missing '+path)
    if not revenue:
        if flag:errors.append('Public Desktop checkout flag is on; this is not a prelaunch-safe source configuration')
        if any(os.environ.get(k)=='true' for k in ('CLOUD_CHECKOUT_ENABLED','DESKTOP_CHECKOUT_ENABLED')):errors.append('Paid backend flags are on; run revenue verification in the authorized release environment instead')
        print('Mode: PRELAUNCH SAFE (not revenue-ready)')
    else:
        print('Mode: REVENUE READY — requires external owner evidence')
        result=subprocess.run(['node','cloud/scripts/commerce-readiness.mjs'],cwd=ROOT,capture_output=True,text=True,check=False)
        if result.returncode:errors.append('Could not evaluate server-side commerce configuration')
        else:
            readiness=json.loads(result.stdout)
            for kind,r in readiness.items():
                errors.extend(kind+': '+item for item in r['missing'])
                if r['mode']!='production':errors.append(kind+': production environment required')
        if not flag:errors.append('Public Desktop funnel is still disabled')
        for key in ['CRON_SECRET','OPS_ALERT_WEBHOOK_URL']:
            if not os.environ.get(key):errors.append(key+' must be configured and tested')
        evidence=os.environ.get('RELEASE_VERIFICATION_FILE','')
        try:
            document=json.loads(Path(evidence).read_text(encoding='utf-8'))
            commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            if document.get('commit')!=commit:errors.append('Release evidence is for a different commit')
            if not document.get('approved_by'):errors.append('Owner approval identity missing')
            for check in CHECKS:
                if document.get('checks',{}).get(check) is not True:errors.append('External check not signed off: '+check)
        except (OSError,ValueError,subprocess.CalledProcessError):errors.append('A private, completed RELEASE_VERIFICATION_FILE is required')
    for error in errors:print('BLOCKED:',error)
    if errors:return 1
    print('PASS' if not revenue else 'PASS: declarations/configuration match; retain the underlying evidence privately')
    return 0


if __name__=='__main__':raise SystemExit(main())
