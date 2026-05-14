#!/usr/bin/env python3
"""一键构建知识库 — 从 seed 数据和 docx 文件构建 TF-IDF 索引"""

import os
import sys

# 确保在项目根目录
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.kb_client import KnowledgeBase

kb = KnowledgeBase()
success = kb.build(rebuild=True)

if success:
    print(f"\n✅ 知识库构建成功！共 {len(kb.chunks)} 条知识片段")
    sys.exit(0)
else:
    print("\n❌ 知识库构建失败")
    sys.exit(1)
