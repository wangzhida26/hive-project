# -*- coding: utf-8 -*-
"""通过 editor_sdk 生成第 4 周两份 Word（部署手册 / API 配置指南）"""
import json, re, subprocess, os, uuid

SDK = r"D:\aaa\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\workbuddy-local-office-edit\edsdk.py"
BASE = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw"
DOCS = BASE + r"\docs"
SRC = DOCS + r"\src"
SCREEN = BASE + r"\screen"

IMG_MARK = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$", re.M)


def call(tool, **kw):
    args = ["python", SDK, "call", tool]
    if kw:
        args += ["--json", json.dumps(kw, ensure_ascii=False)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout.strip() + "\n" + r.stderr.strip()).strip()
    print(f"== {tool} ==\n{out[:200]}\n")
    if r.returncode != 0:
        raise RuntimeError(f"{tool} failed: {out[:300]}")
    return out


def grab(out, key):
    m = re.search(rf'"?{key}"?\s*[:=]\s*("?[^,}}\s]+"?)', out)
    return m.group(1).strip('"') if m else None


IMG_RESOLVE = {
    "大屏截图.png": SCREEN + r"\大屏截图.png",
}


def build_doc(md_path, out_name):
    """按段落分块插入（整块 HTML 过大时 editor_sdk 转换失败）。"""
    text = open(md_path, encoding="utf-8").read()
    # 以图片行分段
    blocks, last = [], 0
    for m in IMG_MARK.finditer(text):
        chunk = text[last:m.start()]
        if chunk.strip():
            blocks.append(("md", None, chunk))
        blocks.append(("img", os.path.join(os.path.dirname(md_path), os.path.basename(m.group(1))), None))
        last = m.end()
    if text[last:].strip():
        blocks.append(("md", None, text[last:]))

    out = call("create_doc")
    fid = grab(out, "file_id")
    fpath = grab(out, "file_path")
    call("open_file", file_path=fpath, file_type="doc", wait=True)

    pos = 0
    n = 0
    for kind, payload, content in blocks:
        if kind == "img":
            out = call("doc_insert_image", file_id=fid, idx=pos, image_path=payload, w=640)
            p2 = grab(out, "position") or grab(out, "last_edit_index")
            if p2: pos = int(p2)
            out = call("doc_insert_paragraph", file_id=fid, idx=pos)
            p3 = grab(out, "next_index") or grab(out, "position")
            pos = int(p3) if p3 else pos + 1
            # 图片二进制经 SSE 流式上传，等待落盘完成
            import time as _t
            _t.sleep(3)
            gi = call("doc_get_images", file_id=fid)
            print("  images registered:", gi.count('"source"'), gi[-150:].replace("\n", " "))
            continue
        # md 块按空行再切小段插入
        paras = re.split(r"\n\s*\n", content.strip())
        for para in paras:
            if not para.strip():
                continue
            n += 1
            tf = SRC + f"\\_w4p_{n}.md"
            open(tf, "w", encoding="utf-8", newline="\n").write(para.strip())
            out = call("doc_insert_markdown", file_id=fid, idx=pos, markdown="file://" + tf)
            p2 = grab(out, "position") or grab(out, "last_edit_index")
            if p2: pos = int(p2)
            os.remove(tf)
    call("doc_set_page_number", file_id=fid, position="center", format="decimal",
         scope="whole_doc", section_index=0, text_format={"font_size": 9})
    call("save_file", file_id=fid, file_path=DOCS + "\\" + out_name)
    print(f"DONE -> {out_name}\n")


build_doc(SRC + r"\06_部署手册.md", "部署手册.docx")
build_doc(SRC + r"\07_API配置指南.md", "API配置指南.docx")
print("ALL DONE")
