# -*- coding: utf-8 -*-
"""通过 editor_sdk 生成三份 Word 报告"""
import json, re, subprocess, sys

SDK = r"D:\aaa\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\workbuddy-local-office-edit\edsdk.py"
DOCS = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw\docs"
SRC = DOCS + r"\src"

def call(tool, **kw):
    args = ["python", SDK, "call", tool]
    if kw:
        args += ["--json", json.dumps(kw, ensure_ascii=False)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout.strip() + "\n" + r.stderr.strip()).strip()
    print(f"== {tool} ==\n{out[:400]}\n")
    if r.returncode != 0 or "error" in out.lower()[:60]:
        raise RuntimeError(f"{tool} failed")
    return out

def grab(out, key):
    m = re.search(rf'"?{key}"?\s*[:=]\s*("?[^,}}\s]+"?)', out)
    return m.group(1).strip('"') if m else None

def build_doc(md_parts, out_name, image=None):
    out = call("create_doc")
    fid = grab(out, "file_id")
    pos = 0
    for i, part in enumerate(md_parts):
        out = call("doc_insert_markdown", file_id=fid, idx=pos,
                   markdown="file://" + part)
        pos = int(grab(out, "position") or grab(out, "last_edit_index") or pos)
        if image and i == 0:
            out = call("doc_insert_image", file_id=fid, idx=pos,
                       image_path=image, w=660)
            p2 = grab(out, "position") or grab(out, "last_edit_index")
            if p2: pos = int(p2)
            out = call("doc_insert_paragraph", file_id=fid, idx=pos)
            p3 = grab(out, "next_index") or grab(out, "position")
            pos = int(p3) if p3 else pos + 1
    call("doc_set_page_number", file_id=fid, position="center",
         format="decimal", scope="whole_doc", section_index=0,
         text_format={"font_size": 9})
    call("save_file", file_id=fid, file_path=DOCS + "\\" + out_name)
    return fid

build_doc([SRC + r"\01_数据质量对比报告.md"], "数据质量对比报告.docx")
build_doc([SRC + r"\02a.md", SRC + r"\02b.md"], "数仓架构设计文档.docx",
          image=DOCS + r"\dw_architecture.png")
build_doc([SRC + r"\03_探索性分析简报.md"], "探索性分析简报.docx")
print("ALL DONE")
