
with open('api/routes/documents.py', 'r') as f:
    text = f.read()
text = text.replace('\\\\n\\\\n', '\\n\\n')
with open('api/routes/documents.py', 'w') as f:
    f.write(text)

