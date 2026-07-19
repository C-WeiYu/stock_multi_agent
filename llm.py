from __future__ import annotations

from langchain_ollama import ChatOllama

OLLAMA_MODEL = "llama3.2:3b"  # router 與所有 sub-agent 共用的模型，可改成你 ollama 上有的模型


def get_llm(temperature: float = 0) -> ChatOllama:
    return ChatOllama(model=OLLAMA_MODEL, temperature=temperature)
