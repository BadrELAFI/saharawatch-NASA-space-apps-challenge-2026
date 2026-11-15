# Bundled rainfall snapshot

`precip.mon.mean.nc` is the original GPCP v2.3 monthly precipitation file from
[NOAA PSL](https://psl.noaa.gov/data/gridded/data.gpcp.html), included so a new
deployment can start without a data download. It contains January 1979–October
2026; annual analyses exclude the incomplete final year. The approximately
20 MB file retains upstream observations and metadata. The app selects MENA
and converts rates to monthly totals at runtime.

`precip.mon.mean.json` records source URL, source attributes, coverage and
SHA-256. Its preparation timestamp records local validation, not a satellite
acquisition or a new upstream release. Source interim-status attributes remain
available in the app and reports.

Validate the snapshot offline with `python scripts/check_deployment.py`.
To intentionally download the latest upstream file, validate it, and regenerate
provenance and derived local files, use `python scripts/prepare_data.py --refresh`.
Review and commit the NetCDF and JSON together after a refresh and rerun the
tests. The moving upstream record may have newer coverage than this snapshot.
Other NetCDF files, NASA POWER downloads and satellite caches remain ignored.
