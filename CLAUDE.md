# isla-autopost

Automated Instagram posting for @islakerrow (pen name Isla Kerrow, psychological thrillers).
Read `brand/isla.md` before writing any content, and `plan/` for the current month plan.

## How it works
- Each post is a folder `posts/queue/YYYY-MM-DD-slug/` with a `post.json`.
- `scripts/render.py` turns the slides into `01.jpg, 02.jpg …` (1080x1350).
- `.github/workflows/publish.yml` runs hourly and publishes every post whose `publish_at` has passed,
  then moves it to `posts/published/`. Never edit or delete anything in `posts/published/`.
- The repo must stay public: Instagram fetches the images from raw.githubusercontent.com.
- Only content merged into `main` gets published. New weeks always go through a pull request so Shelley approves them first.

## post.json
- `publish_at`: ISO time with offset, Europe/Amsterdam (`+01:00` in winter, `+02:00` in summer).
- `caption`: full caption incl. hashtags. ≤2200 chars, ≤30 hashtags.
- `slides`: types `cover`, `text`, `quote`, `cta`, `book` (cover image + optional kicker/title), `photo`.
  One slide = single-image post; 2–10 slides = carousel.

## Reels (book excerpts with voice-over)
- `post.json` with `"type": "reel"`: `book`, `cover`, `hook`, `excerpt` (lines), `end`, `caption`; `style` is `"page"`.
  Field details are at the top of `scripts/reel.py`.
- The reel is a designed book page (Remotion project in `video/`): cream paper, Cormorant Garamond, the words turn
  to ink as the voice reads them, pages turn, a title page with the hook and an end page with the cover.
  No stock footage, no drawn scenes. Mark the one key sentence with `"key": true` (italic + red wavy underline).
  Check the page frames after rendering: text must stay inside the page, nothing cut off.
- `excerpt` lines must be copied VERBATIM from the book (epubs are in Shelley's Documents › Amazon KDP Books).
  Only use scenes from the first part of a book: no spoilers. Keep a reel under ~75 seconds.
- `.github/workflows/render-reels.yml` makes `reel.mp4` + `thumb.jpg` on the week branch after a push
  (British AI voice via edge-tts with word timing; Remotion renders the page video).
  Watch the result before opening the PR. In the PR, show `thumb.jpg` and link `reel.mp4`.
- Aim for at least one reel a week; it counts as the book spotlight.

## Weekly routine (Sundays)
1. `git pull`. Look at `posts/published/`, `posts/queue/` and `plan/` to avoid repeats and follow the plan.
2. Check the coming week (Mon–Sun) for reading moments (Halloween, Bonfire Night, Black Friday, Christmas reads, Kindle deals).
3. Write 7 posts (one a day) across the pillars, at least two book spotlights (one per live book) and one reel.
   Times: 18:30 weekdays, 10:00 weekends.
4. Branch `week-YYYY-WW`, add folders, `python scripts/render.py --all`, look at every image (text fits, no overlaps), commit, push.
5. PR titled `Week WW: <short theme>` with per post: day/time, caption, and images as
   `![](https://raw.githubusercontent.com/hellovascostudio/isla-autopost/<branch>/posts/queue/<folder>/01.jpg)`.
   End with: "Merge om deze week in te plannen. Wil je iets anders? Reageer hier of in Claude."
6. Never merge it yourself and never publish directly.
