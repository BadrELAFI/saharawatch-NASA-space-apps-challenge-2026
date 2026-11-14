"""SaharaWatch Streamlit dashboard. Run: streamlit run app.py."""
import html
import json
import numpy as np
import pandas as pd
import streamlit as st
from saharawatch.data import (ROOT, RAW, VARIABLES, load_data, complete_years, grid_series,
                              select_period, boundaries, country_mask, regional_series)
from saharawatch.analysis import trend, trend_grid, annual_anomalies, fdr_bh, monthly_anomalies
from saharawatch.plots import map_figure, history_figure, anomaly_figure, style, CYAN, AMBER
import plotly.graph_objects as go

st.set_page_config(page_title='SaharaWatch · MENA Climate Intelligence',page_icon='◉',layout='wide')
st.html(f'<style>{(ROOT / "assets/styles.css").read_text()}</style>')


@st.cache_data(show_spinner='Reading and validating real GPCP precipitation…')
def cached_data(stamp):
    return load_data()


@st.cache_data(show_spinner=False)
def cached_trends(stamp, start, end, _annual):
    # File identity and selected years fully identify the excluded xarray argument.
    return trend_grid(_annual)


@st.cache_data(show_spinner=False)
def cached_mask(lat, lon, feature):
    import xarray as xr
    grid = xr.DataArray(np.zeros((len(lat),len(lon))),dims=('lat','lon'),coords={'lat':lat,'lon':lon})
    return country_mask(grid,feature)


def fmt(value, digits=1):
    return f'{value:,.{digits}f}' if np.isfinite(value) else 'Unavailable'


def reset():
    for key in list(st.session_state):
        del st.session_state[key]


def preset(name):
    st.session_state.update(mode='Country aggregation',country='Morocco',first_country='Morocco',period=default_period)
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
indicators = ['Mean annual rainfall','Linear trend','Relative trend','Annual anomaly','Standardized anomaly','Trend significance']
with st.sidebar:
    st.html('<div class="brand"><i class="brand-symbol"></i> Sahara<span>Watch</span></div><p class="eyebrow">Earth observation / MENA</p>')
    st.divider()
    st.caption('01 / LOCATION')
    mode = st.radio('Selection mode',['Grid cell','Country aggregation'] if countries else ['Grid cell'],key='mode',horizontal=True)
    feature = None
    selected = None
    if mode == 'Country aggregation':
        country = st.selectbox('Country',country_names,index=country_names.index('Morocco'),key='country')
        feature = countries[country]
        mask = cached_mask(annual.lat.values,annual.lon.values,feature)
        st.caption(f'{int(mask.sum())} grid-cell centers · cosine latitude weighting')
    else:
        lat = st.number_input('Latitude (° N)',min_value=10.,max_value=43.,value=31.25,step=2.5,key='lat')
        lon = st.number_input('Longitude (° E)',min_value=-18.,max_value=63.,value=-6.25,step=2.5,key='lon')
    st.divider()
    st.caption('02 / ANALYSIS')
    st.selectbox('Environmental variable',list(VARIABLES),format_func=lambda k:VARIABLES[k]['label'],key='variable')
    indicator = st.selectbox('Map indicator',indicators,key='indicator')
    start,end = st.slider('Analysis period',years[0],years[-1],default_period,key='period')
    with st.expander('Baseline & statistical settings',expanded=indicator in ['Annual anomaly','Standardized anomaly','Trend significance']):
        bstart,bend = st.slider('Reference baseline',years[0],years[-1],default_baseline,key='baseline')
        alpha = st.selectbox('Significance threshold α',[0.01,0.05,0.10],index=1,key='alpha')
        correction = st.radio('Map significance',['Benjamini–Hochberg FDR','Raw p-values'],key='correction')
        st.caption('95% slope intervals remain fixed. Baselines and trends each require ≥10 complete years.')
    st.button('Reset exploration',on_click=reset,width='stretch')
    st.divider()
    st.caption(f'AVAILABLE RECORD\n\n{metadata["start"][:7]} → {metadata["end"][:7]}\n\nAnnual analysis excludes incomplete years.')
    st.markdown('[Dataset & attribution ↗](https://psl.noaa.gov/data/gridded/data.gpcp.html)')

