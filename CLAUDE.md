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

## Weekly routine (Sundays)
1. `git pull`. Look at `posts/published/`, `posts/queue/` and `plan/` to avoid repeats and follow the plan.
2. Check the coming week (Mon–Sun) for reading moments (Halloween, Bonfire Night, Black Friday, Christmas reads, Kindle deals).
3. Write 4 posts across the pillars, at least one book spotlight. Times: 18:30 weekdays, 10:00 weekends.
4. Branch `week-YYYY-WW`, add folders, `python scripts/render.py --all`, look at every image (text fits, no overlaps), commit, push.
5. PR titled `Week WW: <short theme>` with per post: day/time, caption, and images as
   `![](https://raw.githubusercontent.com/hellovascostudio/isla-autopost/<branch>/posts/queue/<folder>/01.jpg)`.
   End with: "Merge om deze week in te plannen. Wil je iets anders? Reageer hier of in Claude."
6. Never merge it yourself and never publish directly.
