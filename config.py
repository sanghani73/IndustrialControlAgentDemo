import os
from dotenv import load_dotenv
from anthropic import Anthropic
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

if not MONGODB_URI:
    raise ValueError("Missing MONGODB_URI environment variable.")
if not LLM_API_KEY:
    raise ValueError("Missing LLM_API_KEY environment variable.")
if not LLM_MODEL:
    raise ValueError("Missing LLM_MODEL environment variable.")

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["manufacturing_ops"]

# The Anthropic Python SDK is used as the HTTP client. It supports a
# base_url override so the same client can talk to a Grove-style gateway
# or any provider endpoint that implements the Anthropic Messages API.
_client_kwargs = {"api_key": LLM_API_KEY}
if LLM_BASE_URL:
    base = LLM_BASE_URL.rstrip("/")
    for suffix in ["/v1/messages", "/v1"]:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    _client_kwargs["base_url"] = base

llm_client = Anthropic(**_client_kwargs)
