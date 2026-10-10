# Vox: build in public plan (v2)

Goals, in order: **visibility, developer credibility, promoting Vox.**
Research basis: X ranking code (`xai-org/x-algorithm`, param sync 2026-10-02), LinkedIn ranking write-ups (Hootsuite 2026-07, Digital Codex 2026-04), ~1,100 X posts, four small-account breakouts studied by timeline, and r/buildinpublic, r/SideProject, r/SaaS, r/indiehackers (Oct 2026). Samples are small and noisy; follower counts are as of today, not historical.

## Vox in one line
You call a real phone number. It creates tasks, moves the calendar, and calls you back. **Phone interface + follow-through after the call ends.**
Brand rule (`vox-web/PRODUCT.md`): no invented numbers, testimonials or benchmarks. Every claim must be shown in a demo or measured.

## Decision: hero demo first, building blocks as episodes
Original idea: show small blocks (voice pipeline, game tracking, Swiggy), reveal the product last. Changed because:
- Closest comparable (@yashaswini_s_s, 894 followers): a complete WhatsApp voice assistant demo with a human hook got 2.5k likes / 312k views. Her technical deep-dive five days later got 97 likes / 11k views (about 3.5% of that reach).
- Building blocks reach builders, not users, and are hard to send to a friend. Reply/share/copy-link signals are what X rewards.
- A cold account gets a short new-author window; spend it on something shareable.
- Views did not become followers for two of four breakouts (980 and 894 followers after 1.9M and 312k views). Followers came from daily cadence and a profile worth following.
New order: **hero demo -> blocks as follow-up episodes -> daily ships and replies -> full product launch moment.**

## Claims to verify before posting anything
- **Swiggy:** connector is read-only (orders, tracking), not live-verified, callback needs Swiggy allowlisting, and Swiggy does not issue refresh tokens (login can lapse). Only post it if a real account link works on camera. Say "tracks", never "orders".
- **PlayStation hours:** derived from lifetime-counter increases with unknown session times. Say "estimated this week", never exact sessions.
- **Callback / outbound calls:** confirm working live before claiming.
- **Latency numbers:** measure first (p50/p95, first-audio time). Only post numbers you logged.
- **Voice biometrics:** state it plainly; show only your own or consented calls.

## What the small accounts did
| Account | Followers | What worked | Lesson |
|---|---|---|---|
| @yashaswini_s_s | 894 | Personal hook ("for my dadi") + end-to-end video + safety detail up front + tagged tool makers | Story + working demo beats architecture. Hit did not convert to followers (mostly retweets elsewhere). |
| @Rubzem | 980 | Playable link, "reply with what I should add next", sequels (Part 2), platform tags | Sequels and reply-bait CTAs multiply reach; still needs a profile that earns the follow. |
| @xevrion_the1 | 1.9k | 5-10 small ships/day, "someone asked, shipped same day", number recaps ("8 stars to 1,190"), open source, link in separate reply | Slow but real growth; typical 20-100 likes, ~1 in 10 posts breaks out. |
| @rossaxbt | 157 | One post/day at the same time, self-repost 12h later, free template giveaway on a hot topic | Cadence and a free artifact work. Don't copy the repackaged-clip content. |
Data posts also work for voice: a number-led post ("2,029 real phone calls") got 2.1k likes / 371k views, from a 23k-follower account.

## Algorithm: what matters

### X (from ranking code)
Score = sum of (weight x predicted probability of each action).
- Positive: **copy-link share 20**, reply 5, quote 5, share-via-DM 5, follow author 4, share 2, repost 1, like 0.5, link open 0.2, dwell 0.05.
- Reply from a mutual follow gets an extra +15 boost.
- Negative: not interested -47.5, block -31.2, mute -58.8, report -234. No spam hooks.
- Posts older than 48h are dropped; ranking is front-loaded. New authors (low impressions) get a lift for posts under about 2 hours old.
- Out-of-network posts are discounted; reach to strangers comes from replies, DM shares and link copies.
- Author diversity decay: a second post soon after the first is discounted. Space posts out.
- No explicit link penalty found in the weights. "Link in reply" is folklore; test it.
Implication: write things people reply to, send to a friend, or copy the link for.

### LinkedIn (secondary sources)
- Three gates: quality filter, test audience in first 60-120 minutes, then wider ranking.
- Saves (~5x a like) and comments (~2x) beat likes; dwell time counts.
- Reported penalties: links in body, engagement bait, 6+ hashtags, two posts within ~12 hours.
- Best slots: Tue/Wed morning. Use LinkedIn for milestones only.

### Reddit
- Bare promotion gets about 1 upvote. Lead with a specific number, a story and a visual.
- Top examples: "900 downloads in 2 weeks" (416), "free version of an expensive app" (200), "makes $0, costs $181/month" (96), fog-of-war map demo (2.8k).
- Comment 5-10 times on your own post; read each sub's rules; disclose you built it.

