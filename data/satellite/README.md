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
