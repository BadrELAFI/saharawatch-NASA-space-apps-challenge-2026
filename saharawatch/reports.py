"""Portable investigation archives with actual data, provenance and embedded charts."""
import base64
import html
import io
import json
import os
import shutil
from pathlib import Path
import zipfile
import pandas as pd
import numpy as np
import plotly.graph_objects as go


def configure_report_browser():
    """Respect an explicit browser, then find system Chrome or local Playwright."""
    if os.environ.get('BROWSER_PATH'):
        return os.environ['BROWSER_PATH']
    for name in ('chromium','chromium-browser','google-chrome','google-chrome-stable'):
        browser=shutil.which(name)
        if browser:
            os.environ['BROWSER_PATH']=browser
            return browser
    cache=Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH',Path.home()/'.cache/ms-playwright'))
    for pattern in ('chromium-*/chrome-linux64/chrome','chromium-*/chrome-linux/chrome'):
        for browser in sorted(cache.glob(pattern),reverse=True):
            if browser.is_file() and os.access(browser,os.X_OK):
                os.environ['BROWSER_PATH']=str(browser)
                return str(browser)
    # Kaleido can discover other supported installations itself.
    return None


def build_report_archive(clues):
    """Only pinned observations are used; charts cannot drift with current filters."""
    if not clues:raise ValueError('Pin evidence before creating an illustrated report.')
    configure_report_browser()
    parts=['<!doctype html><html><head><meta charset="utf-8"><title>SaharaWatch investigation</title>',
           '<style>body{font:16px system-ui;max-width:1000px;margin:3em auto;padding:0 1em;line-height:1.6}img{width:100%}pre{white-space:pre-wrap}article{page-break-after:always}table{border-collapse:collapse}td{padding:.3em;border-bottom:1px solid #ddd}</style></head><body>',
           '<h1>SaharaWatch · Evidence report</h1><p>Historical exploration; not a drought forecast. Data: <a href="https://psl.noaa.gov/data/gridded/data.gpcp.html">NOAA PSL GPCP satellite–gauge analysis</a>. Boundaries: Natural Earth.</p>']
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
        for i,clue in enumerate(clues,1):
            parts.append(f'<article><h2>Clue {i}: {html.escape(clue["location"])}</h2><table>')
            for key,value in clue.items():
                if key not in ['annual_data','chart_json','recent_country_briefing']:
                    parts.append(f'<tr><td>{html.escape(key.replace("_"," "))}</td><td>{html.escape(str(value))}</td></tr>')
            parts.append('</table>')
            if clue.get('annual_data'):
                frame=pd.DataFrame(clue['annual_data'])
                archive.writestr(f'data/clue_{i:02d}.csv',frame.to_csv(index=False))
            recent=clue.get('recent_country_briefing')
            if recent and recent.get('annual_years'):
                frame=pd.DataFrame({'year':recent['annual_years'],'observed_mm':recent['annual_mm'],
                                    'baseline_annual_mean_mm':recent.get('baseline_annual_mean_mm',np.nan)})
                archive.writestr(f'data/clue_{i:02d}_recent_country.csv',frame.to_csv(index=False))
            for name,serialized in clue.get('chart_json',{}).items():
                figure=go.Figure(json.loads(serialized))
                image=figure.to_image(format='png',width=1100,height=420,scale=1)
                archive.writestr(f'charts/clue_{i:02d}_{name}.png',image)
                encoded=base64.b64encode(image).decode()
                parts.append(f'<h3>{html.escape(name.title())}</h3><img alt="{html.escape(name)} chart for pinned observations" src="data:image/png;base64,{encoded}">')
            if not clue.get('chart_json'):
                parts.append('<p>This older pinned clue has no stored chart data. No chart has been reconstructed from current filters.</p>')
            parts.append('</article>')
        parts.append('<h2>Scientific limits</h2><p>Climate inference is exploratory. See each clue for its inference and weighting methods. Serial correlation, small samples, coarse grid cells and approximate boundaries limit interpretation. Relative anomalies are not SPI. A significant association does not establish causality.</p></body></html>')
        archive.writestr('report.html',''.join(parts))
        archive.writestr('evidence.json',json.dumps(clues,indent=2,allow_nan=False))
    return out.getvalue()
