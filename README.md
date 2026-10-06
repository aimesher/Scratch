# Reel Studio

A dashboard for planning, assembling and publishing 10-12 second Instagram Reels, Stories and YouTube Shorts. You generate the clips in Google Flow with your own plan. Everything around that is handled here, and nothing is posted until you approve it.

```
Create (master prompt, plan)  ->  Flow (you)  ->  upload clips  ->  auto-assemble  ->  review  ->  approve  ->  post
```

## Online version (tablet and phone, chat with Claude)

Reel Studio can run online at your own private web address, with a Claude connector: you plan, write and schedule posts by chatting with Claude, approved videos post to Instagram through **your own** Meta app, and nothing goes through a third-party service. See **[DEPLOY.md](DEPLOY.md)** for the step-by-step setup.

## Install and start (Windows)

1. Download **Install Reel Studio.bat** (or the whole repository as a ZIP) and double-click it. If Windows warns that it is from an unknown publisher, choose *More info*, then *Run anyway*.
2. It downloads Reel Studio into `C:\Users\<you>\ReelStudio`, installs Python and ffmpeg if they are missing (Windows asks permission), installs the components and puts a **Reel Studio** shortcut on your desktop.
3. From then on, double-click the desktop shortcut. Your browser opens the dashboard. Keep the black window open while you work.

Running the installer again updates Reel Studio and keeps your settings, keys and posts.

## Install and start (Mac and Linux)

Install [Python 3](https://python.org) and ffmpeg (`brew install ffmpeg` on Mac), then double-click **Start Reel Studio.command** (Mac) or run `./start.sh` (Linux).

Your files stay on your computer. The dashboard only listens on `127.0.0.1`, so nobody else on your network can reach it.

## First-time setup (in the dashboard)

1. **Settings**: describe your account. Under Connections, pick who writes your prompts. **Google Gemini** has a free tier: get a key at aistudio.google.com/apikey and paste it. Claude is the paid alternative. **Copy and paste** needs no key at all: the dashboard gives you a request to paste into the Gemini or Claude app, and you paste the answer back. Then Save.
2. **Create**: press *Create my master prompt*. Read it, edit anything, Save.
3. **Create**: choose Reel or Story, how many, an optional theme, press *Generate prompts*.

## Copy-and-paste mode (no API key)

In **Create**, each step shows three boxes: **Copy request**, open Gemini or Claude and paste it into a new chat, then paste the whole answer back and press **Use this answer**. If the answer breaks a rule (for example the shots add up to 16 seconds), the dashboard lists what is wrong and gives you a correction request to paste into the same chat.

## Making a post

1. **Posts**: open a post. Copy each prompt into Flow, shot by shot. For shot 2 onward, start from the last frame of the previous clip.
2. Download the clips from Flow, then drop each into its slot on the post. No renaming. Optional music slot.
3. When every clip is in, the studio joins them to 1080x1920, trims to your maximum length and shows the result.
4. Watch it, edit the caption, optionally pick a time, press **Approve**.
5. **Post it** boxes appear for Instagram and YouTube Shorts: *Download video*, *Copy caption* (or *Copy title* and *Copy description* for YouTube), *Open Instagram* or *Open YouTube Studio*. Post it, then press **I posted it**. When every platform is done the post shows as Published.
6. Stories can only be posted from the Instagram phone app, so send the downloaded file to your phone.

Choose platforms under **Settings > Publishing**. No Meta, Facebook or Google developer account is needed for this.

## Optional: let the dashboard post to Instagram itself

In Settings > Publishing, choose *Instagram API posts it for me*. You need an Instagram Business or Creator account, a Meta developer app with the Instagram API (Instagram Login), your account added as a tester, and a token with content publishing permission. Paste the user ID and token in Settings. Tokens last 60 days. YouTube is always posted by you: Google keeps videos uploaded through its API private until the app passes an audit.

**The publishing calls were written from memory of Meta's docs and have not been run against Instagram.** Test with a throwaway Story first. If it fails, the post is marked *Needs attention* and Meta's own error message is shown.

## Notes

- Stories cannot carry captions or stickers through the API. Add polls and links in the app.
- Text on screen is not burned in. Add it in Instagram's editor so it stays inside the safe zone.
- The command line still works: `python -m igflow --help`.
- Developers: `pip install -r requirements-dev.txt && python -m pytest` (uses real ffmpeg, no network).
