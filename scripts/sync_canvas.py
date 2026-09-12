"""One canonical editable-workspace UI for Cloud and Desktop."""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
for source in (ROOT/'shared/canvas').iterdir():
    if not source.is_file(): continue
    for destination in [ROOT/'cloud/public/canvas'/source.name,ROOT/'app/brandforge_assets/canvas'/source.name]:
        if args.check:
            if not destination.exists() or destination.read_bytes()!=source.read_bytes(): raise SystemExit('Canvas asset drift: '+str(destination))
        else:
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(source.read_bytes())
print('Canvas assets match canonical source.')