st.html('<p class="eyebrow">Historical climate observatory</p><h1>Follow the rainfall. Find the change.</h1><p class="subtitle">Earth System Trend Intelligence for MENA.</p>')
st.html(f'<span class="source-pill">● GPCP {metadata["version"]} / NOAA PSL</span><span class="source-pill">{start} — {end}</span><span class="source-pill">2.5° × 2.5° · Monthly observations</span>')
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
    result = trend(series.year.values,series.values,alpha)
    anomaly,z,baseline_mean = annual_anomalies(whole_series,bstart,bend)
except ValueError as exc:
    st.warning(str(exc)); st.stop()

explorer,comparison,guided,methods = st.tabs(['Precipitation explorer','Regional comparison','Explore a Climate Mystery','Data & methodology'])
with explorer:
    titlecol,controlcol = st.columns([3,1])
    with titlecol:
        st.subheader('The MENA precipitation atlas')
        st.caption(f'{indicator.upper()} / {start}–{end}')
    with controlcol:
        anomaly_year = st.selectbox('Observation year',list(range(start,end+1)),index=end-start,
                                    disabled=indicator not in ['Annual anomaly','Standardized anomaly'],key='anomaly_year')
    pvalues = None
    diverging = indicator != 'Mean annual rainfall'
    significance = indicator == 'Trend significance'
    if indicator == 'Mean annual rainfall':
        values,units = window.mean('year'),'mm/year'
    elif indicator in ['Annual anomaly','Standardized anomaly']:
        grid_anomaly,grid_z,_ = annual_anomalies(annual,bstart,bend)
        values = (grid_anomaly if indicator == 'Annual anomaly' else grid_z).sel(year=anomaly_year)
        units = 'mm' if indicator == 'Annual anomaly' else 'σ'
    else:
        trends = cached_trends(file_stamp,start,end,window)
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
    if indicator in ['Annual anomaly','Standardized anomaly']:
        period_text = f'{anomaly_year} vs. {bstart}–{bend} baseline'
    figure = map_figure(values,indicator,units,period_text,pvalues=pvalues,selected=selected,
                        feature=feature,diverging=diverging,significance=significance)
    st.plotly_chart(figure,width='stretch',theme=None,key='map',config={'scrollZoom':True,'displaylogo':False})
    if significance:
        st.caption(f'{correction} at α = {alpha}. Orange: significant decrease · dark: no significant trend detected · teal: significant increase. Missing cells are unfilled. Hover shows raw p-values; FDR tests all valid cells in the study rectangle, including ocean.')
    else:
        st.caption('Pan, zoom, and hover to investigate. Every square is an actual 2.5° GPCP cell, including ocean; no spatial interpolation. Unfilled cells have insufficient data. Select coordinates or a country in the sidebar.')
    if indicator == 'Relative trend':
        st.caption('Relative trends are withheld where mean annual rainfall is below 10 mm/year.')
    if indicator == 'Standardized anomaly':
        st.caption('Annual standardized anomaly = (observed − baseline mean) / baseline sample standard deviation. This is not SPI.')
    st.markdown(f'### {label}')
    if mode == 'Country aggregation':
        st.caption('Approximate national series: Natural Earth center-point mask with cosine latitude weights. Boundary cells are not fractionally allocated; very small countries may contain only one cell. Boundaries are descriptive and do not imply endorsement.')
    cols = st.columns(4)
    cols[0].metric('Mean annual rainfall',fmt(result['mean'])+' mm')
    cols[1].metric('Linear trend',fmt(result['decade'])+' mm/decade')
    cols[2].metric('OLS p-value',fmt(result['p'],4))
    cols[3].metric('Complete years',str(result['n']))
    st.write('')
    left,right = st.columns([2.3,1])
    with left:
        st.markdown('### Rainfall through time')
        view = st.radio('Time resolution',['Annual','Monthly'],horizontal=True,key='resolution')
        moving = st.checkbox('Show moving average',key='moving')
        displayed = whole_monthly.sel(time=slice(f'{start}-01-01',f'{end}-12-31')) if view == 'Monthly' else series
        st.plotly_chart(history_figure(displayed,result,baseline=float(baseline_mean),moving=moving,monthly=view=='Monthly'),
                        width='stretch',theme=None,key='history')
        st.caption(f'Annual totals require 12 valid months. Baseline: {bstart}–{bend}. Monthly totals preserve seasonality; annual OLS statistics above do not change with chart resolution.')
    with right:
        st.markdown('### Reading the evidence')
        st.html(f'<div class="insight"><b>{html.escape(result["status"])}</b><br><br>Over {start}–{end}, the fitted annual rainfall trend is <b>{fmt(result["decade"])} mm per decade</b> with a raw OLS p-value of <b>{fmt(result["p"],4)}</b> at α = {alpha}.</div>')
        st.write('')
        st.caption(f'95% slope interval: {fmt(result["low"])} to {fmt(result["high"])} mm/decade')
        st.caption(f'Annual slope: {fmt(result["slope"],2)} mm/year')
        st.caption(f'Relative trend: {fmt(result["relative"])} %/decade · Fitted change: {fmt(result["change"])} mm')
        st.caption(f'Lag-1 annual residual correlation: {fmt(result["lag1"],2)}. This diagnostic does not correct the p-value.')
        st.caption('OLS inference is exploratory and assumes independent residuals. Non-significance does not prove no change. Significance does not establish causality.')
    with st.container(border=True):
        st.markdown('### Wet years. Dry years. A consistent reference.')
        standard = st.toggle('Standardized annual anomalies',key='standard')
        st.plotly_chart(anomaly_figure((z if standard else anomaly).sel(year=slice(start,end)),standard,series,baseline_mean),width='stretch',theme=None,key='anomalies')
        st.caption(f'Orange: below the {bstart}–{bend} baseline. Teal: above baseline. Standardized anomalies use sample standard deviation and require at least 10 baseline years with nonzero variance. These are precipitation anomalies, not a formal drought index or SPI.')
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
    st.download_button('Download selected annual series · CSV',export.to_csv(index=False),file_name='saharawatch_annual.csv',mime='text/csv')

