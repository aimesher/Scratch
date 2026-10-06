# Put Reel Studio online (works from a tablet)

This gives you your own private Reel Studio at a web address, plus a Claude connector, so you can plan and schedule posts by chatting with Claude on any device. It runs on your account at a hosting company. Nobody else holds your Instagram login.

These steps use **Railway** (railway.com), which works fully in a browser. Its Hobby plan has been about $5 a month; check the current price when you sign up. Any host that runs a Dockerfile with a persistent disk works the same way.

## 1. Create the server (about 10 minutes)

1. Go to **railway.com** and sign in with your GitHub account (`aimesher`).
2. **New Project**, then **Deploy from GitHub repo**, then choose **aimesher/Scratch**.
3. Open the new service, then **Settings**, then **Source**. Set the branch to `claude/instagram-agentic-google-flow-9pjpec` (change it to `main` once the code is merged there).
4. **Add a volume** (right-click the service, or the + menu, then Volume). Mount path: `/data`. This is where your posts, videos and settings live. Without it, everything is lost on every update.
5. **Variables**: add `DASHBOARD_PASSWORD` with a long password only you know (at least 10 characters; a short sentence is good).
6. **Settings**, then **Networking**, then **Generate Domain**. You get an address like `https://reelstudio-production.up.railway.app`. Railway passes it to the app automatically.
7. Wait for the deploy to turn green, open the address and sign in with your password.

## 2. Fill in Settings

Describe your account, check the timezone, and save.

## 3. Connect Claude (2 minutes)

In **Settings > Use with Claude**, copy the connector URL. Then on claude.ai: **Settings > Connectors > Add custom connector**, paste it, **Add**, **Connect**. A Reel Studio page opens: type your password and press **Allow**. It now works in the Claude app on your tablet and phone too. Custom connectors need a paid Claude plan.

Try: *"Look at my account and plan three reels for this week."*

## 4. Connect Instagram (about 30 minutes, once)

Follow **Settings > Instagram > First time? Set up your Meta app**. In short: a Business or Creator Instagram account, a free Meta developer account with your email (no Facebook needed), an app with *API setup with Instagram login*, the App ID and Secret pasted into Settings, the Redirect URL pasted into the Meta app. Then press **Connect Instagram**.

After that, approved posts go out to Instagram by themselves and the token renews itself. YouTube Shorts stay a one-minute manual step in the dashboard.

## Day to day

- Ask Claude for ideas; it saves the posts with their Flow prompts.
- Generate the clips in Google Flow, then upload them into each post's slots in the dashboard (works from the tablet's Files app).
- Watch the finished video, then tell Claude (or press Approve) with a time.

## Notes

- **First real post**: the Instagram publishing calls follow Meta's documentation but have not been run against a live account yet. Start with a Story. If it fails, the post shows *Needs attention* with Meta's exact message.
- **Updates**: Railway redeploys when the branch changes. Your data on the volume stays.
- **Lost password**: change `DASHBOARD_PASSWORD` in Railway's Variables; the service restarts with the new one.
- **Disconnect Claude** any time from Settings; it signs out every connected app.
