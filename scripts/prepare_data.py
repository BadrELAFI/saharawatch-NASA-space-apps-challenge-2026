"""Download once, validate before replacing the raw dataset, and write provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import datetime
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saharawatch.data import RAW, ROOT, SOURCE, load_data, complete_years


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if not RAW.exists() or args.refresh:
        temporary = RAW.with_suffix('.nc.part')
        print(f'Downloading {SOURCE}', flush=True)
        with requests.get(SOURCE, stream=True, timeout=(30, 180)) as response:
            response.raise_for_status()
            with temporary.open('wb') as output:
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
        load_data(temporary)  # A failed validation never replaces a valid file.
        temporary.replace(RAW)
    monthly, annual, metadata = load_data()
    metadata.update(sha256=hashlib.sha256(RAW.read_bytes()).hexdigest(),
                    prepared_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    mena_shape=dict(monthly.sizes))
    RAW.with_suffix('.json').write_text(json.dumps(metadata, indent=2, default=str)+'\n')
    processed = ROOT / 'data/processed'
    processed.mkdir(parents=True, exist_ok=True)
    monthly.to_dataset(name='precip_mm').to_netcdf(processed / 'mena_monthly.nc')
    (processed / 'provenance.json').write_text(json.dumps(metadata, indent=2, default=str))
    print(json.dumps(metadata, indent=2, default=str))
    print(f'Complete annual totals: {complete_years(monthly)}')


if __name__ == '__main__':
    main()
