import os
import requests
import xml.etree.ElementTree as ET

GROUP_URL = "https://steamcommunity.com/groups/joint-command/memberslistxml/?xml=1"
PREFIX = "[(JCom)]"
# Automatically write to the same directory as this script
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "whitelist.txt")

def fetch_group_members():
    print("Fetching group member list...")
    xml_data = requests.get(GROUP_URL).text
    root = ET.fromstring(xml_data)
    return [m.text for m in root.findall(".//steamID64")]

def fetch_steam_name(steamid):
    try:
        profile_url = f"https://steamcommunity.com/profiles/{steamid}/?xml=1"
        xml_data = requests.get(profile_url, timeout=5).text
        root = ET.fromstring(xml_data)
        return root.findtext("steamID") or "Unknown"
    except Exception as e:
        print(f"Error fetching {steamid}: {e}")
        return "Unknown"

def generate_whitelist():
    steam_ids = fetch_group_members()
    lines = []
    for sid in steam_ids:
        name = fetch_steam_name(sid)
        formatted = f"Admin={sid}:Whitelist // {PREFIX} {name}"
        lines.append(formatted)
        print(formatted)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n✅ {len(lines)} entries written to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_whitelist()
