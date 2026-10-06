# Reel Studio Online on your own PC (free, no hosting)

Your Windows PC runs Reel Studio, and **Tailscale Funnel** gives it a fixed, secure `https://` address. Your tablet, phone and Claude reach the PC through that address. Your posts, videos and Instagram token never leave your computer, and there is no monthly cost.

The trade-off: the PC must be **on**, with the **Reel Studio Online** window open, for the tablet and Claude to reach it and for scheduled posts to go out. While that window is open the PC will not go to sleep by itself.

## One-time setup (about 15 minutes)

1. **Install or update Reel Studio**: double-click `Install Reel Studio.bat`. When it asks *Install Tailscale now?*, type `y`. (Already installed? Run it again: it updates and keeps your posts.)
2. **Sign in to Tailscale**: open Tailscale from the Start menu and sign in. A Google account works. It is free for personal use.
3. **Start it**: double-click **Reel Studio Online** on your desktop.
   - The first time, it asks you to choose a **password** (at least 10 characters). You type this on your tablet and when connecting Claude.
   - The first time, Tailscale shows a **link to approve Funnel**. Open it, approve, then return to the black window. This turns on the secure address for this PC.
4. The window shows your address, for example `https://your-pc.tail1234.ts.net`. Open it on your tablet and sign in. Bookmark it or add it to your home screen.
5. In **Settings**, check your timezone, then follow **Use with Claude** and **Instagram** (same steps as in [DEPLOY.md](DEPLOY.md), sections 3 and 4).

## Every day

- Double-click **Reel Studio Online** and leave the window open.
- Use the dashboard and Claude from your tablet or phone as usual.
- To stop, close the window or press Ctrl+C. Your PC is then no longer reachable from the internet.

Run **either** "Reel Studio" (this PC only) **or** "Reel Studio Online" (tablet, phone, Claude), not both. If you try, the second one tells you and stops, so a post can never go out twice.

## Notes

- **Address**: it stays the same across restarts, so Claude's connector and your bookmark keep working.
- **Uploads from the tablet**: clips upload through the same address. Large files take a little longer than on the PC itself.
- **Laptop lid**: closing the lid may still sleep the PC, whatever Reel Studio asks. Keep it open, or change "When I close the lid" in Windows power settings.
- **Turning it off for good**: uninstall Tailscale, or just never start Reel Studio Online. The normal "Reel Studio" shortcut keeps working on the PC alone.
