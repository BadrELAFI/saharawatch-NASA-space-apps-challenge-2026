"""Plot real GPCP cells without interpolation or remote map dependencies."""
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import shape, box
from .data import ROOT

CYAN = '#45deca'
AMBER = '#f4af65'
RAIN = [[0, '#1a283b'], [.08, '#263c53'], [.22, '#245e76'], [.45, '#278b9b'], [.7, '#45c9bd'], [1, '#d2f1d7']]
DIVERGING = [[0, '#cf7942'], [.25, '#edb37b'], [.5, '#24364a'], [.75, '#49b9c8'], [1, '#9aeae0']]


def style(fig, height=310):
    fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Arial, sans-serif', color='#a8bdc9', size=12), height=height,
                      margin=dict(l=10, r=15, t=15, b=20),
                      legend=dict(orientation='h', y=1.16, x=0, font_size=11),
                      hoverlabel=dict(bgcolor='#102332', font_size=13))
    fig.update_xaxes(gridcolor='#203341', zeroline=False)
    fig.update_yaxes(gridcolor='#203341', zeroline=False)
    return fig


def cell_geojson(data):
    features, centers = [], []
    for lat in data.lat.values:
        for lon in data.lon.values:
            i = str(len(features))
            x, y = float(lon), float(lat)
            ring = [[x-1.25,y-1.25],[x+1.25,y-1.25],[x+1.25,y+1.25],[x-1.25,y+1.25],[x-1.25,y-1.25]]
            features.append(dict(type='Feature', id=i, properties={}, geometry=dict(type='Polygon', coordinates=[ring])))
            centers.append([y,x])
    return dict(type='FeatureCollection', features=features), np.asarray(centers)


def map_figure(values, title, units, period, pvalues=None, selected=None, feature=None, diverging=False, significance=False):
    values = values.transpose('lat', 'lon')
    geojson, centers = cell_geojson(values)
    z = values.values.ravel()
    finite = z[np.isfinite(z)]
    limit = max(float(np.max(np.abs(finite))), 1e-6) if finite.size else 1.
    lo, hi = (-limit, limit) if diverging else (0, max(float(np.max(finite)), 1.) if finite.size else 1.)
    if significance:
        lo, hi = -1, 1
    p = np.full(z.shape, np.nan) if pvalues is None else pvalues.transpose('lat','lon').values.ravel()
    custom = np.column_stack((centers, p))
    fig = go.Figure(go.Choroplethmap(
        geojson=geojson, locations=[f['id'] for f in geojson['features']], z=z,
        customdata=custom, zmin=lo, zmax=hi, colorscale=DIVERGING if diverging else RAIN,
        marker=dict(opacity=.9, line=dict(width=.35, color='#365469')),
        colorbar=dict(title=dict(text=units, side='right'), thickness=9, len=.75, tickfont_size=10),
        hovertemplate=('<b>%{customdata[0]:.2f}° N, %{customdata[1]:.2f}° E</b><br>'
                       +title+': %{z:.2f} '+units+'<br>'+period+
                       ('<br>Raw OLS p = %{customdata[2]:.4f}' if pvalues is not None else '')+'<extra></extra>'),
        name=title))
    if significance:
        fig.data[0].colorscale = [[0,'#edb37b'],[.2499,'#edb37b'],[.25,'#24364a'],[.7499,'#24364a'],[.75,'#49b9c8'],[1,'#49b9c8']]
        fig.data[0].colorbar.update(tickvals=[-1,0,1],ticktext=['Decrease','Not significant','Increase'])
    # Draw local Natural Earth outlines and labels, so map context works offline.
    path = ROOT / 'data/boundaries/countries.geojson'
    if path.exists():
        outlines = json.loads(path.read_text())['features']
        xs, ys, lx, ly, labels = [], [], [], [], []
        extent = box(-25, 3, 70, 52)
        for country in outlines:
            geom = shape(country['geometry'])
            if not geom.intersects(extent):
                continue
            polygons = [geom] if geom.geom_type == 'Polygon' else geom.geoms
            for polygon in polygons:
                x, y = polygon.exterior.xy
                xs.extend(list(x)+[None]); ys.extend(list(y)+[None])
            point = geom.representative_point()
            if extent.contains(point) and geom.area > 8:
                lx.append(point.x); ly.append(point.y); labels.append(country['properties']['ADMIN'].upper())
        fig.add_trace(go.Scattermap(lon=xs, lat=ys, mode='lines', line=dict(width=1.1,color='#9daeb6'),
                                    hoverinfo='skip', showlegend=False))
        fig.add_trace(go.Scattermap(lon=lx, lat=ly, text=labels, mode='text', textfont=dict(size=10,color='#e0e7eb'),
                                    hoverinfo='skip', showlegend=False))
    if feature is not None:
        fig.add_trace(go.Choroplethmap(geojson=dict(type='FeatureCollection', features=[dict(feature, id='country')]),
                                      locations=['country'], z=[0], colorscale=[[0,'rgba(0,0,0,0)'],[1,'rgba(0,0,0,0)']],
                                      showscale=False, marker_line=dict(width=3,color=CYAN), hoverinfo='skip'))
    if selected is not None:
        lat, lon = selected
        fig.add_trace(go.Scattermap(lat=[lat],lon=[lon],mode='markers', marker=dict(size=13,color='#ffffff'),
                                   name='Selected cell', hovertemplate='Selected grid cell<extra></extra>',showlegend=False))
    fig.update_layout(map=dict(style=dict(version=8, sources={'context':dict(type='geojson',data=dict(type='FeatureCollection',features=[]))}, layers=[dict(id='background',type='background',
                      paint={'background-color':'#0a1826'})]), center=dict(lat=27,lon=22), zoom=2.7),
                      uirevision='mena-map', showlegend=False)
    return style(fig, 480)


