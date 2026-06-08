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

