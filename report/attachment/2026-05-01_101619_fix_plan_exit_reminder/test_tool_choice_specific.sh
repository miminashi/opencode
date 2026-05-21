#!/bin/bash
# Test if llama-server honors tool_choice with specific tool name
# (The format used by AI SDK when toolChoice = { type: 'tool', toolName: 'X' })

echo "=== Test 1: tool_choice as object {function: {name}} ==="
curl -s http://10.1.4.14:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M",
    "messages": [{"role": "user", "content": "I want to go home."}],
    "tools": [
      {"type": "function", "function": {"name": "plan_exit", "description": "Exit plan mode", "parameters": {"type": "object", "properties": {}}}},
      {"type": "function", "function": {"name": "task", "description": "Run subagent", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}}}}
    ],
    "tool_choice": {"type": "function", "function": {"name": "plan_exit"}},
    "max_tokens": 100,
    "temperature": 0.55
  }' | head -c 500

echo ""
echo ""

echo "=== Test 2: tool_choice = required, with multiple tools ==="
curl -s http://10.1.4.14:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M",
    "messages": [{"role": "user", "content": "I want to go home."}],
    "tools": [
      {"type": "function", "function": {"name": "plan_exit", "description": "Exit plan mode", "parameters": {"type": "object", "properties": {}}}},
      {"type": "function", "function": {"name": "task", "description": "Run subagent", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}}}}
    ],
    "tool_choice": "required",
    "max_tokens": 100,
    "temperature": 0.55
  }' | head -c 500
