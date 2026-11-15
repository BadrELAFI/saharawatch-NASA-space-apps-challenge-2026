# Licensing and attribution

The [MIT License](LICENSE) applies to SaharaWatch's original application code
and documentation. It does not relicense third-party data, imagery, software,
names or marks. Retain upstream notices when redistributing those materials.

| Material | Source and retained information |
| --- | --- |
| Rainfall observations | GPCP v2.3, distributed by NOAA Physical Sciences Laboratory. The NetCDF retains source attributes and the Adler et al. citation. See [snapshot provenance](data/raw/README.md), its [metadata](data/raw/precip.mon.mean.json), and the [source dataset page](https://psl.noaa.gov/data/gridded/data.gpcp.html). |
| Bundled satellite imagery | NASA EOSDIS GIBS, Aqua and Terra MODIS. Original image responses, credits, acquisition dates and checksums are described in [satellite provenance](data/satellite/README.md) and its [manifest](data/satellite/manifest.json). |
| Country boundaries | Natural Earth 1:110m Admin 0 countries. See [boundary provenance](data/boundaries/README.md) and [Natural Earth's public-domain terms](https://www.naturalearthdata.com/about/terms-of-use/). |
| Optional downloaded observations | NASA GIBS custom comparisons and NASA POWER temperature responses retain source provenance in their caches and exports. They are not original SaharaWatch observations. |
| Python and browser libraries | Dependencies in `requirements.txt` and their transitive dependencies retain their own licenses. Plotly JavaScript bundled by installed Plotly and browser components also retains its upstream license. |

NASA and NOAA names identify data sources. No endorsement of SaharaWatch is
implied. The MIT license does not grant rights to third-party names or marks.
