# Rotating post images

Drop pictures in this folder and they join the daily rotation for the top banner and the
cards of every post. No renaming, no front matter, no code.

- **Formats:** `.jpg`, `.jpeg`, `.png`, `.webp`. Landscape works best, at least 1600 px wide.
  Camera originals are fine; Hugo shrinks each one at build time (banner 1600 px, cards 640 px),
  so the live site stays light.
- **How it picks:** the image changes once a day (Japan time), when the site is rebuilt.
  Different posts show different pictures on the same day, and a post's banner and cards always
  agree. Adding or removing a picture reshuffles the order, which is expected.
- **Keep one post's own image:** add `pin_image: true` to that post's front matter. It then
  uses its `image:` and does not rotate.
- **Not covered:** the home page hero, All Posts, Categories, Tags and About keep their fixed
  images from `hugo.toml`.
- **Empty folder:** posts fall back to their own `image:`, then to `defaultPostImg`.

To preview another day locally: `HUGO_ROTATE_DATE=2026-12-25 hugo server`.
