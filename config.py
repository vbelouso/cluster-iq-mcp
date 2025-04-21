import os

from dotenv import load_dotenv

load_dotenv()

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "phi:latest")
CLUSTERIQ_API_URL = os.getenv("CLUSTERIQ_API_URL", "http://localhost:8080")
CLUSTERIQ_API_TIMEOUT = int(os.getenv("CLUSTERIQ_API_TIMEOUT", 120))

