#!/bin/bash
# Test if llama-server honors tool_choice="required" with a single tool

curl -s http://10.1.4.14:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "I need to exit. What should I do?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "plan_exit",
          "description": "Call this to exit plan mode.",
          "parameters": {"type": "object", "properties": {}}
        }
      }
    ],
    "tool_choice": "required",
    "max_tokens": 200,
    "temperature": 0.55
  }'
