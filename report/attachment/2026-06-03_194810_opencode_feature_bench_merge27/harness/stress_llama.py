import json, urllib.request, time

URL = "http://10.1.4.14:8000/v1/chat/completions"
# 大きめのプロンプト（opencode の system prompt 規模を模擬）。約数千トークン。
big = ("You are a coding assistant working on a Ruby on Rails 8.1 project. " * 400)
payload = {
    "model": "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL",
    "messages": [
        {"role": "system", "content": big},
        {"role": "user", "content": "List 5 steps to add a search feature to an index page. Think step by step."},
    ],
    "max_tokens": 600,
    "temperature": 0.6,
}
data = json.dumps(payload).encode()
req = urllib.request.Request(URL, data=data, headers={
    "Content-Type": "application/json",
    "Authorization": "Bearer aaaaa",
})
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        obj = json.load(r)
    u = obj.get("usage", {})
    tm = obj.get("timings", {})
    print("OK", "prompt_tokens=", u.get("prompt_tokens"), "completion_tokens=", u.get("completion_tokens"))
    print("eval_t/s=", round(tm.get("predicted_per_second", 0), 2), "elapsed=", round(time.time() - t0, 1))
    print("finish=", obj["choices"][0].get("finish_reason"))
except Exception as e:
    print("FAILED:", type(e).__name__, e, "elapsed=", round(time.time() - t0, 1))
