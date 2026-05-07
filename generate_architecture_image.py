import os
import subprocess
import urllib.request
import json

# Ensure packages have __init__.py
packages = ['data', 'models', 'strategies', 'backtest', 'config']
for pkg in packages:
    if os.path.isdir(pkg):
        init_path = os.path.join(pkg, '__init__.py')
        if not os.path.exists(init_path):
            open(init_path, 'w').close()

# Use built-in urllib to avoid requiring 'requests'
def post_quickchart(dot_text, output_file):
    url = "https://quickchart.io/graphviz"
    data = json.dumps({"graph": dot_text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            with open(output_file, 'wb') as f:
                f.write(response.read())
        print(f"Successfully saved {output_file}")
    except Exception as e:
        print(f"Error rendering {output_file}: {e}")

# Run pyreverse
env = os.environ.copy()
# Adjust path if needed or just use current env assuming we run it with venv python
cmd = "pyreverse -o dot " + " ".join(["main.py"] + [p for p in packages if os.path.isdir(p)])
print("Running command:", cmd)
subprocess.run(cmd, shell=True, env=env)

if os.path.exists('classes.dot'):
    with open('classes.dot', 'r', encoding='utf-8') as f:
        post_quickchart(f.read(), 'ProjectChronos_UML_Classes.png')

if os.path.exists('packages.dot'):
    with open('packages.dot', 'r', encoding='utf-8') as f:
        post_quickchart(f.read(), 'ProjectChronos_Modules.png')
