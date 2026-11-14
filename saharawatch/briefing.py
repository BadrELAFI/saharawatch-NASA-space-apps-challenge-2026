"""Evidence-led recent rainfall explanations, not forecasts or vulnerability scores."""
import html
import numpy as np
import pandas as pd
import xarray as xr
import streamlit as st
import plotly.graph_objects as go
from .analysis import MIN_BASELINE_YEARS
from .inference import analyze_trend
from .data import country_weights, regional_series
from .plots import style, AMBER, CYAN


def recent_assessment(full, end, length, bstart, bend):
    """Compare a complete consecutive window against a fixed historical baseline.

    Historical rarity is an empirical midrank among complete overlapping windows
    wholly within the baseline. It is descriptive, not a p-value or SPI.
    """
    if full.dims!=('year',) or length<1 or bstart>=bend:
        raise ValueError('Use one annual series, a positive window length, and an ordered baseline.')
    start=end-length+1
    years=np.arange(start,end+1)
    recent=full.reindex(year=years)
    baseline=full.reindex(year=np.arange(bstart,bend+1))
    valid_base=baseline.where(np.isfinite(baseline),drop=True)
    result=dict(recent_start=start,recent_end=end,length=length,baseline_start=bstart,baseline_end=bend,
                baseline_years=int(valid_base.size),valid_recent_years=int(np.isfinite(recent).sum()),
                status='Insufficient data',total_mm=np.nan,expected_mm=np.nan,departure_mm=np.nan,
                departure_pct=np.nan,dry_years=None,severe_years=None,historical_percentile=np.nan,
                reference_windows=0,reference_lower=0,reference_equal=0,reason='',
                annual_years=years.tolist(),annual_mm=[float(v) if np.isfinite(v) else None for v in recent.values])
    if valid_base.size<MIN_BASELINE_YEARS:
        result['reason']='Fewer than ten complete baseline years are available.';return result
    if result['valid_recent_years']!=length:
        result['reason']='The assessment requires every year in the recent period; missing years are not extrapolated.';return result
    mean=float(valid_base.mean());std=float(valid_base.std(ddof=1))
    total=float(recent.sum());expected=mean*length
    dry=int((recent<mean).sum())
    tolerance=1e-9
    if total<expected-tolerance:
        status='Persistent rainfall deficit' if dry==length else 'Multi-year rainfall deficit'
    else:
        status='No multi-year rainfall deficit'
    reference=baseline.rolling(year=length,min_periods=length).sum().dropna('year')
    lower=int((reference<total-tolerance).sum())
    equal=int((abs(reference-total)<=tolerance).sum())
    percentile=100*(lower+.5*equal)/reference.size if reference.size>=10 and float(reference.std())>tolerance else np.nan
    severe=int(((recent-mean)/std<=-1.5).sum()) if std>tolerance else None
    result.update(status=status,total_mm=total,expected_mm=expected,departure_mm=total-expected,
                  departure_pct=100*(total-expected)/expected if mean>=10 else np.nan,
                  dry_years=dry,severe_years=severe,historical_percentile=percentile,
                  reference_windows=int(reference.size),reference_lower=lower,reference_equal=equal,
                  baseline_annual_mean_mm=mean,baseline_annual_std_mm=std)
    return result


def assessment_text(name, r):
    """A deterministic conclusion with explicit quantity, baseline, and limits."""
    period=f'{r["recent_start"]}–{r["recent_end"]}'
    baseline=f'{r["baseline_start"]}–{r["baseline_end"]}'
    if r['status']=='Insufficient data':
        return f'{name}: a recent rainfall assessment for {period} is unavailable. {r["reason"]}'
    direction='below' if r['departure_mm']<0 else 'above' if r['departure_mm']>0 else 'equal to'
    comparison=(f'{abs(r["departure_pct"]):.1f}% {direction}' if np.isfinite(r['departure_pct']) else
                f'{abs(r["departure_mm"]):.1f} mm {direction}')
    opening=(f'{name} experienced a persistent precipitation deficit: every year in {period} was drier than its baseline annual mean.'
             if r['status']=='Persistent rainfall deficit' else
             f'{name} received less rain than expected over {period}, but the deficit did not persist in every year.'
             if r['status']=='Multi-year rainfall deficit' else
             f'{name} did not show an overall rainfall deficit over {period}, although individual dry years can still occur.')
    sentence=(f'{opening} Total rainfall was {r["total_mm"]:.1f} mm, {comparison} '
              f'the {r["expected_mm"]:.1f} mm expected from the {baseline} baseline. '
              f'{r["dry_years"]} of {r["length"]} years were below the baseline annual mean.')
    if np.isfinite(r['historical_percentile']):
        if r['reference_lower']==0 and r['reference_equal']==0:
            sentence+=f' This total was lower than every one of the {r["reference_windows"]} complete {r["length"]}-year periods wholly within that baseline.'
        else:
            sentence+=f' Its rainfall total lies at the {r["historical_percentile"]:.1f}th percentile among {r["reference_windows"]} complete historical {r["length"]}-year periods in the baseline (lower means drier).'
    else:
        sentence+=' Historical rarity is unavailable because too few comparable windows or insufficient variability remain.'
    if r['length']>=2:
        last,previous=r['annual_mm'][-1],r['annual_mm'][-2]
        movement='increased' if last>previous+1e-9 else 'decreased' if last<previous-1e-9 else 'was unchanged'
        relation='below' if last<r['baseline_annual_mean_mm']-1e-9 else 'above' if last>r['baseline_annual_mean_mm']+1e-9 else 'equal to'
        sentence+=f' Rainfall in {r["recent_end"]} {movement} to {last:.1f} mm from {previous:.1f} mm in {r["recent_end"]-1}; it was {relation} the {r["baseline_annual_mean_mm"]:.1f} mm baseline annual mean.'
    if not np.isfinite(r['departure_pct']):
        sentence+=' Percentage deficits are withheld because mean baseline rainfall is below 10 mm/year.'
    return sentence


