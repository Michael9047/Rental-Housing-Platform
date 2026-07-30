"""Fix NPC center coordinates using known Singapore neighborhood coordinates."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Known Singapore neighborhood coordinates (approx centers)
KNOWN_COORDS = {
    "Ang Mo Kio": (1.3691, 103.8488),
    "Ang Mo Kio North": (1.3750, 103.8470),
    "Ang Mo Kio South": (1.3630, 103.8450),
    "Bedok": (1.3236, 103.9303),
    "Bishan": (1.3509, 103.8488),
    "Bukit Batok": (1.3491, 103.7496),
    "Bukit Merah East": (1.2821, 103.8266),
    "Bukit Merah West": (1.2850, 103.8150),
    "Bukit Panjang": (1.3786, 103.7625),
    "Bukit Timah": (1.3294, 103.8021),
    "Changi": (1.3430, 103.9620),
    "Choa Chu Kang": (1.3840, 103.7440),
    "Clementi": (1.3152, 103.7648),
    "Geylang": (1.3179, 103.8874),
    "Hougang": (1.3716, 103.8930),
    "Jurong East": (1.3329, 103.7436),
    "Jurong West": (1.3404, 103.7065),
    "Kampong Java": (1.3100, 103.8450),
    "Marina Bay": (1.2806, 103.8570),
    "Marine Parade": (1.3030, 103.9080),
    "Nanyang": (1.3480, 103.6830),
    "Orchard": (1.3048, 103.8318),
    "Pasir Ris": (1.3739, 103.9523),
    "Punggol": (1.4010, 103.9075),
    "Queenstown": (1.2940, 103.8000),
    "Rochor": (1.3040, 103.8530),
    "Sembawang": (1.4510, 103.8210),
    "Sengkang": (1.3906, 103.8900),
    "Serangoon": (1.3516, 103.8710),
    "Tampines": (1.3531, 103.9443),
    "Toa Payoh": (1.3343, 103.8563),
    "Woodlands": (1.4360, 103.7860),
    "Woodlands East": (1.4420, 103.7960),
    "Woodlands West": (1.4330, 103.7750),
    "Woodleigh": (1.3390, 103.8710),
    "Yishun": (1.4300, 103.8350),
    "Yishun North": (1.4360, 103.8350),
    "Yishun South": (1.4250, 103.8350),
    "Checkpoint": (1.4440, 103.7690),
}

target = os.path.join(os.path.dirname(__file__), "..", "app", "services", "sg_crime_data.py")
with open(target, encoding="utf-8") as f:
    content = f.read()

# Parse the NPC_CENTERS dict using ast
import ast
# Find the dict
start = content.find("SG_NPC_CENTERS: dict[str, tuple[float, float]] = {")
if start < 0:
    print("ERROR: cannot find SG_NPC_CENTERS")
    sys.exit(1)
start = content.find("{", start)
# Find matching closing brace
depth = 0
end = start
for i in range(start, len(content)):
    if content[i] == "{":
        depth += 1
    elif content[i] == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break

old_dict_str = content[start:end]
# Parse old keys
old_lines = old_dict_str.strip()[1:-1].split("\n")
new_lines = []

for line in old_lines:
    line = line.strip()
    if not line or not line.startswith('"'):
        continue
    # Extract key: "Division - NPC Name": (x, y),
    key_end = line.find('":')
    if key_end < 0:
        new_lines.append(line)
        continue
    key = line[1:key_end]

    # Try to match to known coords
    matched_coord = None
    # Extract the NPC sub-name (after " - ")
    if " - " in key:
        sub = key.split(" - ")[-1].replace(" NPC", "")
        matched_coord = KNOWN_COORDS.get(sub)
    if not matched_coord:
        # Try matching division name
        div = key.split(" Police Division")[0].split(" - ")[0]
        matched_coord = KNOWN_COORDS.get(div)

    if matched_coord:
        new_lines.append(f'    "{key}": ({matched_coord[0]}, {matched_coord[1]}),')
    else:
        print(f"  NO MATCH: {key}")
        new_lines.append(line)

new_dict = "{\n" + "\n".join(new_lines) + "\n}"
content = content[:start] + new_dict + content[end:]

with open(target, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Updated {target}")
print(f"Matched {sum(1 for l in new_lines if l.strip().startswith('\"') and ('1.' in l or '103.' in l))} NPCs")
