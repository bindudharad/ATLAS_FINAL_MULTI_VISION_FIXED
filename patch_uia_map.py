import re

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\mapping\uia_map.py", "r") as f:
    content = f.read()

value_rejection_pattern = """

#: Patterns/values that are commonly seen as FIELD VALUES on the MPF source panel.
KNOWN_VALUE_PATTERNS = (
    "andhra", "arunachal", "assam", "bihar", "chhattisgarh", "goa", "gujarat", 
    "haryana", "himachal", "jharkhand", "karnataka", "kerala", "madhya", "maharashtra",
    "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab", "rajasthan",
    "sikkim", "tamil", "telangana", "tripura", "uttar", "uttarakhand", "bengal",
    "delhi", "chandigarh", "lakshadweep", "puducherry", "ladakh", "jammu",
    "chamar", "turi", "mittal", "kayast", "brahmin", "rajput", "yadav", "gupta",
    "agarwal", "sharma", "singh", "kumar", "devi", "prasad", "das", "pandey",
    "hindu", "muslim", "christian", "sikh", "buddhist", "jain", "parsi",
    "hindi", "bengali", "telugu", "marathi", "tamil", "urdu", "gujarati",
    "kannada", "malayalam", "punjabi", "odia", "assamese", "maithili",
    "never married", "married", "divorced", "widowed", "single", "separated",
    "uttara", "phalguni", "uthram", "palkuni", "rohini", "mrigashira", "ardra",
    "punarvasu", "pushya", "ashlesha", "magha", "purva", "hasta",
    "chitra", "swati", "vishakha", "anuradha", "jyeshtha", "mula", "purvashada",
    "uttarashada", "shravana", "dhanishta", "shatabhisha", "purvabhadra", "uttarabhadra",
    "revati", "ashwini", "bharani", "krittika",
    "simha", "leo", "mesha", "aries", "vrishabha", "taurus", "mithuna", "gemini",
    "karka", "cancer", "kanya", "virgo", "tula", "libra", "vrishchika", "scorpio",
    "dhanu", "sagittarius", "makara", "capricorn", "kumbha", "aquarius", "meena", "pisces",
    "1st pada", "2nd pada", "3rd pada", "4th pada", "1st", "2nd", "3rd", "4th",
    "male", "female", "other", "transgender",
    "own", "rent", "rented", "lease", "ancestral",
    "veg", "vegetarian", "non-veg", "nonveg", "non vegetarian", "eggetarian",
    "no health problems", "healthy", "none", "normal",
    "alive", "passed away", "deceased", "expired",
    "defence", "civil", "services", "salaried", "self-employed", "student", "retired",
    "unemployed", "business", "professional", "housewife",
    "lakh", "crore", "annually", "monthly",
)


def is_likely_value(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False
    if re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", t):
        return True
    if re.search(r"\d{1,2}:\d{2}:\d{2}", t):
        return True
    if t in KNOWN_VALUE_PATTERNS:
        return True
    if t.endswith(("lakh", "crore", "kg", "cm", "ft", "in", "annually", "monthly")):
        return True
    if re.fullmatch(r"[\d,./: -]+", t):
        return True
    if t == t.lower() and len(t) < 20 and not any(c.isupper() for c in text):
        known_short_labels = {"dob", "pan", "mbi", "rai", "app", "age", "sex", "f", "m"}
        if t not in known_short_labels:
            return True
    return False


def is_noise_or_value_label(text: str) -> bool:
    return is_noise_label(text) or is_likely_value(text)
"""

insert_pos = content.find('NOISE_LABELS_EXACT = {')
if insert_pos > 0:
    brace_count = 0
    i = insert_pos
    while i < len(content):
        if content[i] == "{":
            brace_count += 1
        elif content[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                insert_pos = i + 1
                break
        i += 1
    content = content[:insert_pos] + value_rejection_pattern + content[insert_pos:]

old_parse = "            elif kind == \"ignored\":\n                section = \"ignored\"\n            continue  # section header, e.g. \"Religious an"
new_parse = "            elif kind == \"ignored\":\n                section = \"ignored\"\n            elif is_likely_value(line):\n                continue  # skip value-like lines that have no colon\n            continue  # section header, e.g. \"Religious an"
content = content.replace(old_parse, new_parse)

old_geo = "                if label and not is_noise_label(label) and label not in pairs:"
new_geo = "                if is_likely_value(label):\n                    if diagnostics is not None:\n                        diagnostics.reject(label, value, \"label_is_value\")\n                    i += 1\n                    continue\n                if label and not is_noise_label(label) and label not in pairs:"
content = content.replace(old_geo, new_geo)

old_ocr = "            if label and not is_noise_label(label) and label not in pairs and parts[1].strip():"
new_ocr = "            if is_likely_value(label):\n                if diagnostics is not None:\n                    diagnostics.reject(label, parts[1].strip(), \"label_is_value\")\n                continue\n            if label and not is_noise_label(label) and label not in pairs and parts[1].strip():"
content = content.replace(old_ocr, new_ocr)

old_right = "        if form_fields:\n            editable = form_fields\n        right_fields = [n for n in editable if n.rect is not None and n.rect.center[0] >= mid_x]\n        if not right_fields:\n            right_fields = editable\n        right_fields = [self._attach_declared(n, hwnd) for n in right_fields]"
new_right = "        if form_fields:\n            editable = form_fields\n        FORM_FIELD_TYPES = {\"Edit\", \"ComboBox\", \"List\", \"ListItem\", \"DataItem\", \"TreeItem\"}\n        right_fields = [\n            n for n in editable\n            if n.rect is not None \n            and n.rect.center[0] >= mid_x\n            and n.control_type in FORM_FIELD_TYPES\n        ]\n        if not right_fields:\n            right_fields = [n for n in editable if n.rect is not None and n.rect.center[0] >= mid_x]\n        right_fields = [self._attach_declared(n, hwnd) for n in right_fields]"
content = content.replace(old_right, new_right)

old_left = "            and _is_meaningful_label(n.name)\n            and _node_parent_name(n) not in right_form_parents\n        ]"
new_left = "            and _is_meaningful_label(n.name)\n            and not is_likely_value(n.name)  # CRITICAL: reject value-like text as labels\n            and _node_parent_name(n) not in right_form_parents\n        ]"
content = content.replace(old_left, new_left)

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\mapping\uia_map.py", "w") as f:
    f.write(content)
print("uia_map.py patched")
