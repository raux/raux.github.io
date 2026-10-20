#!/usr/bin/env bash
# Checks for the rotating post images (layouts/partials/rotating-image.html).
# Builds the site for fixed dates and asserts what ends up in the HTML.
#
#   scripts/test-rotation.sh                 # uses `hugo` on PATH
#   HUGO=$HOME/bin/hugo114 scripts/test-rotation.sh
#
# It briefly edits one post and moves assets/rotate aside; a trap puts both back.
set -u
cd "$(dirname "$0")/.."
HUGO=${HUGO:-hugo}
TMP=$(mktemp -d)
PINPOST=content/posts/publications.md
HOLD=""
fail=0

restore() {
  [ -n "$HOLD" ] && [ -d "$HOLD" ] && mv "$HOLD" assets/rotate
  git checkout -q -- "$PINPOST" 2>/dev/null
  rm -rf "$TMP"
}
trap restore EXIT

ok()  { echo "  ok    $1"; }
bad() { echo "  FAIL  $1"; fail=1; }
check() { if [ "$1" = "$2" ]; then ok "$3"; else bad "$3 (got '$1', want '$2')"; fi; }

build() {  # build <date> <outdir>
  HUGO_ROTATE_DATE=$1 $HUGO -d "$2" >"$TMP/log" 2>&1 || { echo "build failed:"; tail -5 "$TMP/log"; exit 1; }
}
# base name of the banner image on a built page (library_hu_ab12.jpg or library_hu1234_... -> library)
banner() {
  grep -o 'data-src="[^"]*"' "$1" | head -1 | sed 's#.*/##; s#_hu_\{0,1\}[0-9a-f]\{8,\}.*##; s#\..*##; s#"##'
}

POSTS="first-post students projects publications hobbies-and-projects"
D1=2026-10-20; D2=2026-10-21
N=$(ls assets/rotate | grep -ciE '\.(jpe?g|png|webp)$')
echo "pool: $N images, hugo: $($HUGO version | cut -d' ' -f2)"

build $D1 "$TMP/a"; build $D2 "$TMP/b"

echo "posts differ from each other on one day"
vals=""; for p in $POSTS; do vals="$vals $(banner $TMP/a/posts/$p/index.html)"; done
check "$(echo $vals | tr ' ' '\n' | sort -u | wc -l | tr -d ' ')" "$(echo $POSTS | wc -w | tr -d ' ')" "no two posts share a picture ($vals )"

echo "every post changes the next day"
for p in $POSTS; do
  a=$(banner $TMP/a/posts/$p/index.html); b=$(banner $TMP/b/posts/$p/index.html)
  [ "$a" != "$b" ] && ok "$p: $a -> $b" || bad "$p stayed on $a"
done

echo "the rotation cycles after N days"
CYC=$(date -d "$D1 + $N days" +%F 2>/dev/null || date -j -v+${N}d -f %F $D1 +%F)
build "$CYC" "$TMP/c"
for p in $POSTS; do
  check "$(banner $TMP/c/posts/$p/index.html)" "$(banner $TMP/a/posts/$p/index.html)" "$p back to the same picture after $N days"
done

echo "English and Japanese pages agree"
for p in first-post students projects publications; do
  [ -f "$TMP/a/ja/posts/$p/index.html" ] && check "$(banner $TMP/a/ja/posts/$p/index.html)" "$(banner $TMP/a/posts/$p/index.html)" "$p en = ja"
done

echo "home-page cards use the same picture as the post banner"
for p in $POSTS; do
  b=$(banner $TMP/a/posts/$p/index.html)
  grep -q "/rotate/${b}_hu" $TMP/a/index.html && ok "$p card shows $b" || bad "$p card missing $b"
done

echo "banners are resized, not the raw originals"
big=$(find $TMP/a/rotate -type f -size +700k | wc -l | tr -d ' ')
check "$big" "0" "no generated image over 700 KB"

echo "pages outside posts keep their fixed images"
grep -q 'data-src="/images/allPosts.jpg"' $TMP/a/posts/index.html && ok "All Posts banner unchanged" || bad "All Posts banner changed"

echo "pin_image: true keeps the post's own image"
sed -i.bak 's#^image: "/images/library.jpg"#&\npin_image: true#' $PINPOST && rm -f $PINPOST.bak
build $D1 "$TMP/p"
check "$(grep -o 'data-src="[^"]*"' $TMP/p/posts/publications/index.html | head -1)" 'data-src="/images/library.jpg"' "pinned post keeps /images/library.jpg"
git checkout -q -- "$PINPOST"

echo "empty folder falls back to each post's own image"
HOLD="$TMP/rotate-hold"; mv assets/rotate "$HOLD"
build $D1 "$TMP/e"
check "$(grep -o 'data-src="[^"]*"' $TMP/e/posts/students/index.html | head -1)" 'data-src="/images/kipuri.jpg"' "students falls back to /images/kipuri.jpg"
mv "$HOLD" assets/rotate; HOLD=""

echo
[ $fail = 0 ] && echo "all checks passed" || { echo "SOME CHECKS FAILED"; exit 1; }
