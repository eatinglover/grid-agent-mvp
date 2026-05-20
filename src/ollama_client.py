import requests


def ask_ollama(prompt: str, model: str = "qwen3:4b", host: str = "http://localhost:11434") -> str:
    """
    调用本地 Ollama 模型。
    """
    url = f"{host}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }

    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json().get("response", "")
