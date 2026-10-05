# CIRP EOI Monitor — free deployment

Daily monitor for public IBBI Form G / CIRP Expression of Interest notices.

## Production architecture ($0)

- GitHub Actions runs the crawler daily at 08:00 IST.
- Durable application state is stored as a text SQL dump in `data/state.sql`.
- Excel and the static dashboard are regenerated on every successful run.
- GitHub Pages hosts the live dashboard.
- No Render service/database and no credit card are required.

## Live URL

`https://raksham97.github.io/cirp-eoi-monitor/`

## Manual refresh

GitHub → repository → Actions → **Daily CIRP EOI Monitor** → **Run workflow**.

## Important

The repository is public because GitHub Pages and standard GitHub-hosted Actions are free for public repositories. The monitor stores only public-source CIRP/IBBI data. Do not add client-confidential material or credentials to this repository.
