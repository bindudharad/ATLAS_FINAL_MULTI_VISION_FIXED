with open('main.py', 'r') as f:
    content = f.read()

content = content.replace('find_windows_by_title(\
args.title\)', 'find_windows_by_title(args.title)')
with open('main.py', 'w') as f:
    f.write(content)
print('Done')
