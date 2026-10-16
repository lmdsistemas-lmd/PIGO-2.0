import os
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED

if os.environ.get('COMPUTERNAME') != 'WIN-JG1E0O7FSBS':
    raise SystemExit('Execute na VM WIN-JG1E0O7FSBS.')

root = Path(r'C:\Projetos\P.I.G.O')
if not (root / 'backend/app/main.py').is_file():
    raise SystemExit('Backend atual nao encontrado.')

output = Path(os.environ['TEMP']) / ('PIGO-backend-VM-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.zip')
files = []
for folder, suffix in [('app', '.py'), ('migrations', '.sql'), ('scripts', '.py')]:
    for path in (root / 'backend' / folder).rglob('*'):
        if path.is_file() and path.suffix.lower() == suffix and '__pycache__' not in path.parts:
            if not path.is_symlink() and path.resolve().is_relative_to(root.resolve()):
                files.append(path)
requirements = root / 'backend/requirements.txt'
if requirements.is_file():
    files.append(requirements)
with ZipFile(output, 'x', ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path, path.relative_to(root).as_posix())
print('ZIP criado:', output)
print('Arquivos de fontes:', len(set(files)))
