import subprocess

result = subprocess.run(['python', '-m', 'flake8', 'app.py', 'main_gpu.py', 'services', '--select=F,E402,E9'], capture_output=True, text=True)
with open('critical_errors_utf8.txt', 'w', encoding='utf-8') as f:
    f.write(result.stdout)
