"""Dashboard controls for Features 3 and 4, operating only on supplied observations."""
import numpy as np
import streamlit as st
import xarray as xr
import plotly.graph_objects as go
from .drought import anomaly_statistics, negative_anomaly_frequency, spi_series
from .plots import departure_figure, style, CYAN, AMBER


@st.cache_data(show_spinner='Fitting calendar-month gamma SPI to measured rainfall…')
def cached_spi(values, times, scale, start, end):
    data=xr.DataArray(values,coords={'time':times},dims='time',attrs={'units':'mm'})
    return spi_series(data,scale,start,end)


def render_drought_panel(annual, monthly, label, start, end, bstart, bend, years):
    st.subheader('Precipitation deficits & drought indicators')
    st.caption(f'{label} · analysis {start}–{end} · anomaly reference {bstart}–{bend}')
    period=st.radio('Anomaly time scale',['Annual','Monthly'],horizontal=True,key='deficit_resolution')
    metric_name=st.selectbox('Departure measure',['Absolute anomaly (mm)','Relative anomaly (%)','Standardized anomaly (σ)'],key='deficit_metric')
    metric=dict(zip(['Absolute anomaly (mm)','Relative anomaly (%)','Standardized anomaly (σ)'],
                    ['anomaly','relative_anomaly','standardized_anomaly']))[metric_name]
    is_monthly=period=='Monthly'
    source=monthly if is_monthly else annual
    departures=anomaly_statistics(source,bstart,bend)
    shown=departures.sel(time=slice(f'{start}-01-01',f'{end}-12-31')) if is_monthly else departures.sel(year=slice(start,end))
    st.plotly_chart(departure_figure(shown,metric,is_monthly),width='stretch',theme=None,key='departure_chart')
    st.caption('Terracotta: below baseline · green: above baseline. Hover for observed rainfall, expected rainfall, and departure. '
               +('Monthly values are compared with the same calendar month.' if is_monthly else 'Annual values use complete-year rainfall totals.'))
    minimum=departures.attrs['relative_minimum_mm']
    st.caption(f'Relative anomaly = 100 × (observed − expected) / expected; withheld below {minimum:g} mm '
               +('per month.' if is_monthly else 'per year.')+' Standardized anomaly = (observed − expected) / baseline sample standard deviation. '
               'At least 10 valid baseline observations per group are required; zero variance yields no standardized result. A standardized anomaly is not SPI.')
    threshold=st.select_slider('Severe negative anomaly threshold (σ)',options=[-2.,-1.5,-1.],value=-1.5,key='deficit_threshold')
    frequency=negative_anomaly_frequency(shown.standardized_anomaly,threshold)
    a,b=st.columns(2)
    a.metric('Frequency of severe negative precipitation anomalies',
             f'{frequency["percent"]:.1f}%' if frequency['valid'] else 'Unavailable')
    b.metric('Observations at or below threshold',f'{frequency["count"]} / {frequency["valid"]}' if frequency['valid'] else 'No valid observations')
    st.caption(f'Counts {period.lower()} standardized anomalies ≤ {threshold:g}σ over {start}–{end}. '
               'Only finite standardized observations enter the denominator. This is not official drought frequency; overlapping SPI months and long-term trends require separate interpretation.')
    frame=shown[['observed','expected','anomaly','relative_anomaly','standardized_anomaly']].to_dataframe().reset_index()
    frame['baseline_start']=bstart;frame['baseline_end']=bend;frame['selection']=label
    st.download_button('Download precipitation departures · CSV',frame.to_csv(index=False),
                       file_name='saharawatch_precipitation_departures.csv',mime='text/csv',key='deficit_export')
    st.divider()
    st.markdown('### Standardized Precipitation Index · SPI-3 / SPI-12')
    st.write('SPI fits a probability distribution to accumulated rainfall separately for each calendar month, '
             'then transforms its cumulative probability to a normal score. It is distinct from the anomaly z-scores above.')
    if not st.checkbox('Enable validated gamma SPI',key='enable_spi'):
        st.caption('Enable for the selected grid cell or country series. SPI uses its own calibration period of at least 30 years; '
                   'the 2001–2020 anomaly baseline is too short for SPI.')
        return
    if years[-1]-years[0]+1<30:
        st.info('SPI is unavailable: the record does not contain 30 complete years.'); return
    default=(1981,2010) if 1981 in years and 2010 in years else (years[0],years[-1])
    cstart,cend=st.slider('SPI calibration period',years[0],years[-1],default,key='spi_calibration')
    scale=st.selectbox('SPI accumulation scale',[3,12],format_func=lambda s:f'SPI-{s}',key='spi_scale')
    if cend-cstart+1<30:
        st.info('SPI is unavailable: choose at least 30 calibration years. Anomaly results remain available above.'); return
    from climate_indices.exceptions import ClimateIndicesError
    try:
        computed=cached_spi(monthly.values,monthly.time.values,scale,cstart,cend)
    except (ValueError,RuntimeError,ArithmeticError,ClimateIndicesError) as exc:
        st.warning(f'SPI is unavailable for this series: {exc}'); return
    valid_months=int(computed.eligible_month.sum())
    if not valid_months:
        st.info('SPI is unavailable: no calendar month has 30 valid accumulated calibration observations, '
                '20 positive accumulations, nonzero variability, and an acceptable gamma-fit diagnostic. No substitute index is shown.'); return
    spi=computed.spi.sel(time=slice(f'{start}-01-01',f'{end}-12-31'))
    if not np.isfinite(spi).any():
        st.info('No valid SPI observations in the selected analysis period.'); return
    if valid_months<12:
        omitted=[str(int(m)) for m in computed.month.values[~computed.eligible_month.values]]
        st.warning('SPI is withheld for unreliable calendar months (1=January): '+', '.join(omitted))
    if computed.attrs['warnings']:
        st.warning('SPI fitting diagnostics: '+computed.attrs['warnings'])
    f=go.Figure(go.Bar(x=spi.time.values,y=spi.values,marker_color=np.where(spi.values<0,AMBER,CYAN),
                       hovertemplate='%{x|%b %Y}<br>SPI-'+str(scale)+': %{y:.2f}<extra></extra>'))
    f.add_hline(y=0,line_color='#8b784f')
    f.add_hline(y=-1.5,line_color=AMBER,line_dash='dash',annotation_text='Severely dry threshold')
    f.update_yaxes(title_text=f'SPI-{scale} (dimensionless)')
    st.plotly_chart(style(f,320),width='stretch',theme=None,key='spi_chart')
    st.caption(f'Calibration {cstart}–{cend}; climate-indices 3.1.0 gamma implementation with calibration-period zero probability '
               '(classic zero handling). Values are clipped by the library to ±3.09. Each calendar month needs ≥30 valid and ≥20 positive '
               'accumulated calibration observations with nonzero variance. Gamma fits flagged by the library KS diagnostic (p < 0.05) are withheld; '
               'this is a conservative fit screen, not a formal goodness-of-fit test with parameter-estimation correction. Accumulations retain antecedent months before the analysis period; '
               'missing rainfall invalidates the entire rolling window. SPI-3 reflects 3-month precipitation conditions; SPI-12 reflects 12-month conditions. '
               'Zero-inflated arid climates can make SPI difficult to interpret. SPI is not a forecast or a complete measure of agricultural/hydrological drought.')
    out=computed[['spi','accumulation_mm']].sel(time=spi.time).to_dataframe().reset_index()
    out=out[['time','spi','accumulation_mm']]
    out['calibration_start']=cstart;out['calibration_end']=cend;out['scale_months']=scale
    st.download_button('Download SPI observations · CSV',out.to_csv(index=False),file_name=f'saharawatch_spi_{scale}.csv',mime='text/csv',key='spi_export')
