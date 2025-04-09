# Running the Inference App

## 🛠️ Setup Instructions

1. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure `CLUSTERIQ_API_URL` in [config file](./config.py)
3. Run mcp dev server

```bash
mcp dev server.py
```
