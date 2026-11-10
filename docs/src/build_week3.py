# -*- coding: utf-8 -*-
"""通过 editor_sdk 生成第 3 周两份 Word 报告"""
import json, re, subprocess

SDK = r"D:\aaa\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\workbuddy-local-office-edit\edsdk.py"
DOCS = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw\docs"
SRC = DOCS + r"\src"
OUT_ANALYSIS = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw\analysis\out"


def call(tool, **kw):
    args = ["python", SDK, "call", tool]
    if kw:
        args += ["--json", json.dumps(kw, ensure_ascii=False)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout.strip() + "\n" + r.stderr.strip()).strip()
    print(f"== {tool} ==\n{out[:300]}\n")
    if r.returncode != 0 or "error" in out.lower()[:60]:
        raise RuntimeError(f"{tool} failed")
    return out


def grab(out, key):
    m = re.search(rf'"?{key}"?\s*[:=]\s*("?[^,}}\s]+"?)', out)
    return m.group(1).strip('"') if m else None


IMG_MARK = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$", re.M)


def build_doc(md_path, out_name):
    """把 markdown 中独立的图片行替换为真实图片插入。"""
    text = open(md_path, encoding="utf-8").read()
    # 将图片行替换为分段标记，生成 [ (kind, payload) ] 序列
    segments, last = [], 0
    for m in IMG_MARK.finditer(text):
        if text[last:m.start()].strip():
            segments.append(("md", None, text[last:m.start()].strip()))
        img = m.group(1)
        p = OUT_ANALYSIS + "\\" + img
        segments.append(("img", p, None))
        last = m.end()
    if text[last:].strip():
        segments.append(("md", None, text[last:].strip()))

    # 把 markdown 段落写到临时文件
    import os, uuid
    tmp_files = []
    for i, (kind, payload, content) in enumerate(segments):
        if kind == "md":
            tf = SRC + f"\\_wk3_tmp_{uuid.uuid4().hex[:6]}.md"
            open(tf, "w", encoding="utf-8", newline="\n").write(content)
            tmp_files.append(tf)

    out = call("create_doc")
    fid = grab(out, "file_id")
    pos = 0
    ti = 0
    for kind, payload, content in segments:
        if kind == "md":
            tf = tmp_files[ti]; ti += 1
            out = call("doc_insert_markdown", file_id=fid, idx=pos, markdown="file://" + tf)
            pos = int(grab(out, "position") or grab(out, "last_edit_index") or pos)
            os.remove(tf)
        else:
            out = call("doc_insert_image", file_id=fid, idx=pos, image_path=payload, w=620)
            p2 = grab(out, "position") or grab(out, "last_edit_index")
            if p2: pos = int(p2)
            out = call("doc_insert_paragraph", file_id=fid, idx=pos)
            p3 = grab(out, "next_index") or grab(out, "position")
            pos = int(p3) if p3 else pos + 1
    call("doc_set_page_number", file_id=fid, position="center", format="decimal",
         scope="whole_doc", section_index=0, text_format={"font_size": 9})
    call("save_file", file_id=fid, file_path=DOCS + "\\" + out_name)
    print(f"DONE -> {out_name}\n")


build_doc(SRC + r"\04_预测建模分析报告.md", "预测建模分析报告.docx")
build_doc(SRC + r"\05_AI智能洞察与反思.md", "AI智能洞察与反思.docx")
print("ALL DONE")
