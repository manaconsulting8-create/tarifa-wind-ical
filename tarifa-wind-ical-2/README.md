# Tarifa Wind iCal

Generate and publish an `.ics` calendar feed with the best wind windows for Tarifa, using Open-Meteo.

The script creates calendar events only when your conditions are met, instead of filling your calendar with every forecast hour.

## What it uses

- Open-Meteo Forecast API for wind speed, gusts, and direction.
- Open-Meteo Marine API for wave height, period, and direction.
- GitHub Actions to regenerate the feed every hour.
- GitHub Pages to host the `.ics` file publicly.
- No API key is required for typical non-commercial use.
- No third-party Python packages are required.

## Repository structure

```text
tarifa-wind-ical/
├── .github/
│   └── workflows/
│       └── update-ical.yml
├── README.md
└── tarifa_wind_ical.py
```

The workflow creates this public file automatically:

```text
https://YOUR-USER.github.io/tarifa-wind-ical/tarifa-wind.ics
```

## Quick setup on GitHub

1. Create a new GitHub repository, for example `tarifa-wind-ical`.
2. Upload these files to the repository.
3. Go to **Settings → Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Go to the **Actions** tab.
6. Open **Update and publish Tarifa wind iCal**.
7. Click **Run workflow**.
8. When it finishes, open the deployment URL shown by GitHub Pages.

Your calendar feed URL will be:

```text
https://YOUR-USER.github.io/tarifa-wind-ical/tarifa-wind.ics
```

Replace `YOUR-USER` with your GitHub username.

## Add it to Google Calendar

1. Open Google Calendar.
2. In the left sidebar, click **Other calendars → + → From URL**.
3. Paste your `.ics` URL:

```text
https://YOUR-USER.github.io/tarifa-wind-ical/tarifa-wind.ics
```

4. Click **Add calendar**.

Google Calendar may cache subscribed calendars, so updates might not appear immediately after every hourly run.

## Add it to Apple Calendar

1. Open Apple Calendar.
2. Go to **File → New Calendar Subscription**.
3. Paste your `.ics` URL.
4. Choose an auto-refresh interval.

## Run locally

```bash
python3 tarifa_wind_ical.py
```

This creates:

```text
tarifa-wind.ics
```

You can open this file directly in Apple Calendar, Outlook, or import it into Google Calendar.

## Customize the criteria

Edit the variables near the top of `tarifa_wind_ical.py`, or override them with environment variables.

Example:

```bash
MIN_WIND_KT=18 GOOD_WIND_KT=22 EXCELLENT_WIND_KT=28 MAX_WAVE_M=1.5 python3 tarifa_wind_ical.py
```

Default settings:

- Spot: Tarifa
- Coordinates: `36.0143, -5.6044`
- Timezone: `Europe/Madrid`
- Accepted wind sectors: `60-130,240-300`
  - roughly Levante and Poniente
- Minimum wind: `16 kt`
- Maximum gusts: `40 kt`
- Maximum wave height: `1.8 m`
- Minimum session block: `2 hours`
- Forecast window: `7 days`

To accept all wind directions:

```bash
WIND_SECTORS=0-360 python3 tarifa_wind_ical.py
```

## Useful environment variables

| Variable | Default | Description |
|---|---:|---|
| `SPOT_NAME` | `Tarifa` | Calendar location/name |
| `LATITUDE` | `36.0143` | Spot latitude |
| `LONGITUDE` | `-5.6044` | Spot longitude |
| `TIMEZONE` | `Europe/Madrid` | Forecast timezone |
| `FORECAST_DAYS` | `7` | Number of forecast days |
| `MIN_WIND_KT` | `16` | Minimum average wind to create an event |
| `GOOD_WIND_KT` | `20` | Threshold for a “Good” label |
| `EXCELLENT_WIND_KT` | `25` | Threshold for an “Excellent” label |
| `MAX_GUST_KT` | `40` | Reject sessions above this gust level |
| `MAX_WAVE_M` | `1.8` | Reject sessions above this wave height |
| `MIN_BLOCK_HOURS` | `2` | Minimum consecutive usable hours |
| `WIND_SECTORS` | `60-130,240-300` | Accepted wind direction sectors in degrees |
| `OUTPUT_FILE` | `tarifa-wind.ics` | Output calendar filename |

## Change the published filename

The workflow currently publishes:

```text
public/tarifa-wind.ics
```

If you change the filename, update both:

```yaml
OUTPUT_FILE=public/tarifa-wind.ics python tarifa_wind_ical.py
```

and the link in `public/index.html` inside `.github/workflows/update-ical.yml`.

## Notes

Open-Meteo forecast data can change from run to run. Calendar apps may also cache subscribed `.ics` feeds, so Google Calendar may not refresh immediately after each hourly update.
