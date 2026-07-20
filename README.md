# Vodafone DE LCN Channel Numbers

Publishes a small JSON file mapping each channel's `tvg-id` (as used in the app's
bundled m3u) to its official Vodafone Germany channel number (LCN), so the
Android app can fetch it and sort/number channels correctly without needing
to ship or update LCNs inside the app itself.

## How it works

```
data/channels.m3u   <- copy of the app's bundled m3u (keep in sync when it changes)
data/lcn_list.txt   <- official Vodafone LCN list (tab-separated)
scripts/build_channels.py  <- matches the two together
docs/channels.json  <- OUTPUT the Android app fetches
docs/unmatched.json <- channels with no known LCN (for your review, app ignores it)
```

Every time `data/channels.m3u` or `data/lcn_list.txt` changes on `main`, the
GitHub Action in `.github/workflows/build-channels.yml` reruns the script and
commits the updated `docs/channels.json` automatically. It also runs weekly
and can be triggered manually from the **Actions** tab.

## Android app integration

Fetch the raw JSON from:

```
https://raw.githubusercontent.com/<your-username>/<your-repo>/main/docs/channels.json
```

Format:

```json
[
  { "id": "DasErste.de", "name": "Das Erste HD", "lcn": 1, "position": 1 },
  { "id": "SomeChannel.de", "name": "Some Channel", "lcn": null, "position": 124 }
]
```

`lcn: null` means Vodafone doesn't officially number that channel (e.g. it's a
Pluto TV / regional / streaming-only channel not in your cable lineup).

**`position` is the field to sort by.** It equals `lcn` for matched channels,
and for unmatched channels it continues counting up from `(highest LCN + 1)`
in the channel's original m3u order — so sorting ascending by `position`
automatically puts all numbered Vodafone channels first, in the right order,
followed by everything else in a stable order. No null-handling needed on the
app side: fetch once at startup (and cache), build a `Map<tvg-id, Int>` of
`position`, and sort your channel list by it.

## Keeping data/lcn_list.txt accurate

**Important:** Vodafone's LCN numbering is regional and is currently mid-rollout
of a new unified "NorDig LCN" standard (through mid-2026), so the numbers only
apply to *your* network/headend. To update:

1. Go to the Vodafone-Kabel-Helpdesk page for your network (the one you pasted
   from), select your list type (Standard / GigaTV Netbox / etc.).
2. Copy the TV table and paste it into `data/lcn_list.txt`, tab-separated:
   `LCN<TAB>Sender Name<TAB>Resolution<TAB>Übertragung<TAB>Paket`
3. Commit — the Action rebuilds `docs/channels.json` automatically.

## Keeping data/channels.m3u in sync

Whenever you change the m3u bundled in the Android app's assets, copy the same
file here (`data/channels.m3u`) and commit, so new/renamed/removed channels get
picked up.

## Improving match coverage

Currently **49 of 284** channels in the m3u matched to an official LCN — the
rest (Pluto TV channels, regional Bürgerfunk/OK-TV stations, streaming-only
channels, etc.) genuinely aren't part of Vodafone's numbered lineup, so
`lcn: null` is correct for them, not a bug.

If you find a channel that *should* match but didn't (e.g. wording differs
between the m3u and the official list, like "SAT.1 HD" vs "SAT.1
Nordrhein-Westfalen"), add a line to the `MANUAL_MAP` dictionary at the top of
`scripts/build_channels.py`:

```python
"m3u display name, normalized": "official lcn-list sender name, normalized",
```

Check `docs/unmatched.json` after a build for the list of currently-unmatched
channels and their exact names.
