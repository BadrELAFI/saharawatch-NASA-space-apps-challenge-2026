"""Shared-window comparisons of country masks or actual GPCP grid cells."""
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from .analysis import trend, annual_anomalies
from .data import country_mask, regional_series, grid_series
from .plots import history_figure, style, CYAN, AMBER


def comparison_summary(full, name, start, end, bstart, bend, alpha=.05):
    series=full.sel(year=slice(start,end))
    result=trend(series.year.values,series.values,alpha)
    anomaly,_,_=annual_anomalies(full,bstart,bend)
    return dict(result,selection=name,analysis_start=start,analysis_end=end,baseline_start=bstart,
                baseline_end=bend,alpha=alpha,recent_year=end,recent_anomaly_mm=float(anomaly.sel(year=end)))


def comparison_interpretation(first, second):
    """Compare estimated magnitudes only, never infer significance of a difference."""
    a,b=first,second
    if not all(np.isfinite(r['decade']) for r in (a,b)):
        return 'At least one series has insufficient observations to compare fitted trends.'
    signs=np.sign([a['decade'],b['decade']])
    direction=('Both fitted trends have the same direction.' if signs[0]==signs[1] and signs[0]!=0 else
               'The fitted trends have opposite directions.' if signs[0]*signs[1]<0 else
               'At least one fitted trend is zero.')
    def larger(key,unit):
        if not all(np.isfinite(r[key]) for r in (a,b)):
            return f'Relative trend comparison is unavailable because a mean is below 10 mm/year or a fit is unavailable.'
        if np.isclose(abs(a[key]),abs(b[key])):
            return f'The estimated {unit} magnitudes are equal within numerical precision.'
        chosen=a if abs(a[key])>abs(b[key]) else b
        return f'{chosen["selection"]} has the larger estimated {unit} magnitude ({abs(chosen[key]):.2f}).'
    return ' '.join([direction,larger('decade','absolute trend in mm/decade'),larger('relative','relative trend in %/decade'),
                     'These comparisons do not test whether the two slopes differ significantly.'])


def render_comparison(annual, countries, start, end, bstart, bend, alpha):
    st.subheader('Cross-examine two landscapes')
    st.caption(f'Shared analysis period {start}–{end} · shared baseline {bstart}–{bend} · raw OLS α = {alpha}')
    mode=st.radio('Comparison geography',['Countries','Grid cells'] if len(countries)>=2 else ['Grid cells'],
                  horizontal=True,key='comparison_mode')
    columns=st.columns(2)
    selected=[]
    for i,(col,side) in enumerate(zip(columns,['First','Second'])):
        with col:
            if mode=='Countries':
                names=sorted(countries)
                default='Morocco' if i==0 else 'Algeria'
                name=st.selectbox(f'{side} country',names,index=names.index(default),key='first_country' if i==0 else 'compare_country')
                mask=country_mask(annual,countries[name])
                try:
                    full=regional_series(annual,mask)
                except ValueError as exc:
                    st.warning(f'{name}: {exc}'); continue
                st.caption(f'{int(mask.sum())} cell centers · fixed boundary mask · cosine latitude weights')
            else:
                lat=st.number_input(f'{side} cell latitude (° N)',10.,43.,31.25 if i==0 else 33.75,step=2.5,key=f'compare_lat_{i}')
                lon=st.number_input(f'{side} cell longitude (° E)',-18.,63.,-6.25 if i==0 else 8.75,step=2.5,key=f'compare_lon_{i}')
                full=grid_series(annual,lat,lon)
                name=f'{float(full.lat):.2f}° N, {float(full.lon):.2f}° E'
                st.caption(f'Actual nearest 2.5° GPCP cell: {name}')
            summary=comparison_summary(full,name,start,end,bstart,bend,alpha)
            finite=lambda value: f'{value:,.2f}' if np.isfinite(value) else 'Unavailable'
            st.metric(f'{name} · mean annual rainfall',finite(summary['mean'])+' mm')
            p_text=f'{summary["p"]:.4g}' if np.isfinite(summary['p']) else 'Unavailable'
            st.markdown(f'**{finite(summary["decade"])} mm/decade** · raw p = {p_text}')
            st.write(summary['status'])
            st.caption(f'95% slope CI: {finite(summary["low"])} to {finite(summary["high"])} mm/decade · '
                       f'n = {summary["n"]} · relative trend: {finite(summary["relative"])} %/decade · '
                       f'{end} anomaly: {finite(summary["recent_anomaly_mm"])} mm')
            an,z,base=annual_anomalies(full,bstart,bend)
            s=full.sel(year=slice(start,end))
            st.plotly_chart(history_figure(s,summary,baseline=float(base)),width='stretch',theme=None,key=f'comparison_history_{i}')
            selected.append((summary,s,z.sel(year=s.year)))
    if len(selected)!=2:
        return
    normalized=st.toggle('Compare standardized anomalies',key='normalize_compare')
    chart=go.Figure()
    for (summary,series,z),color in zip(selected,[CYAN,AMBER]):
        plotted=z if normalized else series
        chart.add_trace(go.Scatter(x=series.year.values,y=plotted.values,name=summary['selection'],mode='lines+markers',line=dict(color=color,width=2)))
    chart.update_yaxes(title_text='Standardized anomaly (σ)' if normalized else 'Annual precipitation (mm)')
    st.plotly_chart(style(chart,340),width='stretch',theme=None,key='comparison')
    st.write(comparison_interpretation(selected[0][0],selected[1][0]))
    st.caption('Each region has its own mean and sample standard deviation from the same baseline years. Standardized anomalies are not SPI. '
               'Individual classifications use raw exploratory OLS p-values. Boundary masks are approximate; cell selection does not provide city-level observations.')
    summaries=pd.DataFrame([item[0] for item in selected])
    st.download_button('Download regional comparison · CSV',summaries.to_csv(index=False),file_name='saharawatch_comparison.csv',mime='text/csv',key='comparison_export')
