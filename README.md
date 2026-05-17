# Low Float Catalyst Scanner — Web App

A live dashboard that runs 24/7 online and sends push notifications
to your phone when a low float stock has a high quality catalyst.

## What it looks like

- Live dashboard showing all alerts with Grade A/B/C/D
- Feed status panel showing all 8 news sources
- Settings panel showing your current filters
- Push notifications to your phone via Pushover
- Browser notifications on PC
- Alert sound when new signal fires
- Works on phone browser and PC browser

## Deploy FREE on Railway (recommended — takes 5 minutes)

### Step 1 — Create GitHub account
Go to github.com and sign up free if you don't have one.

### Step 2 — Upload these files to GitHub
1. Go to github.com
2. Click the + button top right
3. Click New repository
4. Name it low-float-scanner
5. Click Create repository
6. Upload all these files:
   - app.py
   - requirements.txt
   - Procfile
   - templates/index.html

### Step 3 — Deploy on Railway
1. Go to railway.app
2. Click Start a New Project
3. Click Deploy from GitHub repo
4. Select your low-float-scanner repo
5. Railway will automatically deploy it
6. Click on your deployment
7. Go to Settings → Domains → Generate Domain
8. You will get a URL like https://low-float-scanner.up.railway.app

### Step 4 — Add your Pushover tokens
1. In Railway click on your project
2. Click Variables
3. Add these two variables:
   PUSHOVER_USER  = your user token from pushover.net
   PUSHOVER_TOKEN = your app token from pushover.net
4. Railway will automatically restart with the new tokens

### Step 5 — Open your app
Visit the URL Railway gave you from any browser on any device.
Bookmark it on your phone home screen for quick access.

## Deploy FREE on Render (alternative)

1. Go to render.com and sign up
2. Click New Web Service
3. Connect your GitHub repo
4. Set:
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
5. Add environment variables PUSHOVER_USER and PUSHOVER_TOKEN
6. Click Deploy

## Environment Variables

| Variable       | What it does                    | Default |
|----------------|---------------------------------|---------|
| PUSHOVER_USER  | Your Pushover user token        | —       |
| PUSHOVER_TOKEN | Your Pushover app token         | —       |
| MIN_SCORE      | Minimum catalyst score 1-10     | 6       |
| MIN_GAP        | Minimum gap % from prior close  | 20.0    |
| MAX_FLOAT      | Maximum float in millions       | 5.0     |
| MIN_PRICE      | Minimum stock price             | 0.50    |
| MAX_PRICE      | Maximum stock price             | 50.0    |
| MIN_VOLUME     | Minimum volume today            | 100000  |
| MIN_RVOL       | Minimum relative volume         | 2.0     |
| SCAN_SECS      | Seconds between scans           | 60      |
| OPEN_HOUR      | Hour to start scanning (ET)     | 4       |
| CLOSE_HOUR     | Hour to stop scanning (ET)      | 20      |

## Cost

Railway free tier gives you $5 credit per month which is enough
to run this app 24/7 for free. No credit card needed to start.
