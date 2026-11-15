# Casablanca satellite evidence

Two unmodified NASA GIBS WMS JPEG responses are bundled for offline comparison. Dates and platforms follow the pair discussed in [NASA Earth Observatory’s February 2024 article](https://science.nasa.gov/earth/earth-observatory/drought-parches-morocco-152467/). These are new, identical-extent GIBS requests, rather than copies of the article’s annotated images.

| Acquisition date | Platform / instrument | GIBS visualization |
| --- | --- | --- |
| 2023-02-12 | Aqua / MODIS | `MODIS_Aqua_CorrectedReflectance_TrueColor` |
| 2024-02-19 | Terra / MODIS | `MODIS_Terra_CorrectedReflectance_TrueColor` |

Both requests use WMS 1.1.1, EPSG:4326, longitude/latitude bounds `[-9, 31, -6, 34]`, and a 900 × 900 output image. See [NASA’s WMS examples](https://nasa-gibs.github.io/gibs-api-docs/python-usage/). Exact request URLs, SHA-256 checksums, retrieval time, acquisition dates, platform names, alignment, visual-review notes, and scientific limits are recorded in [manifest.json](manifest.json). App loading checks each image against its recorded checksum and never requests replacement imagery on interaction.

Credit: NASA EOSDIS Global Imagery Browse Services (GIBS), Aqua and Terra MODIS. The NASA article supplies context; it does not validate SaharaWatch’s separate GPCP calculations. No NASA endorsement is implied.

The coastline and terrain align visually. The earlier image contains visible haze and clouds, and both views include snow. There is no quantitative cloud mask or image-difference classification. Same-season acquisition limits seasonal differences but cannot eliminate them, and the two platforms have different overpass conditions. True-color browse pixels do not measure vegetation health, reservoir volume, or rainfall. Do not infer causation from an image pair.

The optional GPCP overlay shows actual 2.5° cell edges, projected into the image extent. The rainfall panel uses the nearest GPCP cell to Casablanca, not a city-level estimate or a national average. Its six-month totals exclude the image-acquisition month; monthly bars include the full calendar month even when the satellite image was taken earlier in that month.

## User-selected comparisons

The bundled pair remains the recommended example. The separate **Satellite images** workspace also accepts two years, a common month/day and one MODIS platform for both acquisitions. It checks the selected platform's actual GIBS time-domain intervals and requests exact dates; it never silently selects an adjacent date. Custom imagery uses transparent PNG responses over the same extent and dimensions as the example.

Original responses and per-image provenance are cached under ignored `data/raw/satellite/`. Checksums validate cache reuse; missing or unreadable dates retain the currently displayed pair. The last successfully fetched availability catalogue can support cached use when the service is unreachable, with a stale-catalogue notice. Cached image area measures nontransparent pixels, not cloud-free coverage. Custom pairs are not manually reviewed for clouds or registration artifacts.

The loaded pair's manifest and originals are included in the satellite evidence ZIP. Case 006 independent-investigation pins use the current pair and its rainfall dates; the guided quiz remains tied to the explicitly labeled, reviewed training example.
