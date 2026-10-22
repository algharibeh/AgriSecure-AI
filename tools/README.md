# tools: what `reproduce.bat` needs so that nothing has to be installed

Part of the AgriSecure-AI project.

| File | What it is | Source | SHA-256 |
| --- | --- | --- | --- |
| `python-3.9.13-embed-amd64.zip` | Python 3.9.13 for 64-bit Windows, python.org's "embeddable package": the interpreter and standard library as a plain zip, no installer, no registry entries | https://www.python.org/ftp/python/3.9.13/python-3.9.13-embed-amd64.zip (downloaded October 21, 2026; MD5 57731cf80b1c429a0be7133266d7d7cf) | `938a1f3b80d580320836260612084d74ce094a261e36f9ff3ac7b9463df5f5e4` |
| `get-pip.py` | pip's official bootstrap script for Python 3.9, because the embeddable package ships without pip | https://bootstrap.pypa.io/pip/3.9/get-pip.py (downloaded October 21, 2026) | `95c0ae79ccf9ac1e47e4187f49081d6ae1f45997afd4549e14f37337cbcfd766` |

Both files are redistributed unchanged. Python is distributed under the Python
Software Foundation License; pip under the MIT License.

What `reproduce.bat` does with them on the first run, in order:

1. Unpacks the zip into `tools/python/` with PowerShell's `Expand-Archive`
   (present on every Windows 10 and 11).
2. Rewrites `tools/python/python39._pth` to end with `import site`, so that the
   interpreter sees the packages installed into its own `Lib/site-packages`
   (the package ships with that line commented out).
3. Runs `get-pip.py` with that interpreter to install pip into it.
4. Installs the pinned `requirements.txt` into it, prebuilt wheels only, and
   writes `tools/python/requirements.ok`.
5. Runs `reproduce.py` with `tools/python/python.exe`. Later runs skip 1 to 4.

`tools/python/` is ignored by git; delete it to start over. A machine that
already has a `.venv` with `requirements.ok` (the author's own clone) keeps
using that instead. The only download the first run makes is the pinned
packages, about 120 MB, from the Python Package Index.
