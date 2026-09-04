with open('main.py', 'r') as f:
    content = f.read()

old1 = 'candidates = WindowGeometry.find_windows_by_title(\
MPF
Form
Filling\)'
new1 = 'candidates = WindowGeometry.find_windows_by_title(args.title)'
content = content.replace(old1, new1)

old2 = 'print(\
ERROR:
No
window
found
with
title:
MPF
Form
Filling\)'
new2 = 'print(\
ERROR:
No
window
found
with
title:
\ + args.title)'
content = content.replace(old2, new2)

with open('main.py', 'w') as f:
    f.write(content)
print('Fixed')