def deficit_footprint(annual, weights, end, length, bstart, bend):
    """Area represented by below-baseline cells, with valid spatial coverage shown."""
    if weights.dtype==bool:
        w=np.cos(np.deg2rad(annual.lat)).broadcast_like(weights).where(weights,0)
    else:w=weights
    base=annual.reindex(year=np.arange(bstart,bend+1))
    recent=annual.reindex(year=np.arange(end-length+1,end+1))
    valid=(base.count('year')>=10)&(recent.count('year')==length)
    expected=base.mean('year')*length
    dry=recent.sum('year',skipna=False)<expected
    covered=float(w.where(valid,0).sum());total=float(w.sum())
    return dict(coverage_pct=100*covered/total if total>0 else np.nan,
                deficit_area_pct=100*float(w.where(valid&dry,0).sum())/covered if covered>0 else np.nan)


@st.cache_data(show_spinner=False,max_entries=128)
def cached_weights(lat,lon,feature,weighting):
    grid=xr.DataArray(np.zeros((len(lat),len(lon))),coords={'lat':lat,'lon':lon},dims=('lat','lon'))
    return country_weights(grid,feature,weighting)


@st.cache_data(show_spinner='Preparing country rainfall briefings…',max_entries=64)
def country_briefings(source_id,countries,end,length,bstart,bend,weighting,analysis_start,analysis_end,alpha,method,_annual):
    rows=[]
    for name,feature in sorted(countries.items()):
        weights=cached_weights(_annual.lat.values,_annual.lon.values,feature,weighting)
        try:
            full=regional_series(_annual,weights)
            r=recent_assessment(full,end,length,bstart,bend)
        except ValueError as exc:
            r=recent_assessment(xr.DataArray(np.full(_annual.sizes['year'],np.nan),coords={'year':_annual.year},dims='year'),end,length,bstart,bend)
            r['reason']=str(exc)
            rows.append(dict(r,country=name));continue
        recent=full.sel(year=slice(analysis_start,analysis_end))
        fit=analyze_trend(recent.year.values,recent.values,alpha,method)
        r.update(country=name,trend_status=fit['status'],trend_mm_decade=fit['decade'],trend_p=fit['p'],
                 inference_method=method,country_weighting=weighting,analysis_start=analysis_start,analysis_end=analysis_end,alpha=alpha,source_sha256=source_id,
                 **deficit_footprint(_annual,weights,end,length,bstart,bend))
        rows.append(r)
    return rows


