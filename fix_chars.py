import re

filepath = r"D:\XJTLU Y2S1\Obsidian_Vault\Main\XJTLU\Sem2\Rental Housing Structure\frontend\src\views\MapSearch.vue"

with open(filepath, 'rb') as f:
    data = f.read()

text = data.decode('utf-8')

# The template has been corrupted. Let me fix the most critical issues:
# 1. In template: }}/? {{ numberFormat... -> }}/\u00a5{{ numberFormat...
text = re.sub(r'\}\}/\? \{\{ numberFormat', r'}}/\u00a5{{ numberFormat', text)
text = re.sub(r'\}\}/\?\{\{ numberFormat', r'}}/\u00a5{{ numberFormat', text)

# 2. ?/? ? {{ bedrooms -> \u00a5/\u6708 \u00b7 {{ bedrooms
text = re.sub(r'\?/\? \? \{\{ p\.bedrooms', r'\u00a5/\u6708 \u00b7 {{ p.bedrooms', text)

# 3. Fix script section: \u00a5${numberFormat -> keep
text = re.sub(r'\?/\? \? \$\{p\.bedrooms', r'\u00a5/\u6708 \u00b7 ${p.bedrooms', text)

# 4. Fix popup: same patterns in buildPopupContent
text = re.sub(r'\?/\? \? \$\{p\.bedrooms\}', r'\u00a5/\u6708 \u00b7 ${p.bedrooms}', text)

# 5. Fix emoji and Chinese in template
replacements = [
    ('\u250c\u2500\u25b6', '\U0001f50d'),  # search icon equivalent
    ('\u25b6\ufe0f', '\U0001f4cd'),  # pin
    ('location pin', '\U0001f4cd'),
]

# 6. Broader: find all ? that should be unicode in template section
# Actually let me just check what's broken and report
import unicodedata

# Find all positions where we have bare ? (0x3F) that might be corrupted unicode
# These appear after ASCII chars in contexts that should have CJK/special chars
positions = []
for m in re.finditer(r'[\x20-\x7e]\?[\x20-\x7e\{\}]', text):
    ctx = text[max(0,m.start()-5):m.end()+5]
    positions.append((m.start(), repr(ctx)))

# Write result
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print('Fixed. Problem spots:', len(positions))
for pos, ctx in positions[:5]:
    print(f'  {pos}: {ctx}')