with comparison:
    st.subheader('Different regions. A shared record.')
    st.caption(f'Shared analysis period {start}–{end} · shared baseline {bstart}–{bend}')
    if len(countries) < 2:
        st.info('Country boundaries are unavailable. Grid-cell exploration remains available.')
    else:
        ca,cb = st.columns(2)
        first = ca.selectbox('First country',country_names,index=country_names.index('Morocco'),key='first_country')
        second = cb.selectbox('Second country',country_names,index=country_names.index('Algeria'),key='compare_country')
        normalize = st.toggle('Compare standardized anomalies',key='normalize_compare')
        chart = go.Figure()
        for name,col,color in [(first,ca,CYAN),(second,cb,AMBER)]:
            cmask = cached_mask(annual.lat.values,annual.lon.values,countries[name])
            try:
                full = regional_series(annual,cmask)
            except ValueError as exc:
                st.warning(f'{name}: {exc}'); continue
            s = full.sel(year=slice(start,end))
            r = trend(s.year,s,alpha)
            an,zz,_ = annual_anomalies(full,bstart,bend)
            col.metric(f'{name} · mean annual rainfall',fmt(r['mean'])+' mm')
            col.markdown(f'**{fmt(r["decade"])} mm/decade** · p = {fmt(r["p"],4)}')
            col.caption(f'{r["status"]}. {end} anomaly: {fmt(float(an.sel(year=end)))} mm. {int(cmask.sum())} cell centers.')
            plotted = zz.sel(year=s.year) if normalize else s
            chart.add_trace(go.Scatter(x=s.year.values,y=plotted.values,name=name,mode='lines+markers',line=dict(color=color,width=2)))
        chart.update_yaxes(title_text='Standardized anomaly (σ)' if normalize else 'Annual precipitation (mm)')
        st.plotly_chart(style(chart,380),width='stretch',theme=None,key='comparison')
        st.caption('Country masks use fixed center-point membership and cosine latitude weighting. The two slopes have not been tested for a statistically significant difference. Different climates can have very different absolute rainfall variability.')

