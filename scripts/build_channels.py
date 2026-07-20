#!/usr/bin/env python3
"""
Builds docs/channels.json for the Android app.

Reads:
  - data/channels.m3u   -> list of channels (tvg-id + display name) as bundled in the app
  - data/lcn_list.txt    -> official Vodafone LCN list, tab-separated:
                             <LCN>\t<Sender Name>\t<Resolution>\t<Uebertragung>\t<Paket>

Writes:
  - docs/channels.json   -> [{ "id": tvg-id, "name": display name, "lcn": int|null }, ...]
  - docs/unmatched.json  -> channels from the m3u that got no LCN (for review only,
                             not needed by the app)

To add more LCN matches over time:
  1. Edit data/lcn_list.txt if Vodafone's official numbering changes (paste the
     updated list from the Vodafone-Kabel-Helpdesk page for your network).
  2. Add/adjust entries in MANUAL_MAP below for channels whose name differs
     between the m3u and the official list (e.g. "SAT.1 HD" vs "SAT.1 Nordrhein-Westfalen").
  3. Commit -> the GitHub Action rebuilds docs/channels.json automatically.
"""
import re
import json
import unicodedata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M3U_PATH = ROOT / "data" / "channels.m3u"
LCN_PATH = ROOT / "data" / "lcn_list.txt"
OUT_CHANNELS = ROOT / "docs" / "channels.json"
OUT_UNMATCHED = ROOT / "docs" / "unmatched.json"

# m3u display name (normalized) -> official LCN-list sender name (normalized).
# Only add an entry here when the wording genuinely differs between the two
# sources. If the normalized names already match exactly, no entry is needed.
MANUAL_MAP = {
    "das erste": "das erste",
    "zdf": "zdf",
    "prosieben": "prosieben",
    "rtl": "rtl nordrhein westfalen",
    "rtlzwei": "rtlzwei",
    "sat 1": "sat 1 nordrhein westfalen",
    "kabel eins": "kabel eins",
    "super rtl": "super rtl",
    "zdfneo": "zdf neo",
    "sixx": "sixx",
    "zdfinfo": "zdfinfo",
    "wdr fernsehen": "wdr fernsehen koln",
    "wdr fernsehen duisburg": "wdr fernsehen duisburg",
    "wdr fernsehen dusseldorf": "wdr fernsehen dusseldorf",
    "wdr fernsehen wuppertal": "wdr fernsehen wuppertal",
    "kika": "kika",
    "arte": "arte",
    "ndr niedersachsen": "ndr fernsehen niedersachsen",
    "mdr fernsehen sachsen": "mdr fernsehen sachsen",
    "3sat": "3sat",
    "phoenix": "phoenix",
    "br fernsehen sud": "br fernsehen sud",
    "rbb berlin": "rbb fernsehen berlin",
    "deluxe music": "deluxe music",
    "hr fernsehen": "hr fernsehen",
    "n24 doku": "n24 doku",
    "tagesschau 24": "tagesschau24",
    "ard alpha": "ard alpha",
    "sr fernsehen": "sr fernsehen",
    "hse": "hse",
    "sonnenklar tv": "sonnenklar tv",
    "handystar": "handystar",
    "bibel tv": "bibel tv",
    "ric": "ric",
    "dokusat": "dokusat",
    "hse24 extra": "hse extra",
    "juwelo": "juwelo tv",
    "qvc germany": "qvc",
    "qvc 2 germany": "qvc zwei",
    "qvc style germany": "qvc style",
    "dmf": "dmf",
}


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\[.*?\]", "", s)   # strip [Not 24/7] etc.
    s = re.sub(r"\(.*?\)", "", s)   # strip parenthetical notes
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace(".", " ").replace("_", " ").replace("-", " ").replace("+", " plus ")
    s = re.sub(r"\bhd\b", "", s)
    s = re.sub(r"\bsd\b", "", s)
    s = re.sub(r"\buhd\b", "", s)
    s = re.sub(r"\bld\b", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_m3u(path: Path):
    channels = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF"):
            m = re.search(r'tvg-id="([^"]*)"', line)
            tvg_id = m.group(1) if m else ""
            name = line.rsplit(",", 1)[-1].strip()
            channels.append({"id": tvg_id, "name": name})
    return channels


def parse_lcn_list(path: Path):
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            lcn = int(parts[0])
        except ValueError:
            continue
        sender = parts[1]
        entries.append({"lcn": lcn, "sender": sender, "norm": norm(sender)})
    return entries


def main():
    if not M3U_PATH.exists():
        sys.exit(f"Missing {M3U_PATH}")
    if not LCN_PATH.exists():
        sys.exit(f"Missing {LCN_PATH}")

    m3u_channels = parse_m3u(M3U_PATH)
    lcn_entries = parse_lcn_list(LCN_PATH)

    lcn_by_norm = {}
    for e in lcn_entries:
        lcn_by_norm.setdefault(e["norm"], []).append(e)

    results = []
    unmatched = []

    for ch in m3u_channels:
        n = norm(ch["name"])
        target = MANUAL_MAP.get(n)
        candidates = lcn_by_norm.get(target, []) if target else lcn_by_norm.get(n, [])

        if candidates:
            best = sorted(candidates, key=lambda e: e["lcn"])[0]
            results.append({"id": ch["id"], "name": ch["name"], "lcn": best["lcn"]})
        else:
            results.append({"id": ch["id"], "name": ch["name"], "lcn": None})
            unmatched.append(ch)

    # position: matched channels use their LCN; unmatched channels are appended
    # after the highest LCN, in their original m3u order, so the app can just
    # sort ascending by "position" with no null-handling of its own.
    max_lcn = max((r["lcn"] for r in results if r["lcn"] is not None), default=0)
    next_pos = max_lcn + 1
    for r in results:
        if r["lcn"] is not None:
            r["position"] = r["lcn"]
        else:
            r["position"] = next_pos
            next_pos += 1

    OUT_CHANNELS.parent.mkdir(parents=True, exist_ok=True)
    OUT_CHANNELS.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    OUT_UNMATCHED.write_text(
        json.dumps(unmatched, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    matched = len(m3u_channels) - len(unmatched)
    print(f"Wrote {OUT_CHANNELS} ({matched}/{len(m3u_channels)} channels matched to an LCN)")
    print(f"Wrote {OUT_UNMATCHED} ({len(unmatched)} channels without an LCN, for review)")


if __name__ == "__main__":
    main()
