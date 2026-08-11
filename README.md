# Runner

```
   ____________  ____  ____  ___   ____   ___   ____  ______   _____________
 /|            |/|  |  |  |/|   \/|    |/|   \/|    ||      |/|            |
/ |    ____    | |  |  |  | |    \|    | |    \|    ||   ___| |    ____    |
| |    |  |    | |  |  |  | |          | |          ||  |  /  |    |  |    |
| |    ''''   /| |  |  |  | |          | |          ||  ---|  |    ''''   /
| |          \ | |  ----  | |          | |          ||  ---|  |          \
| |           \| |        | |     |\   | |     |\   ||  |_/_  |           \
| |     \      \ |        | |     | |  | |     | |  ||      | |     \      \
| |     |\      \\________/ |_____| |__| |_____| |__||______| |     |\      \
| |_____| \      \       / /     / /  / /     / /  //      /| |_____| \      \
| /     \  \______\------|/_____/|/__/|/_____/|/__//______/ | /     \  \______\
|/       \| |     |        DOS 1998  ->  PYTHON 2026        |/       \| |     |
/_________\ |     |        BRIAN GEIS ......... CODE        /_________\ |     |
           \|_____|        KRIS SZLAKOWSKI ..... ART                   \|_____|
```

A cross-platform Python port of *Runner*, a 320x200 DOS shooter written in C in 1998.

## Download

Ready-to-run builds for Windows, macOS, and Linux are on the [Releases](https://github.com/briangeis/runner/releases) page. Unpack one and start it. There is nothing to install and no need for Python.

Windows and macOS each ask once before running a program they have not seen before, because these builds are not code signed. The release notes cover the prompt on each system.

## Setup

Running from source needs Python 3.11 or newer. `pygame-ce` is the only dependency, and it installs as a prebuilt wheel on Linux, Windows, and macOS.

### Linux and macOS

```bash
git clone https://github.com/briangeis/runner
cd runner
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m runner
```

The virtual environment is created once. To play again later:

```bash
cd runner
source .venv/bin/activate
python -m runner
```

### Windows

```powershell
git clone https://github.com/briangeis/runner
cd runner
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m runner
```

The virtual environment is created once. To play again later:

```powershell
cd runner
.venv\Scripts\activate
python -m runner
```

## License

The code is licensed under the [GNU General Public License v3.0](LICENSE).

The artwork is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License](runner/assets/LICENSE), and remains the copyright of Kris Szlakowski.
