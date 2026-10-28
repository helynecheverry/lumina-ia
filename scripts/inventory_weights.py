"""Inventory installed weights without copying them; optionally hash all files."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha256', action='store_true', help='Lee todos los pesos; puede tardar mucho.')
    parser.add_argument('--output', type=Path, default=ROOT/'documentacion/evidencias/weights-inventory.json')
    args = parser.parse_args()
    files = []
    for path in sorted((ROOT/'weights').rglob('*')):
        if not path.is_file() or '.cache' in path.parts or '__pycache__' in path.parts:
            continue
        entry = {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size}
        if args.sha256:
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
                    digest.update(block)
            entry['sha256'] = digest.hexdigest()
        files.append(entry)
    report = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'hashes_included': args.sha256, 'total_bytes': sum(f['bytes'] for f in files), 'files': files}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(files)} archivos, {report["total_bytes"]} bytes: {args.output}')


if __name__ == '__main__':
    main()
