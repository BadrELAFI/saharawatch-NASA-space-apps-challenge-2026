"""SaharaWatch Streamlit dashboard. Run: streamlit run app.py."""
import html
import json
import numpy as np
import pandas as pd
import streamlit as st
from saharawatch.data import (ROOT, RAW, VARIABLES, load_data, complete_years, grid_series,
                              select_period, boundaries, country_mask, regional_series, country_weights)
from saharawatch.briefing import render_country_briefing, assessment_text
from saharawatch.inference import METHODS, analyze_trend, inference_grid
from saharawatch.temperature import render_temperature
from saharawatch.time_machine import render_time_machine
from saharawatch.evidence_board import render_evidence_board, clue_id, RELATIONS
from saharawatch.reports import build_report_archive
from saharawatch.guided import render_live_investigation
from saharawatch.comparison import render_comparison
from saharawatch.trend_diagnostics import render_trend_diagnostics
from saharawatch.drought import anomaly_statistics
from saharawatch.drought_panel import render_drought_panel
from saharawatch.analysis import trend, trend_grid, annual_anomalies, fdr_bh, monthly_anomalies
from saharawatch.plots import map_figure, history_figure, anomaly_figure, style, CYAN, AMBER
import plotly.graph_objects as go

st.set_page_config(page_title='SaharaWatch · The Climate Detective Bureau',page_icon='🔎',layout='wide')
st.html(f'<style>{(ROOT / "assets/styles.css").read_text()}</style>')


@st.cache_data(show_spinner='Reading and validating real GPCP precipitation…')
def cached_data(stamp):
    return load_data()


@st.cache_data(show_spinner=False)
def cached_trends(stamp, start, end, _annual, method='OLS'):
    # File identity and selected years fully identify the excluded xarray argument.
    return inference_grid(_annual,method)


@st.cache_data(show_spinner=False)
def cached_mask(lat, lon, feature, weighting):
    import xarray as xr
    grid = xr.DataArray(np.zeros((len(lat),len(lon))),dims=('lat','lon'),coords={'lat':lat,'lon':lon})
    return country_weights(grid,feature,weighting)


def fmt(value, digits=1):
    return f'{value:,.{digits}f}' if np.isfinite(value) else 'Unavailable'


def reset():
    for key in list(st.session_state):
        del st.session_state[key]


def set_lens(indicator, year=None):
    st.session_state['indicator'] = indicator
    if year is not None:
        st.session_state['anomaly_year'] = int(year)


def select_map_cell():
    points=st.session_state.get('map',{}).get('selection',{}).get('points',[])
    if not points:return
    custom=points[-1].get('customdata',[])
    if isinstance(custom,dict) and 'bdata' in custom:
        import base64
        custom=np.frombuffer(base64.b64decode(custom['bdata']),dtype=custom['dtype']).tolist()
    if isinstance(custom,dict):custom=list(custom.values())
    if len(custom)>=2:
        latitude,longitude=map(float,custom[:2])
        if 10<=latitude<=43 and -18<=longitude<=63:
            st.session_state.update(mode='Grid cell',lat=latitude,lon=longitude)


def select_briefing_country():
    st.session_state.update(mode='Country aggregation',country=st.session_state['brief_country'])


def preset(name):
    st.session_state['active_case'] = name
    st.session_state.update(mode='Country aggregation' if 'Morocco' in countries else 'Grid cell',
                            country='Morocco',first_country='Morocco',
                            comparison_mode='Countries' if len(countries)>=2 else 'Grid cells')
    st.session_state.setdefault('period',default_period)
    if name == 'morocco':
        st.session_state['indicator']='Linear trend'
    elif name == 'compare':
        st.session_state['compare_country']='Algeria'
        st.session_state['indicator']='Mean annual rainfall'
    elif name == 'anomaly':
        st.session_state['indicator']='Annual anomaly'
    else:
        st.session_state['indicator']='Linear trend'


try:
    file_stamp = (RAW.stat().st_mtime_ns, RAW.stat().st_size) if RAW.exists() else None
    monthly, annual, metadata = cached_data(file_stamp)
except (FileNotFoundError, ValueError, OSError) as exc:
    st.error(str(exc))
    st.code('python scripts/prepare_data.py\nstreamlit run app.py',language='bash')
    st.stop()

years = complete_years(monthly)
if len(years) < 10:
    st.error('At least ten complete calendar years are needed. Check the downloaded dataset.'); st.stop()
