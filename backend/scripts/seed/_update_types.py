"""临时脚本：更新种子数据中的 property_type 值"""
import re, glob, os

seed_dir = os.path.dirname(os.path.abspath(__file__))
files = glob.glob(os.path.join(seed_dir, "*.py"))

for filepath in files:
    if os.path.basename(filepath) == "_update_types.py":
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'property_type' not in content:
        continue

    lines = content.split('\n')
    new_lines = []
    current_bedrooms = None
    changed = False

    for line in lines:
        m = re.search(r'"bedrooms":\s*(\d+)', line)
        if m:
            current_bedrooms = int(m.group(1))

        if '"property_type": "apartment"' in line:
            new_val = "2-bed" if (current_bedrooms and current_bedrooms >= 2) else "1-bed"
            line = line.replace('"property_type": "apartment"', f'"property_type": "{new_val}"')
            changed = True
        if '"property_type": "house"' in line:
            # house stays as house — no change
            pass

        new_lines.append(line)

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f'Updated: {os.path.basename(filepath)}')
    else:
        print(f'Skipped: {os.path.basename(filepath)} (no changes needed)')

print('\nDone.')
