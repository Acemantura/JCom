import os
import requests
import xml.etree.ElementTree as ET

# Constants
GROUP_URL = "https://steamcommunity.com/groups/joint-command/memberslistxml/?xml=1"
PREFIX = "[(JCom)]"

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

def load_manual_removals():
    removals = set()
    if os.path.exists(MANUAL_REMOVE_FILE):
        print(f"🗑️ Loading manual removals from {MANUAL_REMOVE_FILE}")
        with open(MANUAL_REMOVE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Extract SteamID from full whitelist format
                if line.startswith("Admin=") and ":Whitelist" in line:
                    try:
                        steamid = line.split("Admin=")[1].split(":Whitelist")[0].strip()
                        removals.add(steamid)
                        continue
                    except Exception:
                        pass

                # Otherwise assume the line itself is the SteamID
                if line.isdigit() or len(line) > 10:
                    removals.add(line)

    print(f"🗑️ Loaded {len(removals)} removal entries")
    return removals


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