countries = boundaries()
country_names = sorted(countries)
default_period = (2001,2024) if 2001 in years and 2024 in years else (years[0],years[-1])
default_baseline = (2001,2020) if 2001 in years and 2020 in years else (years[0],years[-1])
indicators = ['Mean annual rainfall','Linear trend','Relative trend','Annual anomaly','Relative anomaly','Standardized anomaly','Trend significance']
with st.sidebar:
    st.html('<div class="brand"><i class="brand-symbol"></i> Sahara<span>Watch</span></div><p class="eyebrow">Climate Detective Bureau</p>')
    st.divider()
    st.caption('01 / MARK THE SCENE')
    mode = st.radio('Selection mode',['Grid cell','Country aggregation'] if countries else ['Grid cell'],key='mode',horizontal=True)
    feature = None
    selected = None
    weighting=st.selectbox('Country weighting',['Center-point','Fractional area'],key='weighting')
    if mode == 'Country aggregation':
        country = st.selectbox('Country',country_names,index=country_names.index('Morocco'),key='country')
        feature = countries[country]
        mask = cached_mask(annual.lat.values,annual.lon.values,feature,weighting)
        st.caption(f'{int((mask>0).sum())} contributing cells · {weighting} weighting')
    else:
        lat = st.number_input('Latitude (° N)',min_value=10.,max_value=43.,value=31.25,step=2.5,key='lat')
        lon = st.number_input('Longitude (° E)',min_value=-18.,max_value=63.,value=-6.25,step=2.5,key='lon')
    st.divider()
    st.caption('02 / CHOOSE YOUR LENS')
    variable=st.selectbox('Environmental variable',list(VARIABLES),format_func=lambda k:VARIABLES[k]['label'],key='variable')
    inference_method=st.selectbox('Trend inference',METHODS,key='inference_method')
    indicator = st.selectbox('Map indicator',indicators,key='indicator') if variable=='precip' else 'Mean annual rainfall'
    start,end = st.slider('Analysis period',years[0],years[-1],default_period,key='period')
    with st.expander('Baseline & statistical settings',expanded=indicator in ['Annual anomaly','Relative anomaly','Standardized anomaly','Trend significance']):
        bstart,bend = st.slider('Reference baseline',years[0],years[-1],default_baseline,key='baseline')
        alpha = st.selectbox('Significance threshold α',[0.01,0.05,0.10],index=1,key='alpha')
        correction = st.radio('Map significance',['Benjamini–Hochberg FDR','Raw p-values'],key='correction')
        st.caption('95% slope intervals remain fixed. Baselines and trends each require ≥10 complete years.')
    st.button('Start a fresh investigation',on_click=reset,width='stretch')
    st.divider()
    st.caption(f'GPCP AVAILABLE RECORD\n\n{metadata["start"][:7]} → {metadata["end"][:7]}\n\nAnnual analysis excludes incomplete years.')
    st.markdown('[Dataset & attribution ↗](https://psl.noaa.gov/data/gridded/data.gpcp.html)')

if variable=='t2m':
    if mode=='Country aggregation':
        from shapely.geometry import shape
        point=shape(feature['geometry']).representative_point()
        temp_lat,temp_lon=point.y,point.x
        st.info('The country selects a starting point for temperature exploration; the result is not a national average.')
    else:temp_lat,temp_lon=lat,lon
    render_temperature(temp_lat,temp_lon,start,end,bstart,bend,alpha,inference_method,monthly)
    st.stop()

st.html("""<section class="hero">
<div><p class="eyebrow">SaharaWatch / The Climate Detective Bureau</p>
<h1>The curious case<br>of the <em>missing rain.</em></h1>
<p class="subtitle">Every landscape leaves a clue. Trace the rainfall, question the patterns, and build your case from decades of Earth observations.</p></div>
<div class="hero-art" aria-hidden="true"><div class="stamp">FIELD OFFICE<br>MENA · EST. 1979</div>
<div class="detective-lens"><span class="lens-drop"></span><span class="lens-dunes"></span></div><span class="coordinates">18° W — 63° E / 10° N — 43° N<br>FOLLOW THE EVIDENCE.</span></div></section>""")
st.html(f'<span class="source-pill">EVIDENCE SOURCE · GPCP {metadata["version"]} / NOAA PSL</span><span class="source-pill">{start} — {end}</span><span class="source-pill">2.5° × 2.5° · Monthly observations</span>')
try:
    window = select_period(annual,start,end)
except ValueError as exc:
    st.warning(str(exc)); st.stop()
