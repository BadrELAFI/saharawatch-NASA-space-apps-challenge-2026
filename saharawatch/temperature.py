"""On-demand NASA POWER/MERRA-2 point-temperature data, with retained provenance."""
from pathlib import Path
import hashlib
import json
import datetime
import numpy as np
import pandas as pd
import requests
import streamlit as st
import xarray as xr
import plotly.graph_objects as go
from .data import ROOT
from .inference import analyze_trend
from .plots import style, CYAN, AMBER

POWER_URL='https://power.larc.nasa.gov/api/temporal/monthly/point'


def parse_power(payload):
    if payload.get('parameters',{}).get('T2M',{}).get('units')!='C':
        raise ValueError('NASA POWER T2M units must be explicitly Celsius (C).')
    if 'MERRA2' not in payload.get('header',{}).get('sources',[]):
        raise ValueError('Expected MERRA2 temperature provenance was not supplied.')
    values=payload.get('properties',{}).get('parameter',{}).get('T2M',{})
    records={pd.Timestamp(f'{k[:4]}-{k[4:6]}-01'):float(v) for k,v in values.items()
             if len(k)==6 and k.isdigit() and 1<=int(k[4:])<=12}
    if not records:raise ValueError('NASA POWER did not return monthly T2M observations.')
    dates=sorted(records)
    data=xr.DataArray([records[t] for t in dates],coords={'time':dates},dims='time')
    fill=float(payload['header'].get('fill_value',-999))
    data=data.where(np.isfinite(data)&(data!=fill))
    data=data.reindex(time=pd.date_range(dates[0],dates[-1],freq='MS'))
    data.attrs.update(units='°C',source='NASA POWER / MERRA-2',resolution='Native MERRA-2 meteorological grid; point API selection')
    return data


def annual_temperature(monthly):
    days=monthly.time.dt.days_in_month
    weighted=(monthly*days).groupby('time.year').sum('time',skipna=True)
    duration=days.groupby('time.year').sum('time')
    result=(weighted/duration).where(monthly.groupby('time.year').count('time')==12)
    return result.assign_attrs(units='°C',aggregation='Day-weighted annual mean of 12 monthly means')


