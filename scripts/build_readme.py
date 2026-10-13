#!/usr/bin/env python3
"""Build README.md (English) and README.id.md (Indonesian) from the JSON files in data/.

The JSON files are the single source of truth for the tool lists, the category names
and the category icons. Edit them, then run:

    python3 scripts/build_readme.py           # rewrite both README files
    python3 scripts/build_readme.py --check   # exit 1 if a README is out of date (for CI)

Only the Python standard library is used (Python 3.8 or newer).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# language code -> (data file, README file)
TARGETS = {
    "en": (DATA_DIR / "tools.en.json", ROOT / "README.md"),
    "id": (DATA_DIR / "tools.id.json", ROOT / "README.id.md"),
}

# Text around the lists. Indonesian uses "Anda", like the tool descriptions in the data file.
TEXT = {
    "en": {
        "switch": "🌐 **English** | [Bahasa Indonesia](README.id.md)",
        "toc": "📑 Table of Contents",
        "others": "📌 Others",
        "contributing": "🙌 Contributing",
        "support": "⭐ Support",
        "contact": "📧 Contact",
        "top": "🔝 Back to Top",
        "contributing_body": [
            "Contributions are welcome!  ",
            "If you know a useful platform that should be listed here, "
            "feel free to open a Pull Request or create an Issue.  ",
            "To add a tool, edit both `data/tools.en.json` and `data/tools.id.json`, "
            "then run `python3 scripts/build_readme.py` to regenerate the README files.  ",
        ],
        "support_body": [
            "If you find this repository helpful, please consider giving it a **star** on GitHub — "
            "it helps others discover this collection too! ",
        ],
        "author": "Author",
        "footer": "Made with ❤️ by the community of developers, analysts, designers, and digital creators.",
    },
    "id": {
        "switch": "🌐 [English](README.md) | **Bahasa Indonesia**",
        "toc": "📑 Daftar Isi",
        "others": "📌 Lainnya",
        "contributing": "🙌 Kontribusi",
        "support": "⭐ Dukungan",
        "contact": "📧 Kontak",
        "top": "🔝 Kembali ke Atas",
        "contributing_body": [
            "Kontribusi sangat diterima!  ",
            "Jika Anda mengetahui platform bermanfaat yang layak masuk daftar ini, "
            "silakan buka Pull Request atau buat Issue.  ",
            "Untuk menambahkan alat, ubah `data/tools.en.json` dan `data/tools.id.json`, "
            "lalu jalankan `python3 scripts/build_readme.py` untuk membuat ulang file README.  ",
        ],
        "support_body": [
            "Jika repositori ini bermanfaat bagi Anda, mohon pertimbangkan untuk memberinya "
            "**bintang** di GitHub — ini membantu orang lain menemukan koleksi ini juga! ",
        ],
        "author": "Penulis",
        "footer": "Dibuat dengan ❤️ oleh komunitas pengembang, analis, desainer, dan kreator digital.",
    },
}

# Characters that would change how Markdown renders a name or a description.
RISKY = re.compile(r"[\[\]*_`<>|\\]")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def validate(en, idn):
    """Return a list of problems found in the two data files (empty list when they are fine)."""
    problems = []
    for code, data in (("en", en), ("id", idn)):
        for key in ("title", "description", "language", "categories"):
            if key not in data:
                problems.append("tools.%s.json: missing key %r" % (code, key))
        if data.get("language") != code:
            problems.append("tools.%s.json: language is %r, expected %r" % (code, data.get("language"), code))
    if problems:
        return problems

    if len(en["categories"]) != len(idn["categories"]):
        return ["the two files have a different number of categories"]

    seen_ids, seen_icons, seen_urls = set(), set(), set()
    for a, b in zip(en["categories"], idn["categories"]):
        label = a.get("id", "?")
        if a.get("id") != b.get("id"):
            problems.append("category order differs: %r vs %r" % (a.get("id"), b.get("id")))
            continue
        if label in seen_ids:
            problems.append("%s: duplicate category id" % label)
        seen_ids.add(label)
        icon = a.get("icon")
        if not icon or not isinstance(icon, str) or icon != icon.strip():
            problems.append("%s: missing or malformed icon" % label)
        elif icon != b.get("icon"):
            problems.append("%s: icon differs between languages (%r vs %r)" % (label, icon, b.get("icon")))
        elif icon in seen_icons:
            problems.append("%s: icon %s is used by another category" % (label, icon))
        seen_icons.add(icon)
        for code, cat in (("en", a), ("id", b)):
            for key in ("name", "description"):
                if not str(cat.get(key, "")).strip():
                    problems.append("%s (%s): empty %s" % (label, code, key))
        if len(a["tools"]) != len(b["tools"]):
            problems.append("%s: tool count differs (%d vs %d)" % (label, len(a["tools"]), len(b["tools"])))
            continue
        for x, y in zip(a["tools"], b["tools"]):
            if (x["name"], x["url"]) != (y["name"], y["url"]):
                problems.append("%s: tool order, name or URL differs: %r vs %r" % (label, x["name"], y["name"]))
            url = x["url"]
            if not url.startswith("https://") or any(ch in url for ch in " ()"):
                problems.append("%s: bad URL %r" % (label, url))
            if url in seen_urls:
                problems.append("%s: URL listed twice: %s" % (label, url))
            seen_urls.add(url)
            for code, tool in (("en", x), ("id", y)):
                if not tool["description"].strip():
                    problems.append("%s: empty description for %s (%s)" % (label, tool["name"], code))
                for field in ("name", "description"):
                    if RISKY.search(tool[field]):
                        problems.append("%s: Markdown character in %s of %s (%s)" % (label, field, tool["name"], code))
    return problems


def slug(heading_text):
    """GitHub heading anchor: lowercase, drop punctuation and emoji, spaces become hyphens."""
    return re.sub(r"[^\w\- ]", "", heading_text.lower(), flags=re.UNICODE).replace(" ", "-")


def build(data, code):
    t = TEXT[code]
    cats = data["categories"]
    toc_anchor = slug(t["toc"])
    heads = ["%s %s" % (c["icon"], c["name"]) for c in cats]

    lines = [t["switch"], "", "### %s 🚀" % data["title"], data["description"], "", "---", "", "### %s" % t["toc"]]
    lines += ["- [%s](#%s)  " % (h, slug(h)) for h in heads]
    lines[-1] = lines[-1].rstrip()
    lines += ["", "### %s" % t["others"]]
    others = [t["contributing"], t["support"], t["contact"]]
    lines += ["- [%s](#%s)%s" % (h, slug(h), "  " if i < len(others) - 1 else "") for i, h in enumerate(others)]
    lines += ["", "---", ""]

    for head, cat in zip(heads, cats):
        lines += ["### %s" % head, cat["description"], ""]
        tools = cat["tools"]
        for i, tool in enumerate(tools):
            trailing = "  " if i < len(tools) - 1 else ""
            lines.append("- [%s](%s) — %s%s" % (tool["name"], tool["url"], tool["description"], trailing))
        lines += ["", "[%s](#%s)" % (t["top"], toc_anchor), "", "---", ""]

    lines += ["### %s" % t["contributing"]] + t["contributing_body"] + [""]
    lines += ["### %s" % t["support"]] + t["support_body"] + [""]
    lines += [
        "### %s" % t["contact"],
        "**%s:** Abu Sofian  " % t["author"],
        "**Email:** [abusofian.id@gmail.com](mailto:abusofian.id@gmail.com)  ",
        "**LinkedIn:** [linkedin.com/in/abusofianid](https://www.linkedin.com/in/abusofianid) ",
        "",
        "[%s](#%s)" % (t["top"], toc_anchor),
        "",
        "---",
        "",
        t["footer"],
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Build the README files from data/tools.*.json.")
    parser.add_argument("--check", action="store_true", help="do not write; exit 1 if a README is out of date")
    args = parser.parse_args()

    data = {code: load(paths[0]) for code, paths in TARGETS.items()}
    problems = validate(data["en"], data["id"])
    if problems:
        print("Data files are not valid:", file=sys.stderr)
        for problem in problems:
            print("  - " + problem, file=sys.stderr)
        return 1

    stale = []
    for code, (_, readme) in TARGETS.items():
        text = build(data[code], code)
        count = sum(len(c["tools"]) for c in data[code]["categories"])
        current = readme.read_text(encoding="utf-8") if readme.exists() else None
        if args.check:
            if current != text:
                stale.append(readme.name)
        else:
            with open(readme, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            print("%s: %d tools in %d categories" % (readme.name, count, len(data[code]["categories"])))

    if stale:
        print("Out of date: %s. Run: python3 scripts/build_readme.py" % ", ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        print("README files are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