with guided:
    st.subheader('Explore a Climate Mystery')
    st.write('Begin with a question. Follow the observations, then weigh the evidence.')
    investigations = [('morocco','01 / Is Morocco becoming drier?','Inspect the fitted trend, annual variability, and uncertainty for the Morocco country mask.'),
                      ('compare','02 / Different regions, different trends','Open Regional comparison to compare Morocco with Algeria on shared years and baselines.'),
                      ('anomaly','03 / Detect historical dry periods','Switch to the annual anomaly map, then change the observation year to explore rainfall deficits.'),
                      ('trends','04 / Where are trends strongest?','Switch to the linear trend map. Hover to inspect magnitude, then use the significance layer to assess evidence.')]
    for key,title,description in investigations:
        with st.container(border=True):
            st.markdown(f'### {title}')
            st.write(description)
            st.button('Start investigation',key='preset_'+key,on_click=preset,args=(key,))
    st.caption('Presets configure live calculations; they do not encode conclusions. Return to Precipitation explorer after starting an investigation.')

with methods:
    st.subheader('Observations first. Methods in the open.')
    st.markdown('''SaharaWatch is a historical Earth observation explorer for the NASA Space Apps challenge **Be An Earth System Trend Detective!** It helps investigate what changed, where, by how much, and with what statistical evidence.

**Source.** [GPCP monthly precipitation, distributed by NOAA PSL](https://psl.noaa.gov/data/gridded/data.gpcp.html), combines satellite estimates and rain-gauge observations. It is associated with the NASA-supported GPCP effort; these are not all direct NASA satellite measurements.

**Geography.** Grid centers are selected within 10–43° N, 18° W–63° E. Cells are 2.5° × 2.5°, displayed at their actual extent. The rectangular domain includes ocean and areas outside MENA. Country masks use [Natural Earth 1:110m boundaries](https://www.naturalearthdata.com/about/terms-of-use/) with center-point inclusion and cosine latitude weighting. Coarse boundary cells, disputed areas, and one-cell countries limit precision. A missing member cell invalidates that regional time step rather than changing the area sampled.

**Units & missingness.** Monthly accumulation is the monthly mean rate in mm/day multiplied by the calendar month's days, including leap days. Annual totals sum only twelve valid months. Negative, nonfinite, fill, and out-of-range observations are missing. Incomplete years are withheld from annual controls. No data is interpolated or imputed.

**Trends.** SciPy ordinary least squares fits annual precipitation against calendar year. At least ten valid complete years are required. Slopes are reported in mm/decade; the two-sided p-value tests zero slope. The 95% slope interval uses Student's t with n−2 degrees of freedom. Relative slopes are withheld below a 10 mm/year mean. Fitted change is slope × elapsed years, not an endpoint observation difference.

**Uncertainty.** OLS assumes independent residuals and may understate uncertainty when climate residuals are serially correlated. Lag-1 residual correlation is a diagnostic only; robust inference is not implemented. The significance map optionally uses Benjamini–Hochberg FDR across all finite cell p-values in the rectangle, including ocean. Hover p-values remain raw. FDR's usual guarantees rely on independence or appropriate positive dependence. Selected-location and country summaries report raw exploratory p-values.

**Baselines.** Annual anomalies subtract the fixed baseline annual mean. Standardized anomalies divide by the baseline sample standard deviation (ddof=1); at least ten valid baseline years and positive variance are required. Monthly anomalies compare the same calendar month. Standardized anomalies are **not SPI**.

**Interpretation.** This is not a forecast. Rainfall deficits relate to meteorological drought but do not fully describe agricultural or hydrological drought. Coarse GPCP cells cannot support city or field-level claims. A significant trend does not establish cause, and a nonsignificant result does not prove no change.''')
    st.info(metadata['attributes'].get('data_comment','Source provisional status not specified.'))
    st.caption('Source-file compatibility: unused time_bnds contains invalid fill dates. It is excluded from decoding; the actual time coordinate is decoded and validated. No measurements are replaced.')
    st.write(f'Dataset: {metadata["title"]} · {metadata["version"]} · {metadata["start"]} to {metadata["end"]}')
    st.code(metadata['attributes'].get('citation',''),language=None)
    st.json({k:v for k,v in metadata.items() if k not in ['attributes','variable_attributes']})
    provenance = ROOT / 'data/processed/provenance.json'
    if provenance.exists():
        st.download_button('Download preparation provenance',provenance.read_text(),file_name='provenance.json',mime='application/json')

st.html('<div class="footer">SAHARAWATCH &nbsp; / &nbsp; Historical evidence, openly explored. &nbsp; · &nbsp; Data provided by NOAA PSL, Boulder, Colorado, USA. GPCP satellite–gauge analysis. &nbsp; · &nbsp; Natural Earth boundaries.</div>')