## Content system
**Hero (week 1):** one 30-60s real call, split screen with tasks/timeline updating and the callback. Human hook, safety detail (confirms before acting), stack named.
**Episodes (one every 2-3 days), each = outcome demo post + engineering detail in a reply/thread + optional write-up for credibility:**
1. Phone call that checks my PlayStation week (estimated), spoken answer on a real call.
2. Voice pipeline: measured latency before/after, with the one change that mattered.
3. Swiggy order tracking, only if live-verified.
4. Calendar follow-through: deadline hits, Vox calls back.
5. Speaker recognition: two voices, separate context.
6. Drive the desktop app from a phone call (desktop control).
7. Share-to-action side project.
**Daily:** one small ship update (screenshot or 10s clip) and 10-20 substantive replies on a list of 25 accounts (5k-50k followers) in voice AI, agents, indie dev.
**Quote-post step (2-3 per week):** quote a post or article from a larger account in voice AI, agents or latency, and add your own working demo or measured number (not a hot take). X weights quotes at 5.0 and shows the post to the quoted account's audience. Rules: only quote work you've tried; lead with your result; never tag-spam; skip income-hype or unverifiable posts. Source: the `@ultimaxbt` / `@0xwhrrari` pattern, minus the anonymous persona and inflated claims.
**Credibility assets:** measured latency write-up, architecture diagram from the repo, "what broke this week" posts, Apache-2.0 self-hosting repo (`vox-deploy`), request-to-ship loop (ship what someone asked for, same day, quote them).
**Promotion:** pinned hero post, bio line "Building Vox: call it, it follows through" with site link, waitlist or "call it" CTA once real. Link in a separate reply or bio; test whether it changes reach. Tag only tools you actually use.

## 4-week itinerary
**Week 0 (2-3 days):** record hero + episode 1-2 clips; verify claims above; measure latency; set bio/pin; build the 25-account list; note baseline followers.
**Week 1:** Day 1 hero post, answer every reply for 3 hours. Days 2-7: one ship/day + replies. Episode 1 (day 3), episode 2 (day 6). LinkedIn post 1 (why a phone call, not an app) day 3. r/SideProject visual post day 6.
**Week 2:** "how it works" thread (call -> task -> calendar -> callback). Episode 4 and 5. LinkedIn milestone with real usage. r/buildinpublic numbers-and-story post.
**Week 3:** open-source/self-hosting post, latency write-up (Dev credibility). Episode 6. Invite 10 specific people to call it; post what they asked, with permission. LinkedIn: why open source.
**Week 4:** keep the top 2 formats, drop the bottom 2. "28 days of building Vox" X thread + LinkedIn carousel. Product launch post with full demo.

## Draft posts

**Hero (X)**
```
I built an assistant you call on a real phone number.

You talk for two minutes between meetings. Hang up.

It keeps working: makes the tasks, moves the calendar, and calls you back when a deadline hits.

No app. Just a call.

Building it in public. Demo below.
```
Native video, no link in post. Reply to yourself with "what's next". Do not claim anything the demo doesn't show.

**Episode 1 (X), PlayStation**
```
I asked my phone how much PS5 I played this week.

It called back with the answer. (Estimated from my account's lifetime counters, so no exact sessions.)

Next: how fast it picks up. Thread below.
```

**Episode 2 (X), latency**
```
My voice assistant used to take [measured]s to answer a call.
Now it takes [measured]s.

One change did most of it: [real change].

Numbers from [N] real calls. Thread:
```
Fill brackets only with logged values.

**LinkedIn hero**
```
I stopped trusting apps to manage my day.

Most of my decisions happen between meetings, in a car, or walking. Typing is the wrong interface.

So I'm building Vox: you call a real phone number. You talk. When you hang up, it creates the tasks, moves the calendar, and calls you back when something needs attention.

It's early. I'll share what ships and what breaks, every week.

What's the one thing you wish you could do by voice during your day?
```
One screenshot, no link in body, Tue/Wed morning.

## Metrics (weekly)
- X: replies per 1k views, profile clicks, shares/DMs if visible, followers from replies vs posts.
- LinkedIn: saves, comments in first 2 hours.
- Reddit: upvote ratio, comments, DMs.
- Product: calls placed, signups, % who call twice. Post only real numbers.
- Review rule: after 2 weeks, cut any format below the median on replies per 1k views.

## Risks
- Overclaiming breaks the brand rule and credibility. Cut anything not demonstrated.
- Viral without conversion: a profile with a pinned hero, clear bio and recent daily posts is the conversion layer.
- Reddit bans for promotion; read rules, lead with value, disclose.
- Privacy: show only your own or consented calls; say voice biometrics are used.
