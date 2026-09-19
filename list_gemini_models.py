import os
import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

r = httpx.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    params={"key": key},
    timeout=30.0,
)
r.raise_for_status()
data = r.json()

for m in data.get("models", []):
    name = m["name"].replace("models/", "")
    methods = m.get("supportedGenerationMethods", [])
    if "generateContent" in methods:
        print(f"  {name}")