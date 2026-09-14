# Student portraits

Files here fill the ticker on [/posts/students/](https://raux.github.io/posts/students/).
A person with no file gets a monogram of their initials instead, so the row is
never broken — it just gets better as photographs arrive.

## Adding one

1. Save the image here as a short lowercase name, e.g. `tao-xiao.jpg`.
2. Put that filename in `data/students.yaml` under that person's `photo:`.
3. `hugo server` to check, then commit.

Square, 400×400 or larger. The ticker crops to a circle at 76px, so anything
much bigger is wasted bytes — `sips -Z 400 photo.jpg` (macOS) or
`convert photo.jpg -resize 400x400^ -gravity center -extent 400x400 out.jpg`
will do it.

## Where the photos should come from

Ask each person for one they are happy with. Their staff photo belongs to the
university that took it, their conference profile photo usually to the
photographer, and either way a former student generally wants a say in which
picture of them sits on their supervisor's site. Emailing fifteen alumni to ask
for a headshot is also a good excuse to hear what they are doing now — which is
the other column this file feeds.

Your own photographs — lab group shots, graduation days, conference dinners —
are yours to crop and use, and usually make a warmer row than a wall of staff
portraits.
