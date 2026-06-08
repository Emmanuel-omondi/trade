Skelter Trader Agent

Local forex trading agent combining lightweight gradient-tree experts, an Echo State Network, a Bayesian reasoning engine, and an evolutionary meta-learner.

Quick start

1. Create a Python 3.10+ environment and install requirements:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. If MSYS2/Mingw is not installed, run the helper script to install it automatically:

```powershell
.\install_msys2.ps1
```

3. (Optional) Build native feature engine on Windows using MinGW:

```powershell
.\build_feature_engine.bat
```

4. Edit `config/settings.json` with your broker settings. For FXPro/FXPesa set `broker` to `rest` and configure `broker_base_url` and `broker_api_key`. Note: public REST APIs for FxPro/FXPesa are not publicly documented; FxPro primarily exposes trading via MT4/MT5 and cTrader platforms. If you don't have a REST API endpoint, use `mt5` as `broker` or choose a broker with a documented REST API (OANDA, IG, etc.).

4. Run the app:

```bash
python main.py
```

Notes

- The app will prefer a native compiled feature engine if available; otherwise it uses the Python fallback.
- For FXPro/FXPesa you must provide a REST endpoint matching the simple API paths used by `core/data/brokers.GenericRESTBridge` (e.g. `/candles`, `/tick`, `/order`, `/positions`). If your broker provides a different API, adapt `core/data/brokers.py` accordingly.
 - If you want an installer for Windows, use the provided `build_installer.bat` which runs PyInstaller to produce a single-file executable. Provide an `assets\app.ico` if you want a custom icon. Example:

```powershell
pip install pyinstaller
.\build_installer.bat
```

 - I checked FxPro and FXPesa websites and did not find a publicly documented REST trading API; FxPro exposes MT5/cTrader. I recommend using the `mt5` broker in `config/settings.json` or switching to a broker with a public REST API such as OANDA if you prefer REST.