def fetch_temperature(lat,lon,start=1981,end=2024):
    if not 10<=lat<=43 or not -18<=lon<=63 or start<1981 or end<start:
        raise ValueError('Invalid NASA POWER point or year range.')
    lat,lon=round(float(lat),2),round(float(lon),2)
    directory=ROOT/'data/raw/power';directory.mkdir(parents=True,exist_ok=True)
    path=directory/f'{lat:.2f}_{lon:.2f}_{start}_{end}.json'
    params=dict(parameters='T2M',community='AG',latitude=lat,longitude=lon,start=start,end=end,format='JSON')
    if path.exists():
        payload=json.loads(path.read_text())
    else:
        response=requests.get(POWER_URL,params=params,timeout=(20,90));response.raise_for_status()
        payload=response.json();parse_power(payload)
        path.write_text(json.dumps(payload))
    monthly=parse_power(payload)
    provenance=dict(url=requests.Request('GET',POWER_URL,params=params).prepare().url,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),latitude=lat,longitude=lon,
        header=payload['header'],parameter=payload['parameters']['T2M'],messages=payload.get('messages',[]))
    sidecar=path.with_suffix('.provenance.json')
    if sidecar.exists():provenance=json.loads(sidecar.read_text())
    else:
        provenance['recorded_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        sidecar.write_text(json.dumps(provenance,indent=2))
    return monthly,annual_temperature(monthly),provenance


def render_temperature(lat,lon,start,end,bstart,bend,alpha,method,precip_monthly):
    st.subheader('Temperature at 2 m · NASA POWER / MERRA-2')
    st.caption('Point analysis at a requested coordinate, not a national average. MERRA-2 is a model-based reanalysis; its native spatial support differs from the 2.5° GPCP cell.')
    a,b=st.columns(2)
    latitude=a.number_input('Temperature latitude (° N)',10.,43.,float(lat),step=.25,key='temperature_lat')
    longitude=b.number_input('Temperature longitude (° E)',-18.,63.,float(lon),step=.25,key='temperature_lon')
    key=f'{latitude:.2f}_{longitude:.2f}_{max(1981,min(start,bstart))}_{max(end,bend)}'
    st.caption('Load makes one NASA POWER request for this point and caches the raw JSON on disk. No temperature requests run at dashboard startup. Coordinates are queried to 0.01°, which does not increase native resolution. Annual temperature is averaged, never summed.')
    if st.button('Load real temperature observations',key='load_temperature'):
        st.session_state['temperature_request']=key
    if st.session_state.get('temperature_request')!=key:
        st.info('Choose a point and load the source-provided reanalysis series to begin.');return
    try:
        with st.spinner('Loading NASA POWER temperature…'):
            monthly,annual,provenance=fetch_temperature(latitude,longitude,max(1981,min(start,bstart)),max(end,bend))
    except (requests.RequestException,ValueError,OSError,KeyError) as exc:
        st.error(f'Temperature data could not be loaded: {exc}');return
    st.caption(f'Loaded POWER record: {str(monthly.time.values[0])[:10]} to {str(monthly.time.values[-1])[:10]}; requested point {provenance["latitude"]:.2f}° N, {provenance["longitude"]:.2f}° E.')
    for message in provenance.get('messages',[]):st.warning(str(message))
    selected=annual.sel(year=slice(start,end));valid=selected.dropna('year')
    if not valid.size:st.info('No complete annual temperature observations in this period.');return
    if start<1981:st.warning('NASA POWER meteorological coverage starts in 1981; earlier years are not substituted.')
    result=analyze_trend(selected.year.values,selected.values,alpha,method)
    r=lambda x:f'{x:.3g}' if np.isfinite(x) else 'Unavailable'
    st.write(f'{method}: **{result["status"]}** · trend {r(result["decade"])} °C/decade · p = {r(result["p"])} · n = {result["n"]}.')
    f=go.Figure(go.Scatter(x=selected.year.values,y=selected.values,name='Temperature',mode='lines+markers',line_color=CYAN))
    if np.isfinite(result['slope']):
        f.add_trace(go.Scatter(x=selected.year.values,y=result['intercept']+result['slope']*selected.year.values,name='Trend',line=dict(color=AMBER,dash='dash')))
    f.update_yaxes(title_text='Day-weighted annual mean temperature (°C)')
    st.plotly_chart(style(f,330),width='stretch',theme=None,key='temperature_history')
    baseline=annual.sel(year=slice(bstart,bend))
    if bstart<1981:
        st.warning('The requested temperature baseline starts before NASA POWER coverage. No alternative baseline is substituted.')
    if bstart>=1981 and int(baseline.count())>=10:
        anomaly=selected-baseline.mean()
        f=go.Figure(go.Bar(x=selected.year.values,y=anomaly.values,marker_color=np.where(anomaly.values>0,AMBER,CYAN)))
        f.update_yaxes(title_text='Temperature anomaly (°C)')
        st.plotly_chart(style(f,260),width='stretch',theme=None,key='temperature_anomaly')
        st.caption(f'Temperature departures from {bstart}–{bend}; uses only available complete years (n={int(baseline.count())}).')
    else:st.info('At least ten complete baseline years are required for temperature anomalies.')
    from .data import grid_series
    rainfall=grid_series(precip_monthly,latitude,longitude)
    rain_annual=(rainfall.groupby('time.year').sum('time')).where(rainfall.groupby('time.year').count('time')==12)
    aligned=xr.merge([annual.rename('temperature_c'),rain_annual.rename('precipitation_mm')],join='inner')
    frame=aligned.sel(year=slice(start,end)).to_dataframe().reset_index()
    st.caption(f'Temporal alignment: annual temperature and nearest GPCP cell ({float(rainfall.lat):.2f}° N, {float(rainfall.lon):.2f}° E). Their spatial supports differ; no causal relationship is inferred.')
    st.dataframe(frame,hide_index=True,width='stretch')
    st.download_button('Download aligned temperature and rainfall · CSV',frame.to_csv(index=False),file_name='saharawatch_temperature_rainfall.csv',mime='text/csv')
    st.download_button('Download temperature provenance · JSON',json.dumps(provenance,indent=2),file_name='temperature_provenance.json',mime='application/json')
    st.json(provenance)
