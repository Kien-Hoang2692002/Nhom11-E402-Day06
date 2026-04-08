### 1. Setup Environment
Copy the `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```
### 2. Setup venv
```bash
python -m venv venv

source venv/Scripts/activate 
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt

playwright install chromium
```

### 4. Run project
```bash
python agent.py
```

### 5. Run fastapi
```bash
uvicorn main:app --reload
```

