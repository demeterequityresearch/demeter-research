"""reports/ 폴더의 .docx / .pdf 를 Hugo 페이지로 변환합니다.

파일명 규칙: 2026-10-18_삼성전자.docx  ->  날짜 2026-10-18, 제목 '삼성전자'
같은 이름의 docx와 pdf가 함께 있으면 본문은 docx, PDF는 다운로드 링크로 붙습니다.
"""
import pathlib, re, shutil, subprocess

SRC = pathlib.Path("reports")
DST = pathlib.Path("content/reports")

# 리포트가 하나도 없어도 메뉴의 '리포트' 목록 페이지가 404가 나지 않도록 섹션 페이지를 만들어 둡니다
DST.mkdir(parents=True, exist_ok=True)
(DST / "_index.md").write_text('---\ntitle: "리포트"\n---\n', encoding="utf-8")

groups = {}
for f in SRC.iterdir():
    if f.suffix.lower() in (".docx", ".pdf"):
        groups.setdefault(f.stem, {})[f.suffix.lower()] = f

for stem, files in sorted(groups.items()):
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(.+)", stem)
    date, title = (m.group(1), m.group(2)) if m else (None, stem)

    bundle = DST / stem
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True)

    front = f'---\ntitle: "{title}"\n'
    if date:
        front += f"date: {date}\n"
    front += "---\n\n"

    body = ""
    if ".docx" in files:
        # 이미지는 페이지 번들 안의 media/ 로 추출되어 상대경로로 연결됩니다
        body = subprocess.run(
            ["pandoc", str(files[".docx"].resolve()), "-t", "gfm", "--extract-media=."],
            cwd=bundle, capture_output=True, text=True, check=True,
        ).stdout
    if ".pdf" in files:
        shutil.copy(files[".pdf"], bundle / "report.pdf")
        if not body:
            body = '<iframe src="report.pdf" width="100%" height="900" style="border:0"></iframe>\n\n'
        body += "\n\n[📄 PDF 다운로드](report.pdf)\n"

    (bundle / "index.md").write_text(front + body, encoding="utf-8")
    print(f"converted: {stem}")
