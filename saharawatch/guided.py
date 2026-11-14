"""Live investigations: no preset conclusions or hardcoded climate measurements."""
import numpy as np
import pandas as pd
import xarray as xr
import streamlit as st
import plotly.graph_objects as go
from .analysis import trend, annual_anomalies, fdr_bh
from .comparison import comparison_summary, comparison_interpretation
from .data import country_mask, regional_series
from .plots import history_figure, anomaly_figure, map_figure, style, CYAN, AMBER


def rank_trend_cells(grid, alpha=.05):
    slopes=grid.sel(stat='decade',drop=True).transpose('lat','lon')
    p=grid.sel(stat='p',drop=True).transpose('lat','lon')
    lat,lon=np.meshgrid(slopes.lat.values,slopes.lon.values,indexing='ij')
    frame=pd.DataFrame(dict(latitude=lat.ravel(),longitude=lon.ravel(),trend_mm_decade=slopes.values.ravel(),
                             raw_p=p.values.ravel(),fdr_significant=fdr_bh(p.values,alpha).ravel()))
    frame=frame[np.isfinite(frame.trend_mm_decade)].copy()
    frame['absolute_trend_mm_decade']=frame.trend_mm_decade.abs()
    frame=frame.sort_values(['absolute_trend_mm_decade','latitude','longitude'],ascending=[False,True,True],kind='stable').reset_index(drop=True)
    frame.insert(0,'rank',np.arange(1,len(frame)+1))
    ranks=xr.full_like(slopes,np.nan,dtype=float)
    for row in frame.itertuples():
        ranks.loc[dict(lat=row.latitude,lon=row.longitude)]=row.rank
    return ranks,frame


def render_live_investigation(annual, countries, start, end, bstart, bend, alpha, active_case, trend_values=None):
    st.markdown('### Evidence for the open case')
    st.caption(f'Live analysis {start}–{end} · anomaly baseline {bstart}–{bend}. Change the sidebar years to rerun this investigation.')
    if active_case in ('morocco','compare'):
        if 'Morocco' not in countries:
            st.info('Morocco boundaries are unavailable. Use grid-cell exploration in the atlas.'); return
        full=regional_series(annual,country_mask(annual,countries['Morocco']))
        s=full.sel(year=slice(start,end))
        result=trend(s.year.values,s.values,alpha)
        anomaly,z,base=annual_anomalies(full,bstart,bend)
        if active_case=='morocco':
            number=lambda v: f'{v:.4g}' if np.isfinite(v) else 'Unavailable'
            st.write(f'Morocco: **{result["status"]}**. Estimated trend {number(result["decade"])} mm/decade; '
                     f'raw OLS p = {number(result["p"])}; 95% interval {number(result["low"])} to {number(result["high"])} mm/decade; n = {result["n"]}.')
            st.plotly_chart(history_figure(s,result,baseline=float(base)),width='stretch',theme=None,key='guided_morocco_history')
            st.plotly_chart(anomaly_figure(anomaly.sel(year=s.year),False,s,base),width='stretch',theme=None,key='guided_morocco_anomalies')
            st.caption('Country center-point mask with cosine latitude weighting. OLS inference is exploratory; nonsignificance does not prove no change. A rainfall deficit alone does not establish agricultural or hydrological drought.')
        else:
            options=[name for name in ['Algeria','Tunisia'] if name in countries]
            if not options:
                st.info('Comparison country boundaries are unavailable.'); return
            partner=st.selectbox('Compare Morocco with',options,key='guided_partner')
            other=regional_series(annual,country_mask(annual,countries[partner]))
            normalized=st.toggle('Normalize guided comparison',key='guided_normalize')
            summaries=[]
            figure=go.Figure()
            for name,data,color in [('Morocco',full,CYAN),(partner,other,AMBER)]:
                summary=comparison_summary(data,name,start,end,bstart,bend,alpha)
                summaries.append(summary)
                plotted=annual_anomalies(data,bstart,bend)[1] if normalized else data
                plotted=plotted.sel(year=slice(start,end))
                figure.add_trace(go.Scatter(x=plotted.year.values,y=plotted.values,name=name,mode='lines+markers',line_color=color))
            figure.update_yaxes(title_text='Standardized anomaly (σ)' if normalized else 'Annual precipitation (mm)')
            st.plotly_chart(style(figure,350),width='stretch',theme=None,key='guided_comparison')
            st.dataframe(pd.DataFrame(summaries)[['selection','mean','decade','relative','p','status','recent_anomaly_mm']],hide_index=True,width='stretch')
            st.write(comparison_interpretation(*summaries))
    elif active_case=='anomaly':
        options=list(range(start,end+1))
        st.session_state.setdefault('guided_year',end)
        st.session_state['guided_year']=max(start,min(end,st.session_state['guided_year']))
        year=st.selectbox('Investigate a historical year',options,key='guided_year')
        anomalies,_,baseline=annual_anomalies(annual,bstart,bend)
        st.plotly_chart(map_figure(anomalies.sel(year=year),'Annual precipitation anomaly','mm',
                       f'{year} vs. {bstart}–{bend}',diverging=True,observed=annual.sel(year=year),expected=baseline),
                       width='stretch',theme=None,key='guided_anomaly_map')
        st.caption('Negative values identify precipitation deficits relative to the selected baseline. One dry year does not establish a long-term drying trend. The rectangle includes ocean and areas outside MENA.')
    elif active_case=='trends' and trend_values is not None:
        ranks,frame=rank_trend_cells(trend_values,alpha)
        if frame.empty:
            st.info('No cells have enough valid annual observations to rank trends in this window.'); return
        figure=map_figure(ranks,'Absolute trend rank','Rank',f'{start}–{end}',pvalues=trend_values.sel(stat='p',drop=True))
        figure.data[0].reversescale=True
        st.plotly_chart(figure,width='stretch',theme=None,key='guided_rank_map')
        st.caption('Rank 1 = largest absolute fitted rainfall trend in mm/decade. All finite cells in the rectangle are ranked, including ocean. '
                   'Equal magnitudes are ordered by latitude then longitude. Magnitude ranking is not significance; hover p-values are raw OLS. '
                   'The table separately flags Benjamini–Hochberg FDR significance at the selected α.')
        st.dataframe(frame.head(20),hide_index=True,width='stretch')
        frame['analysis_start']=start;frame['analysis_end']=end;frame['alpha']=alpha
        st.download_button('Download ranked trend cells · CSV',frame.to_csv(index=False),file_name='saharawatch_ranked_trends.csv',mime='text/csv',key='ranked_trends_export')
    else:
        st.info('Open one of the four cases above to see its live observations, charts, and uncertainty here.')
