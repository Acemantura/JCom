import os
import requests
import xml.etree.ElementTree as ET

# Constants
GROUP_URL = "https://steamcommunity.com/groups/joint-command/memberslistxml/?xml=1"
PREFIX = "[[ROM]]"

# Always resolve absolute paths correctly, even when run from GitHub Actions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "whitelist.txt")
MANUAL_ADD_FILE = os.path.join(BASE_DIR, "manual_additions.txt")
MANUAL_REMOVE_FILE = os.path.join(BASE_DIR, "manual_removals.txt")

# ---------------------------------------------------------------------------

def fetch_group_members():
    print("📡 Fetching group member list...")
    xml_data = requests.get(GROUP_URL).text
    root = ET.fromstring(xml_data)
    members = [m.text for m in root.findall(".//steamID64")]
    print(f"✅ Found {len(members)} group members")
    return members

def fetch_steam_name(steamid):
    try:
        profile_url = f"https://steamcommunity.com/profiles/{steamid}/?xml=1"
        xml_data = requests.get(profile_url, timeout=5).text
        root = ET.fromstring(xml_data)
        name = root.findtext("steamID") or "Unknown"
        return name.strip()
    except Exception as e:
        print(f"⚠️ Error fetching name for {steamid}: {e}")
        return "Unknown"

# ---------------------------------------------------------------------------
# Manual removals: parse, fetch names as needed, sort by first char case-insensitively,
# rewrite manual_removals.txt into canonical format and return a set of steamids to remove.
# ---------------------------------------------------------------------------

def parse_removal_line(line):
    """
    Parse a non-comment removal line. Returns (steamid, raw_name_or_none).
    Accepts:
      - Admin=765...:Whitelist // [[ROM]] NAME
      - Admin=765...:Whitelist // NAME
      - 7656119... (raw steamid)
      - 7656119... // NAME
    """
    line = line.strip()
    # whitelist-style
    if line.startswith("Admin=") and ":Whitelist" in line:
        try:
            steamid = line.split("Admin=")[1].split(":Whitelist")[0].strip()
            raw_name = None
            if "//" in line:
                raw_name = line.split("//", 1)[1].strip()
            return steamid, raw_name
        except Exception:
            pass

    # steamid // name
    if "//" in line:
        left, right = map(str.strip, line.split("//", 1))
        if left.isdigit() or len(left) > 10:
            return left, right

    # plain steamid
    if line.isdigit() or len(line) > 10:
        return line, None

    # unknown format — attempt to extract any digits in the line as steamid
    for token in line.split():
        if token.isdigit() or (len(token) > 10 and any(ch.isdigit() for ch in token)):
            return token, None

    return None, None

def make_canonical_removal_line(steamid, display_name):
    """Return Admin=...:Whitelist // [ROM] DisplayName"""
    # ensure prefix exists in the formatted line (consistent with whitelist)
    name_with_prefix = f"{PREFIX} {display_name}" if not display_name.startswith(PREFIX) else display_name
    return f"Admin={steamid}:Whitelist // {name_with_prefix}"

def load_manual_removals():
    comments = []
    parsed = []  # list of tuples (name_for_sort, steamid, canonical_line)

    if not os.path.exists(MANUAL_REMOVE_FILE):
        print("ℹ️ No manual_removals.txt found.")
        return set()

    print(f"🗂️ Reading {MANUAL_REMOVE_FILE} ...")
    with open(MANUAL_REMOVE_FILE, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                # preserve blank lines in comments block
                comments.append(line)
                continue
            if stripped.startswith("#"):
                comments.append(line)
                continue

            steamid, raw_name = parse_removal_line(stripped)
            if not steamid:
                print(f"⚠️ Could not parse removal line, skipping: {line}")
                continue

            # If raw_name exists and contains the prefix, strip prefix for sorting
            name_for_sort = None
            if raw_name:
                if raw_name.startswith(PREFIX):
                    name_for_sort = raw_name[len(PREFIX):].strip()
                else:
                    name_for_sort = raw_name.strip()

            # If no name given, fetch it (try-except to avoid aborting)
            if not name_for_sort:
                name_for_sort = fetch_steam_name(steamid)

            # canonicalize the stored line to the same format as whitelist
            canonical_line = make_canonical_removal_line(steamid, name_for_sort)
            parsed.append((name_for_sort, steamid, canonical_line))

    if not parsed:
        print("🗒️ No removal entries found (only comments/empty lines).")
        return set()

    # Sort by first character case-insensitive (primary), then full name lower (secondary), then steamid
    def sort_key(item):
        name, sid, _ = item
        name_stripped = (name or "").strip()
        if name_stripped:
            first = name_stripped[0].lower()
            return (first, name_stripped.lower(), sid)
        else:
            return (sid[0], sid, sid)

    parsed.sort(key=sort_key)

    # Rewrite manual_removals.txt: preserve comment block at top, then sorted entries
    print("🧾 Rewriting manual_removals.txt with sorted canonical entries ...")
    with open(MANUAL_REMOVE_FILE, "w", encoding="utf-8") as f:
        # write preserved comment lines first (if any)
        if comments:
            for c in comments:
                f.write(c.rstrip("\n") + "\n")
            f.write("\n")  # add a separating blank line
        # write canonical entries
        for _, _, canonical in parsed:
            f.write(canonical + "\n")

    print("🧾 Sorted removals (first 20 shown):")
    for name, sid, _ in parsed[:20]:
        display = name if name else sid
        print(f"  - {display} ({sid})")

    # Return set of steamids to remove
    return {sid for _, sid, _ in parsed}

# ---------------------------------------------------------------------------

def load_manual_additions():
    manual = []
    if os.path.exists(MANUAL_ADD_FILE):
        print(f"📝 Loading manual additions from {MANUAL_ADD_FILE}")
        with open(MANUAL_ADD_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "//" in line:
                    sid, name = map(str.strip, line.split("//", 1))
                else:
                    sid, name = line, None
                manual.append((name, sid))
    return manual




# ---------------------------------------------------------------------------

def generate_whitelist():
    steam_ids = fetch_group_members()
    entries = []

    # Fetch all group members with names
    for sid in steam_ids:
        name = fetch_steam_name(sid)
        entries.append((name, sid))

    # Manual additions
    manual_entries = load_manual_additions()
    for name, sid in manual_entries:
        if not any(s == sid for _, s in entries):
            if not name:
                name = fetch_steam_name(sid)
            entries.append((name, sid))
            print(f"✅ Added manual entry {sid} // {name}")

    # Manual removals
    removals = load_manual_removals()
    if removals:
        before = len(entries)
        entries = [(name, sid) for name, sid in entries if sid not in removals]
        after = len(entries)
        print(f"🚫 Removed {before - after} entries via manual_removals.txt")

    # Sort alphabetically by name (case-insensitive)
    entries.sort(key=lambda x: x[0].lower())

    # Format whitelist
    lines = [f"Admin={sid}:Whitelist // {PREFIX} {name}" for name, sid in entries]

    # Always overwrite file explicitly
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n✅ {len(lines)} entries written to {OUTPUT_FILE}")
    print(f"📄 Sample output:\n{lines[0] if lines else '(no entries)'}")

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    generate_whitelist()