def render_country_briefing(annual,countries,years,source_id,bstart,bend,weighting,start,end,alpha,method,
                           current_country=None,on_country_change=None):
    if not countries:return None
    st.subheader('Country briefing · What the recent rainfall tells us')
    st.caption('Area-weighted country-average precipitation conditions, compared with each country’s own historical baseline. This is not a forecast or a ranking of drought vulnerability.')
    a,b,c=st.columns([1.5,1,1])
    names=sorted(countries)
    if current_country and st.session_state.get('_brief_main_country')!=current_country:
        st.session_state['brief_country']=current_country
        st.session_state['_brief_main_country']=current_country
    name=a.selectbox('Country briefing',names,index=names.index('Morocco') if 'Morocco' in names else 0,
                     key='brief_country',on_change=on_country_change)
    latest=years[-1]
    st.session_state.setdefault('brief_end',latest)
    finish=b.selectbox('Assessment ending year',years,key='brief_end')
    length=c.selectbox('Recent period (complete years)',[3,5,10],key='brief_length')
    st.caption(f'Assessment: {finish-length+1}–{finish}. Latest complete dataset year: {latest}; the current incomplete year is excluded. '
               f'The long-term trend context uses your separate {start}–{end} analysis window.')
    if finish>=bstart and finish-length+1<=bend:
        st.caption('The assessment overlaps the reference baseline. This is a descriptive comparison, not an independent significance test.')
    rows=country_briefings(source_id,countries,finish,length,bstart,bend,weighting,start,end,alpha,method,annual)
    r=next(row for row in rows if row['country']==name)
    st.html(f'<div class="clue-card briefing-verdict"><p class="eyebrow">{html.escape(name)} / {r["recent_start"]}–{r["recent_end"]}</p>'
            f'<h3>{html.escape(r["status"])}</h3><p>{html.escape(assessment_text(name,r))}</p></div>')
    with st.expander('Why this assessment? Spatial evidence and long-term context'):
        if r['status']!='Insufficient data':
            if np.isfinite(r['deficit_area_pct']):
                st.write(f'**How widespread was it?** {r["deficit_area_pct"]:.1f}% of the area-weighted country mask was represented by cells with below-baseline accumulated rainfall '
                         f'({r["coverage_pct"]:.1f}% valid spatial coverage). This describes coarse grid-cell conditions, not individual farms or cities.')
            if r['severe_years'] is not None:
                st.write(f'**How pronounced were the annual deficits?** {r["severe_years"]} of {length} years had an annual standardized anomaly ≤ −1.5 relative to the baseline. These annual z-scores are not SPI or an official drought declaration.')
            context=(f'**Does the longer record agree?** The {start}–{end} country trend is {r["trend_mm_decade"]:.1f} mm/decade '
                     f'using {method} (p = {r["trend_p"]:.4g}): {r["trend_status"].lower()}. '
                     'Recent deficits and long-term trend significance answer different questions.' if np.isfinite(r['trend_p']) else
                     f'**Long-term context:** no valid {method} significance assessment is available for {start}–{end}; this does not erase the observed recent rainfall totals.')
            st.write(context)
            if np.isfinite(r['trend_p']):
                drying=r['trend_p']<alpha and r['trend_mm_decade']<0
                wetting=r['trend_p']<alpha and r['trend_mm_decade']>0
                deficit=r['departure_mm']<0
                if deficit and drying:
                    st.write('The recent precipitation deficit and the longer-term drying signal point in the same direction.')
                elif deficit and wetting:
                    st.write('The recent dry period occurred despite a longer-term increase in rainfall. A short dry spell and a long-term wetting trend can coexist.')
                elif deficit:
                    st.write('The recent rainfall shortfall is observed, but the longer record does not establish a significant drying trend at the selected threshold.')
                elif drying:
                    st.write('Recent rainfall was not below the multi-year baseline expectation, but the longer record still shows a drying signal. Recent recovery does not erase a longer-term trend.')
                else:
                    st.write('This assessment does not identify an overall recent rainfall shortfall; it does not establish that drought impacts or water shortages are absent.')
        st.caption('Persistent deficit means every assessed year was below its baseline annual mean. The historical percentile compares complete, overlapping windows within the baseline; it is descriptive, not an independent-sample significance test, SPI, or a probability of future drought. '
                   'Precipitation evidence alone cannot establish agricultural/hydrological drought, susceptibility, or impacts. Temperature, evaporative demand, soil moisture, water availability and exposure also matter.')
    with st.expander('Show the rainfall behind this assessment'):
        if r['status']!='Insufficient data':
            observed=np.array([np.nan if v is None else v for v in r['annual_mm']])
            f=go.Figure(go.Bar(x=r['annual_years'],y=observed,marker_color=np.where(observed<r['baseline_annual_mean_mm'],AMBER,CYAN),
                              hovertemplate='%{x}: %{y:.1f} mm<extra></extra>'))
            f.add_hline(y=r['baseline_annual_mean_mm'],line_dash='dot',line_color='#8b784f',annotation_text='Baseline annual mean')
            f.update_yaxes(title_text='Annual rainfall (mm)')
            st.dataframe(pd.DataFrame({'year':r['annual_years'],'observed_mm':observed,
                'baseline_annual_mean_mm':r['baseline_annual_mean_mm'],'anomaly_mm':observed-r['baseline_annual_mean_mm']}),hide_index=True,width='stretch')
            if st.checkbox('Plot recent annual rainfall',key='brief_plot'):
                st.plotly_chart(style(f,240),width='stretch',theme=None,key='briefing_history')
        st.json({k:v for k,v in r.items() if k not in ['annual_mm','annual_years']})
    with st.expander('Compare recent precipitation conditions across countries'):
        frame=pd.DataFrame(rows)
        columns=['country','status','departure_pct','dry_years','historical_percentile','reference_windows','deficit_area_pct','coverage_pct']
        available=[k for k in columns if k in frame.columns]
        st.dataframe(frame[available].sort_values('historical_percentile',na_position='last'),hide_index=True,width='stretch')
        st.caption('Lower historical percentiles indicate a drier recent window relative to that country’s own reference climate. Differences are descriptive; they are not a formal test of differing drought susceptibility. Percentages are withheld for near-zero rainfall baselines.')
        export=frame.drop(columns=['annual_years','annual_mm'],errors='ignore').copy()
        export['source_sha256']=source_id
        st.download_button('Download country rainfall briefings · CSV',export.to_csv(index=False),file_name='saharawatch_recent_country_briefings.csv',mime='text/csv',key='briefings_export')
    return r
