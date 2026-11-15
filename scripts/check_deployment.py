"""Offline deployment preflight; optionally exercise the real Chromium report renderer."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from saharawatch.data import RAW, ROOT, load_data, complete_years, boundaries
from saharawatch.reports import build_report_archive, configure_report_browser
from saharawatch.satellite import load_satellite_pair


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-report',action='store_true',help='Require a working browser and render a PNG into a report ZIP.')
    args=parser.parse_args()
    provenance=json.loads(RAW.with_suffix('.json').read_text())
    digest=hashlib.sha256(RAW.read_bytes()).hexdigest()
    if digest != provenance['sha256']:
        raise ValueError('Rainfall snapshot checksum differs from its provenance. Run scripts/prepare_data.py and review both files.')
    monthly,annual,metadata=load_data()
    if len(complete_years(monthly)) < 10 or not boundaries():
        raise ValueError('Missing rainfall history or country boundaries.')
    load_satellite_pair()
    for asset in ('assets/styles.css','assets/case-folders.css','assets/office/office.css','assets/office/effects.js'):
        if not (ROOT/asset).is_file():
            raise FileNotFoundError(asset)
    print(f'Rainfall snapshot validated: {metadata["start"][:7]} to {metadata["end"][:7]} / SHA-256 {digest}')
    print('Bundled satellite evidence, boundaries and office assets available.')
    if args.render_report:
        import plotly.graph_objects as go
        values=annual.mean(('lat','lon'))
        chart=go.Figure(go.Scatter(x=values.year.values,y=values.values)).to_json()
        payload=build_report_archive([dict(location='Deployment preflight / MENA grid mean',chart_json={'rainfall':chart})])
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if not archive.read('charts/clue_01_rainfall.png').startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Report renderer did not produce a PNG.')
            archive.read('report.html')
        print(f'Illustrated report rendered successfully with {configure_report_browser() or "Kaleido browser discovery"}.')
    print('Deployment preflight passed. No external data downloads were needed.')


if __name__=='__main__':
    main()
