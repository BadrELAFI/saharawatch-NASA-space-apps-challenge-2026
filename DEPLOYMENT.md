# Deploy SaharaWatch

The recommended free host is [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud).
The app needs Python 3.12 and no API keys. Its validated rainfall snapshot,
country boundaries and recommended satellite comparison are included in the
repository. A new deployment needs no rainfall download or preparation step.
Custom satellite dates and temperature observations require outbound access
to NASA GIBS and NASA POWER when requested by a user.

## Streamlit Community Cloud

1. Commit and push the complete project to GitHub, including
   `data/raw/precip.mon.mean.nc`, its adjacent JSON provenance, `packages.txt`,
   and all application assets.
2. Sign into [Community Cloud](https://share.streamlit.io/) with GitHub and
   choose **Create app**. Select the repository and branch with the changes.
3. Set the entrypoint to **`app.py`** at the repository root.
4. In **Advanced settings**, select **Python 3.12**. No secrets are required.
5. Deploy. The service installs `requirements.txt` and the system packages in
   `packages.txt`, including Chromium for illustrated report exports.
6. Open the public app and perform the release checks below.

Use the supplied `streamlit.app` subdomain to avoid domain costs. Free hosting
has shared resource limits and hibernates inactive apps; it is suitable for a
portfolio or hackathon demo, with no always-on or high-concurrency guarantee.
See the host's current [limits and sleep behavior](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).

No Docker configuration is needed for Community Cloud. Its supported
[dependency mechanism](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
uses the root requirements and packages files.

## Docker or another container host

```bash
docker build -t saharawatch .
docker run --name saharawatch -p 8501:8501 saharawatch
```

Open http://localhost:8501. The image installs Python dependencies and Chromium,
runs an offline data and real PNG-report preflight during the build, and serves
Streamlit on `0.0.0.0:8501` as a non-root user. Configure the host to route to
container port **8501**, support WebSockets, and probe **`/_stcore/health`**.
TLS belongs at the hosting platform or reverse proxy. Container hosting costs
depend on the provider; this option is not a promise of free hosting.

## Verify a release

From a Python 3.12 environment:

```bash
pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium
python scripts/check_deployment.py --render-report
pytest -q
```

The preflight checks the rainfall SHA-256 and observations, bundled evidence,
and a real PNG chart inside an illustrated report ZIP. GitHub Actions runs the
preflight and Python tests for pushes and pull requests.

After deploying, verify the actual public URL:

- Open the desk in a fresh browser and open a case folder.
- Open the atlas and confirm its rainfall map and source coverage.
- Move the satellite divider and load a custom date pair.
- Pin rainfall evidence, build an illustrated report and open the downloaded
  ZIP. This exercises Chromium, beyond the health probe.
- Verify a quiz and the desk on a phone; sound should start muted.

For browser automation, replace the URL below:

```bash
SAHARAWATCH_TEST_URL=https://YOUR-APP.streamlit.app python scripts/browser_office_smoke.py
SAHARAWATCH_TEST_URL=https://YOUR-APP.streamlit.app python scripts/browser_smoke.py
SAHARAWATCH_TEST_URL=https://YOUR-APP.streamlit.app python scripts/browser_deployment_smoke.py
```

The office and general browser scripts write local screenshots under `assets/`.
The deployment script also downloads and inspects a real illustrated report.
None publish anything. The health endpoint confirms the server responds; it does not
validate data, scientific calculations or report rendering.

## State, updates and troubleshooting

- Quiz attempts, notes, board layouts and saved investigations are
  **session-only**. Download reports before refreshing, closing or rebooting.
- Download caches use local disk and can disappear on host rebuilds or
  restarts. They are an optimization, not permanent evidence storage.
- Refresh rainfall intentionally with `python scripts/prepare_data.py --refresh`.
  Review and commit the NetCDF and provenance JSON together, with updated
  coverage documentation and scientific checks.
- If rainfall is missing, confirm the binary snapshot was committed.
- If report rendering fails, confirm `chromium` installed from `packages.txt`.
  Browser discovery prefers `BROWSER_PATH`, system Chromium/Chrome, then a
  local Playwright installation. Rebuild after changing system packages.
- Custom image or temperature failures can reflect source downtime. The
  bundled comparison and rainfall analysis remain available independently.
- Main data, trend and spatial-mask caches have entry limits. Validate memory
  and responsiveness with your expected audience before a busy event.
- Keep credentials out of Git. `.streamlit/secrets.toml` and `.env` files are
  excluded from Git and the Docker context.

This repository supplies deployment configuration and local verification.
The public-URL checks remain necessary to verify a hosted release.

## Local verification

On 15 November 2026, all 90 Python tests passed. The Docker image installed
dependencies in a clean Python 3.12 environment and passed the data and PNG
report preflight with networking disabled. Its app passed the deployment
browser check while limited to 1 GB RAM and two CPUs: real rainfall map,
notebook pins, illustrated report ZIP download and bundled satellite images.
The container ran as a non-root user and reported healthy. This verifies a
local demo workload, not concurrent audience capacity or a hosted release.
