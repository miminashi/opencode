#!/usr/bin/env python3
"""glm レビュー用のプロンプトを組む（ヘッダ + 事前登録全文）。出力: tmp/glm_review_prompt_layer3.txt"""
import io

HEAD = "/home/ubuntu/projects/opencode/tmp/glm_review_prompt_layer3_head.txt"
PREREG = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/prereg_layer3.md"
OUT = "/home/ubuntu/projects/opencode/tmp/glm_review_prompt_layer3.txt"

body = io.open(HEAD, encoding="utf-8").read() + io.open(PREREG, encoding="utf-8").read()
io.open(OUT, "w", encoding="utf-8").write(body)
print(f"wrote {OUT} ({len(body)} chars)")