if bend-bstart+1 < 10:
    st.warning('Choose a baseline spanning at least 10 complete years.'); st.stop()
try:
    if mode == 'Country aggregation':
        whole_series = regional_series(annual,mask)
        whole_monthly = regional_series(monthly,mask)
        label = f'{country} · country mask'
    else:
        whole_series = grid_series(annual,lat,lon)
        whole_monthly = grid_series(monthly,lat,lon)
        selected = (float(whole_series.lat),float(whole_series.lon))
        label = f'Grid cell · {selected[0]:.2f}° N, {selected[1]:.2f}° E'
    series = whole_series.sel(year=slice(start,end))
    result = analyze_trend(series.year.values,series.values,alpha,inference_method)
    anomaly,z,baseline_mean = annual_anomalies(whole_series,bstart,bend)
except ValueError as exc:
    st.warning(str(exc)); st.stop()

case_titles = {'morocco': 'Is Morocco becoming drier?', 'compare': 'Across the border',
               'anomaly': 'The dry-year files', 'trends': 'Follow the strongest trail'}
active_case = case_titles.get(st.session_state.get('active_case'), 'An open investigation')
st.html(f'<div class="case-strip"><b>CASE FILE / OPEN</b><span>{html.escape(active_case)}</span><span>{html.escape(label)} · {start}–{end}</span></div>')
explorer,comparison,guided,notebook,methods,deficits = st.tabs(['01 / Evidence atlas','02 / Cross-examine','03 / Case files','04 / Field notebook','05 / The science','06 / Rainfall deficits & SPI'])
with explorer:
    st.caption('YOUR INVESTIGATION / Survey the scene → inspect a year → weigh the trend → pin your evidence')
    tool_a, tool_b, tool_c = st.columns(3)
    valid_series = series.where(np.isfinite(series), drop=True)
    driest_year = int(valid_series.idxmin('year')) if valid_series.size else None
    tool_a.button('⌕ Inspect the driest year', key='inspect_driest', width='stretch',
                  disabled=driest_year is None, on_click=set_lens, args=('Annual anomaly', driest_year),
                  help='Find the lowest annual rainfall in the current location and period; inspect its anomaly map.')
    tool_b.button('↗ Trace the long-term trend', key='trace_trend', width='stretch',
                  on_click=set_lens, args=('Linear trend',))
    tool_c.button('⚖ Challenge the evidence', key='challenge_evidence', width='stretch',
                  on_click=set_lens, args=('Trend significance',))
    if st.toggle('Open the rainfall time machine', key='rainfall_time_machine'):
        with st.container(border=True):
            render_time_machine(annual, whole_series, years, start, end, bstart, bend,
                                label, metadata, selected=selected, feature=feature)
    titlecol,controlcol = st.columns([3,1])
    with titlecol:
        st.subheader('The evidence atlas')
        st.caption(f'{indicator.upper()} / {start}–{end}')
    with controlcol:
        st.session_state.setdefault('anomaly_year', end)
        st.session_state['anomaly_year'] = max(start, min(end, st.session_state['anomaly_year']))
        anomaly_year = st.selectbox('Observation year',list(range(start,end+1)),
                                    disabled=indicator not in ['Annual anomaly','Relative anomaly','Standardized anomaly'],key='anomaly_year')
    pvalues = None
    observed_grid = expected_grid = None
    diverging = indicator != 'Mean annual rainfall'
    significance = indicator == 'Trend significance'
    if indicator == 'Mean annual rainfall':
        values,units = window.mean('year'),'mm/year'
    elif indicator in ['Annual anomaly','Relative anomaly','Standardized anomaly']:
        grid_departures = anomaly_statistics(annual,bstart,bend)
        grid_metric = {'Annual anomaly':'anomaly','Relative anomaly':'relative_anomaly','Standardized anomaly':'standardized_anomaly'}[indicator]
        values = grid_departures[grid_metric].sel(year=anomaly_year)
        observed_grid=annual.sel(year=anomaly_year)
        expected_grid=grid_departures.expected
        units = {'Annual anomaly':'mm','Relative anomaly':'%','Standardized anomaly':'σ'}[indicator]
    else:
        trends = cached_trends(file_stamp,start,end,window,inference_method)
        pvalues = trends.sel(stat='p',drop=True)
        if indicator == 'Trend significance':
            sig = fdr_bh(pvalues.values,alpha) if correction == 'Benjamini–Hochberg FDR' else pvalues.values < alpha
            values = (np.sign(trends.sel(stat='decade',drop=True))*sig).where(np.isfinite(pvalues))
            units = 'Trend class'
        elif indicator == 'Relative trend':
            values,units = trends.sel(stat='relative',drop=True),'%/decade'
        else:
            values,units = trends.sel(stat='decade',drop=True),'mm/decade'
    period_text = f'{start}–{end}'
    if indicator in ['Annual anomaly','Relative anomaly','Standardized anomaly']:
        period_text = f'{anomaly_year} vs. {bstart}–{bend} baseline'
    figure = map_figure(values,indicator,units,period_text,pvalues=pvalues,selected=selected,
                        feature=feature,diverging=diverging,significance=significance,observed=observed_grid,expected=expected_grid)
    st.plotly_chart(figure,width='stretch',theme=None,key='map',on_select=select_map_cell,selection_mode='points',config={'scrollZoom':True,'displaylogo':False})
    st.caption(f'Inference: {inference_method}. P-values test the selected method; FDR correction is separate from autocorrelation treatment.')
    if significance:
        st.caption(f'{correction} at α = {alpha}. Terracotta: significant decrease · parchment: no significant trend detected · green: significant increase. Missing cells are unfilled. Hover shows unadjusted p-values for the selected method; FDR tests all valid cells in the study rectangle, including ocean.')
    else:
        st.caption('Pan, zoom, and hover to investigate. Every square is an actual 2.5° GPCP cell, including ocean; no spatial interpolation. Unfilled cells have insufficient data. Click a cell-center dot to inspect it, or select coordinates or a country in the sidebar.')
    if indicator == 'Relative anomaly':
        st.caption('Relative anomalies are withheld where baseline mean annual rainfall is below 10 mm/year.')
    if indicator == 'Relative trend':
        st.caption('Relative trends are withheld where mean annual rainfall is below 10 mm/year.')
    if indicator == 'Standardized anomaly':
        st.caption('Annual standardized anomaly = (observed − baseline mean) / baseline sample standard deviation. This is not SPI.')
    st.divider()
    country_brief=render_country_briefing(annual,countries,years,metadata['sha256'],bstart,bend,weighting,start,end,alpha,inference_method,
                                        country if mode=='Country aggregation' else None,select_briefing_country)
    st.caption('Source status: '+metadata['attributes'].get('data_comment','Provisional status not specified.'))
    st.divider()
    if indicator in ['Annual anomaly', 'Relative anomaly', 'Standardized anomaly']:
        observed_mm = float(whole_series.sel(year=anomaly_year))
        departure_mm = float(anomaly.sel(year=anomaly_year))
        st.html(f'<div class="clue-card"><p class="eyebrow">Year under investigation / {anomaly_year}</p><h3>{html.escape(label)}</h3><p>Recorded rainfall: <b>{fmt(observed_mm)} mm</b> · Departure from the {bstart}–{bend} baseline: <b>{fmt(departure_mm)} mm</b>. One year is a clue; the full timeline is needed to investigate a trend.</p></div>')
    st.markdown(f'### {label}')
    if mode == 'Country aggregation':
        st.caption(f'Approximate national series with {weighting} weighting. Fractional mode uses polygon overlap in an equal-area projection; GPCP cells remain coarse mixed-area observations. Natural Earth boundaries are descriptive and imply no endorsement.')
    cols = st.columns(4)
    cols[0].metric('Mean annual rainfall',fmt(result['mean'])+' mm')
    cols[1].metric('Linear trend',fmt(result['decade'])+' mm/decade')
    cols[2].metric(f'{inference_method} p-value',fmt(result['p'],4))
    cols[3].metric('Complete years',str(result['n']))
    st.write('')
    left,right = st.columns([2.3,1])
    with left:
        st.markdown('### Exhibit A · The rainfall timeline')
        view = st.radio('Time resolution',['Annual','Monthly'],horizontal=True,key='resolution')
        moving = st.checkbox('Show moving average',key='moving')
        displayed = whole_monthly.sel(time=slice(f'{start}-01-01',f'{end}-12-31')) if view == 'Monthly' else series
        st.plotly_chart(history_figure(displayed,result,baseline=float(baseline_mean),moving=moving,monthly=view=='Monthly'),
                        width='stretch',theme=None,key='history')
        st.caption(f'Annual totals require 12 valid months. Baseline: {bstart}–{bend}. Monthly totals preserve seasonality; annual OLS statistics above do not change with chart resolution.')
    with right:
        st.markdown('### The evidence speaks')
        st.html(f'<div class="insight"><b>{html.escape(result["status"])}</b><br><br>Over {start}–{end}, the fitted annual rainfall trend is <b>{fmt(result["decade"])} mm per decade</b> using {inference_method} with an unadjusted p-value of <b>{fmt(result["p"],4)}</b> at α = {alpha}.</div>')
        st.write('')
        st.caption(f'95% slope interval: {fmt(result["low"])} to {fmt(result["high"])} mm/decade')
        st.caption(f'Annual slope: {fmt(result["slope"],2)} mm/year')
        st.caption(f'Relative trend: {fmt(result["relative"])} %/decade · Fitted change: {fmt(result["change"])} mm')
        st.caption(f'Lag-1 annual residual correlation: {fmt(result["lag1"],2)}. This diagnostic does not correct the p-value.')
        st.caption('OLS assumes independent residuals; HAC and modified MK address autocorrelation under additional assumptions. Modified MK uses a Sen slope and has no autocorrelation-adjusted slope CI here. All inference is exploratory; non-significance does not prove no change, and significance does not establish cause.')
    render_trend_diagnostics(series,alpha,label)
    with st.container(border=True):
        st.markdown('### Exhibit B · Departures from the usual')
        standard = st.toggle('Standardized annual anomalies',key='standard')
        st.plotly_chart(anomaly_figure((z if standard else anomaly).sel(year=slice(start,end)),standard,series,baseline_mean),width='stretch',theme=None,key='anomalies')
        st.caption(f'Terracotta: below the {bstart}–{bend} baseline. Green: above baseline. Standardized anomalies use sample standard deviation and require at least 10 baseline years with nonzero variance. These are precipitation anomalies, not a formal drought index or SPI.')
    with st.expander('Monthly seasonality and anomalies'):
        seasonal = whole_monthly.sel(time=slice(f'{bstart}-01-01',f'{bend}-12-31')).groupby('time.month').mean('time')
        f = go.Figure(go.Bar(x=seasonal.month,y=seasonal.values,marker_color=CYAN))
        f.update_xaxes(tickvals=list(range(1,13)),ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
        f.update_yaxes(title_text='Baseline monthly rainfall (mm)')
        st.plotly_chart(style(f,240),width='stretch',theme=None,key='seasonal')
        monthly_anomaly = monthly_anomalies(whole_monthly,bstart,bend).sel(time=slice(f'{start}-01-01',f'{end}-12-31'))
        f = go.Figure(go.Bar(x=monthly_anomaly.time.values,y=monthly_anomaly.values,marker_color=np.where(monthly_anomaly.values<0,AMBER,CYAN)))
        f.update_yaxes(title_text='Monthly anomaly (mm)')
        st.plotly_chart(style(f,240),width='stretch',theme=None,key='monthly_anomaly')
        st.caption('Each monthly anomaly compares accumulated rainfall with the same calendar month in the reference baseline.')
    export = pd.DataFrame({'year':series.year.values,'precipitation_mm':series.values,
                            'anomaly_mm':anomaly.sel(year=series.year).values,'standardized_anomaly':z.sel(year=series.year).values})
    st.download_button('Take the evidence · Annual series CSV',export.to_csv(index=False),file_name='saharawatch_annual.csv',mime='text/csv')

with deficits:
    render_drought_panel(whole_series,whole_monthly,label,start,end,bstart,bend,years)

with comparison:
    render_comparison(annual,countries,start,end,bstart,bend,alpha,inference_method,weighting)

with guided:
    st.subheader('Explore a Climate Mystery')
    st.write('A good detective begins with a question. Open a file, follow the trail, and let the observations challenge your first impression.')
    investigations = [('morocco','Case 001 / Is Morocco becoming drier?','Inspect the fitted trend, annual variability, and uncertainty for the Morocco country mask.'),
                      ('compare','Case 002 / Across the border','Open Cross-examine to compare Morocco with Algeria on shared years and baselines.'),
                      ('anomaly','Case 003 / The dry-year files','Switch to the annual anomaly map, then change the observation year to explore rainfall deficits.'),
                      ('trends','Case 004 / Follow the strongest trail','Switch to the linear trend map. Hover to inspect magnitude, then use the significance layer to assess evidence.')]
    case_columns = st.columns(2)
    for index, (key,title,description) in enumerate(investigations):
        with case_columns[index % 2].container(border=True):
            st.markdown(f'### {title}')
            st.write(description)
            st.button('Open this case',key='preset_'+key,on_click=preset,args=(key,))
    st.caption('Presets configure live calculations; they do not encode conclusions. Results for the open case appear below.')
    active=st.session_state.get('active_case')
    guided_trends=cached_trends(file_stamp,start,end,window,inference_method) if active=='trends' else None
    render_live_investigation(annual,countries,start,end,bstart,bend,alpha,active,guided_trends,inference_method,weighting)

with notebook:
    st.subheader('Your field notebook')
    st.write('Make a prediction. Gather clues. Leave room to change your mind.')
    st.caption('The notebook stays in this browser session. Download your case report before closing or refreshing the session. Starting a fresh investigation clears it.')
    context = f'{label}|{start}|{end}|{bstart}|{bend}|{alpha}|{inference_method}|{weighting}'
    hypothesis = st.radio('Working hypothesis', ['Rainfall is decreasing', 'Rainfall is increasing', 'I am still investigating'],
                          key='hypothesis', horizontal=True)
    finite_fit = np.isfinite(result['p'])
    if not finite_fit:
        assessment = result.get('reason') or 'The record is too short for a trend assessment. Gather at least ten complete years.'
    elif result['p'] >= alpha:
        assessment = 'Inconclusive: this exploratory trend test does not establish a direction of change. A dry year alone does not prove a drying trend.'
    elif hypothesis == 'I am still investigating':
        assessment = f'The exploratory test detects a {"decrease" if result["slope"] < 0 else "increase"}. Inspect the uncertainty before drawing a conclusion.'
    else:
        matches = (result['slope'] < 0) == (hypothesis == 'Rainfall is decreasing')
        assessment = ('The exploratory trend supports your proposed direction.' if matches else 'The exploratory trend points in the opposite direction to your hypothesis.') + ' This does not establish a cause.'
    st.html(f'<div class="clue-card"><p class="eyebrow">Current lead / {html.escape(label)}</p><h3>{html.escape(result["status"])}</h3><p>{html.escape(assessment)}</p></div>')
    review_columns = st.columns(3)
    checks = [review_columns[i].checkbox(title, key=f'review_{i}_{context}') for i, title in enumerate([
        'I inspected the rainfall timeline', 'I checked the baseline & anomalies', 'I considered uncertainty & resolution'])]
    st.progress(sum(checks) / 3, text=f'{sum(checks)} / 3 evidence checks recorded — self-reported, not a scientific score')
    notes = st.text_area('Field notes', placeholder='What caught your eye? What other explanation would you investigate?', key=f'notes_{context}')
    st.session_state.setdefault('clues', [])
    if st.button('＋ Pin this evidence to the notebook', key='pin_evidence', type='primary'):
        snapshot = dict(location=label, period=f'{start}–{end}', baseline=f'{bstart}–{bend}',
                        source=f'GPCP {metadata["version"]} / NOAA PSL', inference_method=inference_method, country_weighting=weighting, source_sha256=metadata['sha256'], coverage=f'{metadata["start"]} to {metadata["end"]}',
                        hypothesis=hypothesis, mean_mm=fmt(result['mean']), trend_mm_decade=fmt(result['decade']),
                        p_value=fmt(result['p'], 6), confidence_interval=f'{fmt(result["low"])} to {fmt(result["high"])} mm/decade',
                        alpha=alpha, valid_years=result['n'], status=result['status'],
                        observation_year=anomaly_year, anomaly_mm=fmt(float(anomaly.sel(year=anomaly_year))),
                        checks=sum(checks), notes=notes, assessment=assessment,
                        recent_country_explanation=assessment_text(country_brief['country'],country_brief) if country_brief else '',
                        recent_country_briefing=dict(country_brief) if country_brief else None,
                        annual_data=json.loads(export.to_json(orient='records')),
                        chart_json={'rainfall':history_figure(series,result,float(baseline_mean)).to_json(),
                                    'anomalies':anomaly_figure(anomaly.sel(year=series.year),False,series,baseline_mean).to_json()})
        if snapshot.get('recent_country_briefing'):
            snapshot['recent_country_briefing']=json.loads(pd.Series(snapshot['recent_country_briefing']).to_json())
        if snapshot not in st.session_state['clues']:
            st.session_state['clues'].append(snapshot)
            st.success('Evidence pinned with its location, period, baseline, and uncertainty.')
        else:
            st.info('This exact evidence is already pinned. Change the location, period, hypothesis, or notes to add another lead.')
    clues = st.session_state['clues']
    st.markdown(f'### Pinned evidence · {len(clues):02d}')
    if not clues:
        st.info('Your notebook is empty. Inspect the atlas, then pin your first finding here.')
    board = render_evidence_board(clues)
    report = ['# SaharaWatch / Climate detective case report', '',
              'Exploratory historical rainfall analysis. Not a drought forecast or climate attribution.', '']
    for i, clue in enumerate(clues):
        with st.expander(f'Clue {i+1:02d} · {clue["location"]} · {clue["period"]}'):
            st.write(f'**{clue["status"]}**')
            st.write(f'Trend: {clue["trend_mm_decade"]} mm/decade · {clue.get('inference_method','OLS')} p = {clue["p_value"]} · 95% CI: {clue["confidence_interval"]}')
            st.caption(f'Baseline {clue["baseline"]} · {clue["valid_years"]} complete years · α = {clue["alpha"]} · {clue["source"]}')
            st.write(clue['assessment'])
            if clue.get('recent_country_explanation'):
                st.markdown('**Pinned recent country briefing**')
                st.write(clue['recent_country_explanation'])
            if clue['notes']:
                st.text(clue['notes'])
            st.button('Remove this clue', key=f'remove_clue_{i}', on_click=lambda index=i: st.session_state['clues'].pop(index))
        report.extend([f'## Clue {i+1:02d}', *[f'- {key.replace("_", " ")}: {value}' for key, value in clue.items() if key not in ['annual_data','chart_json','recent_country_briefing']], ''])
    if board['connections']:
        numbers = {clue_id(clue): index+1 for index, clue in enumerate(clues)}
        report.extend(['## Evidence relationships', 'User interpretations, not statistical tests or causal findings.', ''])
        report.extend(f'- Clue {numbers[edge["source"]]:02d} → Clue {numbers[edge["target"]]:02d}: {RELATIONS[edge["relation"]]}'
                      for edge in board['connections'])
        report.append('')
    report.extend(['## Scientific limits', 'Raw OLS inference assumes independent residuals; autocorrelation can understate uncertainty. Country summaries use the pinned center-point or fractional-area weighting method on a 2.5° grid. Anomalies are not SPI. Statistical significance does not establish causation.', '',
                   'Data: https://psl.noaa.gov/data/gridded/data.gpcp.html', 'Boundaries: Natural Earth (public domain).'])
    st.download_button('Download the case report · Markdown', '\n'.join(report), file_name='saharawatch_case_report.md',
                       mime='text/markdown', disabled=not clues)

    import hashlib
    report_fingerprint=hashlib.sha256(json.dumps(clues,sort_keys=True).encode()).hexdigest()
    if st.button('Build illustrated investigation report',disabled=not clues,key='build_rich_report'):
        try:
            with st.spinner('Rendering pinned charts and packaging observations…'):
                st.session_state['rich_report']=build_report_archive(clues)
                st.session_state['rich_report_key']=report_fingerprint
        except (ValueError,RuntimeError,OSError) as exc:
            st.error(f'Report could not be rendered: {exc}')
    if st.session_state.get('rich_report') and st.session_state.get('rich_report_key')==report_fingerprint:
        st.download_button('Download illustrated report · ZIP',st.session_state['rich_report'],file_name='saharawatch_investigation.zip',mime='application/zip')
        st.caption('Contains a self-contained HTML report with embedded PNG charts, standalone chart images, pinned observations, and metadata. This file records the clues used when Build was clicked.')

with methods:
    st.subheader('Observations first. Methods in the open.')
    st.markdown('''SaharaWatch is a historical Earth observation explorer for the NASA Space Apps challenge **Be An Earth System Trend Detective!** It helps investigate what changed, where, by how much, and with what statistical evidence.

**Source.** [GPCP monthly precipitation, distributed by NOAA PSL](https://psl.noaa.gov/data/gridded/data.gpcp.html), combines satellite estimates and rain-gauge observations. It is associated with the NASA-supported GPCP effort; these are not all direct NASA satellite measurements.

**Geography.** Grid centers are selected within 10–43° N, 18° W–63° E. Cells are 2.5° × 2.5°, displayed at their actual extent. The rectangular domain includes ocean and areas outside MENA. Country summaries use [Natural Earth 1:110m boundaries](https://www.naturalearthdata.com/about/terms-of-use/). Center-point mode uses cosine latitude weights. Fractional mode clips every 2.5° cell to the country polygon and measures overlap area in EPSG:6933 after boundary densification to 0.1°. Sub-cell rainfall is assumed uniform; this improves area allocation without adding observations or resolution. Coarse boundary cells, disputed areas, and one-cell countries limit precision. A missing member cell invalidates that regional time step rather than changing the area sampled.

**Units & missingness.** Monthly accumulation is the monthly mean rate in mm/day multiplied by the calendar month's days, including leap days. Annual totals sum only twelve valid months. Negative, nonfinite, fill, and out-of-range observations are missing. Incomplete years are withheld from annual controls. No data is interpolated or imputed.

**Trends.** SciPy ordinary least squares fits annual precipitation against calendar year. At least ten valid complete years are required. Slopes are reported in mm/decade; the two-sided p-value tests zero slope. The 95% slope interval uses Student's t with n−2 degrees of freedom. Relative slopes are withheld below a 10 mm/year mean. Fitted change is slope × elapsed years, not an endpoint observation difference.

**Uncertainty.** OLS assumes independent residuals and may understate uncertainty when climate residuals are serially correlated. Lag-1 residual correlation is a diagnostic only; selected-series Newey–West HAC inference is available in Statistical trend diagnostics. HAC uses consecutive annual observations, a Bartlett kernel, small-sample correction, and Student-t inference. The sidebar selects OLS, Newey–West HAC, or Hamed–Rao modified Mann–Kendall (up to three significant detrended-rank autocorrelation lags, screened at a fixed 5%) across maps, comparisons, guided cases, and notebook records. Modified MK reports a Sen slope; no autocorrelation-adjusted slope confidence interval is supplied. Invalid modified variance yields no significance result. The significance map optionally uses Benjamini–Hochberg FDR across all finite cell p-values in the rectangle, including ocean. Hover p-values are the selected method’s unadjusted p-values. FDR's usual guarantees rely on independence or appropriate positive dependence. Selected-location and country summaries report exploratory method-specific p-values without a spatial multiple-testing adjustment. The paired regional difference test fits first-minus-second annual rainfall with HAC, preserving cross-region covariance and requiring ten consecutive common valid years.

**Baselines.** Annual anomalies subtract the fixed baseline annual mean. Standardized anomalies divide by the baseline sample standard deviation (ddof=1); at least ten valid baseline years and positive variance are required. Monthly anomalies compare the same calendar month. Standardized anomalies are **not SPI**.

**SPI-3 / SPI-12.** The Rainfall deficits & SPI tab uses the pinned climate-indices 3.1.0 gamma implementation on accumulated monthly rainfall, with calendar-month fitting and calibration-period zero probability. Its separate default calibration is 1981–2010; at least 30 calibration years are required. Each calendar month needs ≥30 valid and ≥20 positive accumulated observations with nonzero positive-rainfall variance. Gamma fits with a missing or <0.05 library KS diagnostic are withheld as a conservative reliability screen, not a formal parameter-adjusted goodness-of-fit test. Scores are clipped by the library to ±3.09. Missing months invalidate rolling windows. SPI is fitted only on request for the selected series, not for the whole map. Results are validated against the reference library and an independent gamma-CDF calculation.

**Interpretation.** This is not a forecast. Rainfall deficits relate to meteorological drought but do not fully describe agricultural or hydrological drought. Coarse GPCP cells cannot support city or field-level claims. A significant trend does not establish cause, and a nonsignificant result does not prove no change.''')
    st.info(metadata['attributes'].get('data_comment','Source provisional status not specified.'))
    st.caption('Source-file compatibility: unused time_bnds contains invalid fill dates. It is excluded from decoding; the actual time coordinate is decoded and validated. No measurements are replaced.')
    st.write(f'Dataset: {metadata["title"]} · {metadata["version"]} · {metadata["start"]} to {metadata["end"]}')
    st.code(metadata['attributes'].get('citation',''),language=None)
    st.json({k:v for k,v in metadata.items() if k not in ['attributes','variable_attributes']})
    provenance = ROOT / 'data/processed/provenance.json'
    if provenance.exists():
        st.download_button('Download preparation provenance',provenance.read_text(),file_name='provenance.json',mime='application/json')

st.html('<div class="footer">SAHARAWATCH / CLIMATE DETECTIVE BUREAU &nbsp; · &nbsp; No hunch without evidence. &nbsp; · &nbsp; Data provided by NOAA PSL, Boulder, Colorado, USA. GPCP satellite–gauge analysis. &nbsp; · &nbsp; Natural Earth boundaries.</div>')
