"""Central configuration. All tunable thresholds live here, not scattered in code."""
import os

# Which inference provider to use. Both serve Llama 3.3 70B, so the classifier
# prompt and eval baseline carry across; only the endpoint and key change.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()  # "groq" or "nvidia"

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# NVIDIA NIM (build.nvidia.com) - OpenAI-compatible, separate free quota.
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")


def active_model() -> str:
    return NVIDIA_MODEL if LLM_PROVIDER == "nvidia" else GROQ_MODEL

# Below this classifier confidence, the case is held for a human before any action is sent.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# Max attempts to get schema-valid JSON out of the LLM before the rules fallback takes over.
LLM_MAX_ATTEMPTS = 2

DB_PATH = os.getenv("DB_PATH", "triage.db")

# SLA targets in minutes, by request type.
SLA_MINUTES = {
    "billing_dispute": 24 * 60,
    "general_enquiry": 48 * 60,
    "service_request": 8 * 60,
    "complaint": 60,
}