def history_figure(series, result, baseline=None, moving=False, monthly=False):
    fig = go.Figure()
    x = series.time.values if monthly else series.year.values
    fig.add_trace(go.Scatter(x=x,y=series.values, name='Monthly total' if monthly else 'Annual rainfall',
                             mode='lines' if monthly else 'lines+markers',line=dict(color=CYAN,width=2),
                             marker=dict(size=5),fill='tozeroy',fillcolor='rgba(69,222,202,.055)',
                             hovertemplate='%{x}: %{y:.1f} mm<extra></extra>'))
    if not monthly and np.isfinite(result['slope']):
        fig.add_trace(go.Scatter(x=x,y=result['intercept']+result['slope']*x,name='Linear trend',
                                 mode='lines',line=dict(color=AMBER,width=2,dash='dash')))
    if moving:
        window = 60 if monthly else 5
        smooth = pd.Series(series.values).rolling(window,min_periods=window,center=True).mean()
        fig.add_trace(go.Scatter(x=x,y=smooth,name='60-month mean' if monthly else '5-year mean',line=dict(color='#c9d9e8',width=2)))
    if baseline is not None and np.isfinite(baseline) and not monthly:
        fig.add_hline(y=float(baseline),line_dash='dot',line_color='#6e8291',annotation_text='Baseline mean',annotation_position='bottom right')
    fig.update_yaxes(title_text='Monthly precipitation (mm)' if monthly else 'Annual precipitation (mm)',rangemode='tozero')
    fig.update_layout(hovermode='x unified')
    return style(fig)


def anomaly_figure(series, standardized=False, observed=None, baseline=None):
    fig = go.Figure(go.Bar(x=series.year.values,y=series.values,marker_color=np.where(series.values<0,AMBER,CYAN),
                          hovertemplate='%{x}: %{y:.2f}<extra></extra>',name='Anomaly'))
    if observed is not None and baseline is not None:
        fig.data[0].customdata = np.column_stack([observed.values, np.full(series.shape,float(baseline))])
        fig.data[0].hovertemplate = '%{x}<br>Observed: %{customdata[0]:.1f} mm<br>Baseline mean: %{customdata[1]:.1f} mm<br>Anomaly: %{y:.2f}' + (' σ' if standardized else ' mm') + '<extra></extra>'
    fig.add_hline(y=0,line_color='#7c929e',line_width=1)
    fig.update_yaxes(title_text='Standardized anomaly (σ)' if standardized else 'Precipitation anomaly (mm)')
    return style(fig,280)
