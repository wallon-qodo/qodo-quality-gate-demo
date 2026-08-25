#!/usr/bin/env python3
"""headline_rewrite.py — put plain-English headlines inside Qodo's findings comment.

Qodo's review comment leads each finding with the engine's own technical title --
"Reapply failure ignored", "gh_json() silently drops errors". That title is precise
and it is the right thing for the author of the diff. It is the wrong thing for the
reviewer scanning sixteen findings, and it is unreadable for anyone who did not write
the file. This script rewrites the lead line of every finding as an outcome headline
and adds a consequence-first "what this means" block, in place, inside Qodo's comment.

Nothing the engine said is discarded. The engine's title is demoted, not deleted --
it stays under the headline, and the engine's Description / Code / Evidence blocks are
left byte-for-byte alone. A plain-English layer an engineer cannot audit against the
engine's own words is worse than the jargon it replaced.

The wording comes from the plain-english-findings engine, imported rather than copied,
so the report and the PR comment cannot drift apart (--engine-dir).

Methodology is the churn advisory's, and so are its two consequences:

  * There is no product-supported way to feed an external signal into a Qodo review,
    so this edits the posted comment through the GitHub API.
  * Qodo owns that comment and rewrites it when it re-reviews, which reverts the
    headlines. This waits for the review to land, rewrites, then keeps watching and
    re-rewrites the fresh body until it has survived --stable seconds.

  headline_rewrite.py --repo o/r --pr 14
  headline_rewrite.py --body-file body.md --out new.md --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import textwrap
import time

MARKER = "<!-- plain-english-headlines v1 -->"
PE_SUMMARY = "><summary>What this means</summary>"
REVIEW_SIGNATURE = "Code Review by Qodo"

SUMMARY_RE = re.compile(r"^<summary>\s+(\d+)\.\s+(.*?)</summary>\s*$")
BADGE_RE = re.compile(r"img\.shields\.io/badge/([A-Za-z]+)-")
TAG_RE = re.compile(r"<code>(.*?)</code>")
STRIP_TAGS_RE = re.compile(r"</?(?:s|b|i|ins|strong|em|del)>")

# The finding-type tag, as opposed to the domain / status / CWE tags beside it.
KINDS = ("Bug", "Rule violation", "Skill insight", "Security issue", "Team insight",
         "Compliance", "Ticket compliance")

DEFAULT_ENGINE_DIR = os.path.expanduser(
    os.environ.get("PLAIN_ENGLISH_DIR",
                   "~/.claude/skills/plain-english-findings"))


# --------------------------------------------------------------------------- parse

def plain(text: str) -> str:
    """The human words in a fragment of Qodo's markup, with the markup removed."""
    return " ".join(html.unescape(STRIP_TAGS_RE.sub("", text or "")).split())


def split_summary(inner: str):
    """'<s>Title</s> <code>tag</code>...' -> (title_html, tags_html).

    The first ` <code>` is the boundary: Qodo puts every tag after the title and
    never puts a <code> inside it.
    """
    cut = inner.find(" <code>")
    if cut == -1:
        return inner.rstrip(), ""
    return inner[:cut].rstrip(), inner[cut:].strip()


def read_description(lines, start: int, stop: int) -> str:
    """The Description <pre> block of the finding whose summary is at `start`."""
    i = start
    while i < stop and ">" + "<summary>Description</summary>" not in lines[i]:
        i += 1
    while i < stop and lines[i].strip() != "><pre>":
        i += 1
    out = []
    i += 1
    while i < stop and lines[i].strip() != "></pre>":
        out.append(plain(lines[i].lstrip(">")))
        i += 1
    return " ".join(" ".join(out).split())


def parse_findings(body: str):
    """Every finding in a Qodo review comment, in the order it is rendered."""
    lines = body.split("\n")
    heads = [(n, m) for n, m in
             ((n, SUMMARY_RE.match(ln)) for n, ln in enumerate(lines)) if m]
    findings = []
    for pos, (line_no, m) in enumerate(heads):
        stop = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
        title_html, tags_html = split_summary(m.group(2))
        tags = [plain(t) for t in TAG_RE.findall(tags_html)]
        kinds = [t for t in tags if any(k.lower() in t.lower() for k in KINDS)]
        # The severity band this finding is rendered under: the nearest badge above it.
        level = "Unknown"
        for prev in range(line_no, -1, -1):
            b = BADGE_RE.search(lines[prev])
            if b:
                level = b.group(1)
                break
        title = plain(title_html)
        desc = read_description(lines, line_no, stop)
        findings.append({
            "id": hashlib.sha1(
                (title + "|" + desc[:300]).encode("utf-8")).hexdigest()[:12],
            "num": int(m.group(1)),
            "line": line_no,
            "stop": stop,
            "title": title,
            "title_html": title_html,
            "tags_html": tags_html,
            "resolved": title_html.strip().startswith("<s>"),
            "category": kinds[0] if kinds else (tags[0] if tags else "Finding"),
            "level": level,
            "description": desc,
        })
    return findings


# ------------------------------------------------------------------------- rewrite

def sowhat_block(sowhat: str, engine_title: str) -> list:
    """The quoted details block that carries the so-what and the demoted title."""
    wrapped = textwrap.wrap(sowhat, 96) or [sowhat]
    out = ["> <details open>",
           "><summary>What this means</summary>",
           "><br/>",
           ">",
           "><pre>"]
    out += [">" + html.escape(w, quote=False) for w in wrapped]
    out += ["></pre>",
            ">",
            "><code>Qodo's title: " + html.escape(engine_title, quote=False) +
            "</code>",
            "></details>",
            ""]
    return out


def rewrite_body(body: str, headlines: dict, sowhats: dict) -> tuple:
    """Return (new_body, rewritten_count). A finding with no headline is untouched.

    Idempotent: run twice and the second run returns the first run's output. That
    matters because the watch loop re-reads whatever is on the PR right now, and a
    body it has already rewritten must not grow a second copy of every block.
    """
    lines = [ln for ln in body.split("\n") if ln.strip() != MARKER]
    findings = parse_findings("\n".join(lines))
    done = 0
    # Back to front, so an insertion never moves a line number still to be used.
    for f in reversed(findings):
        headline = headlines.get(f["id"])
        if not headline:
            continue
        if any(PE_SUMMARY in ln for ln in lines[f["line"]:f["stop"]]):
            continue  # already carries a plain-English block -- leave it alone
        lead = html.escape(headline, quote=False)
        if f["resolved"]:
            lead = "<s>" + lead + "</s>"
        tail = (" " + f["tags_html"]) if f["tags_html"] else ""
        lines[f["line"]] = ("<summary>  %d.  %s%s</summary>"
                           % (f["num"], lead, tail))
        sw = sowhats.get(f["id"])
        if sw:
            at = f["line"]
            while at < f["stop"] and lines[at].strip() != "> <details open>":
                at += 1
            if at < f["stop"]:
                lines[at:at] = sowhat_block(sw, f["title"])
        done += 1
    new = "\n".join(lines).rstrip() + "\n\n" + MARKER + "\n"
    return new, done


# -------------------------------------------------------------------------- model

def load_engine(engine_dir: str):
    """The plain-english-findings engine, or None if it is not provisioned here."""
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    try:
        import engine  # noqa: PLC0415 -- optional dependency, resolved at runtime
        return engine
    except ImportError as exc:
        print("headline_rewrite: no translation engine at " + engine_dir +
              " (" + str(exc)[:80] + ")", file=sys.stderr)
        return None


def translate(findings, engine, cache_path: str, force: bool = False) -> tuple:
    """(headlines, sowhats) by finding id. Cached, so a re-apply costs nothing."""
    cache = {"headline": {}, "sowhat": {}}
    if os.path.exists(cache_path) and not force:
        try:
            with open(cache_path) as fh:
                cache.update(json.load(fh))
        except (OSError, ValueError):
            pass

    def save():
        try:
            with open(cache_path, "w") as fh:
                json.dump(cache, fh, indent=1, sort_keys=True)
        except OSError as exc:
            print("headline_rewrite: cannot write cache -- " + str(exc)[:120],
                  file=sys.stderr)

    todo = [f for f in findings if f["id"] not in cache["headline"]]
    if todo:
        engine.generate(todo, "headline", cache["headline"],
                        on_batch=lambda *a: save())
        save()
    for f in findings:
        f["headline"] = cache["headline"].get(f["id"], f["title"])
    todo = [f for f in findings if f["id"] not in cache["sowhat"]]
    if todo:
        engine.generate(todo, "sowhat", cache["sowhat"], on_batch=lambda *a: save())
        save()
    # A so-what that just restates its own headline wastes the lead line.
    echo = [f for f in findings
            if f["id"] in cache["sowhat"]
            and engine.echoes_headline(f["headline"], cache["sowhat"][f["id"]])]
    if echo:
        for f in echo:
            cache["sowhat"].pop(f["id"], None)
        engine.generate(echo, "sowhat", cache["sowhat"], on_batch=lambda *a: save())
        save()
    return cache["headline"], cache["sowhat"]


# --------------------------------------------------------------------------- forge

def gh_json(*args: str):
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True,
                         timeout=120)
    if out.returncode != 0:
        print("headline_rewrite: gh api failed -- " + out.stderr.strip()[:200],
              file=sys.stderr)
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        print("headline_rewrite: gh api returned no JSON object", file=sys.stderr)
        return None


def find_review_comment(repo: str, pr: str):
    """The most recent Qodo findings comment, or None."""
    data = gh_json("repos/" + repo + "/issues/" + pr + "/comments", "--paginate")
    hits = [c for c in (data or []) if REVIEW_SIGNATURE in (c.get("body") or "")]
    return hits[-1] if hits else None


def patch_comment(repo: str, comment_id: int, text: str, tmp: str) -> bool:
    with open(tmp, "w") as fh:
        fh.write(text)
    out = subprocess.run(
        ["gh", "api", "-X", "PATCH",
         "repos/" + repo + "/issues/comments/" + str(comment_id),
         "-F", "body=@" + tmp],
        capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        print("headline_rewrite: cannot edit comment " + str(comment_id) + " -- " +
              out.stderr.strip()[:300], file=sys.stderr)
        return False
    return True


def apply_once(repo: str, pr: str, engine, cache: str, tmp: str,
               force: bool = False) -> str:
    """'applied' | 'already' | 'no-review' | 'no-findings' | 'no-headlines' | 'failed'."""
    review = find_review_comment(repo, pr)
    if not review:
        return "no-review"
    body = review.get("body") or ""
    if MARKER in body and not force:
        return "already"
    findings = parse_findings(body)
    if not findings:
        return "no-findings"
    headlines, sowhats = translate(findings, engine, cache)
    new, done = rewrite_body(body, headlines, sowhats)
    if not done:
        # The model was unreachable. Qodo's own wording is still correct -- leave it.
        return "no-headlines"

    # Translation can take long enough for Qodo to refresh this comment. Do not
    # PATCH a whole stale body: that would restore the old review and lose its
    # newly posted findings. Re-read immediately before writing and retry on the
    # next watch iteration if the comment changed (or was replaced).
    current = find_review_comment(repo, pr)
    if (not current or current.get("id") != review.get("id") or
            (current.get("body") or "") != body):
        return "failed"
    return "applied" if patch_comment(repo, int(review["id"]), new, tmp) else "failed"


# ---------------------------------------------------------------------------- main

def offline(a) -> int:
    with open(a.body_file) as fh:
        body = fh.read()
    findings = parse_findings(body)
    print("headline_rewrite: %d findings parsed from %s"
          % (len(findings), a.body_file))
    for f in findings:
        print("  %2d. [%-9s %-15s] %s" % (f["num"], f["level"],
                                          f["category"][:15], f["title"]))
        if not f["description"]:
            print("      !! no description parsed -- the so-what would be thin")
    if a.dry_run:
        return 0
    engine = load_engine(a.engine_dir)
    if engine is None:
        return 1
    headlines, sowhats = translate(findings, engine, a.cache, a.force)
    new, done = rewrite_body(body, headlines, sowhats)
    print("headline_rewrite: rewrote %d/%d findings" % (done, len(findings)))
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(new)
        print("headline_rewrite: wrote " + a.out)
    else:
        sys.stdout.write(new)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--pr")
    ap.add_argument("--body-file", help="rewrite a saved comment body, no API calls")
    ap.add_argument("--out", help="with --body-file: write the rewritten body here")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and report only; calls no model and no API")
    ap.add_argument("--engine-dir", default=DEFAULT_ENGINE_DIR)
    ap.add_argument("--cache", default="headline-cache.json")
    ap.add_argument("--force", action="store_true",
                    help="re-translate, and rewrite even if the marker is present")
    ap.add_argument("--wait", type=int, default=300,
                    help="seconds to wait for the Qodo review to be posted")
    ap.add_argument("--watch", type=int, default=600,
                    help="seconds to keep re-applying after a Qodo rewrite")
    ap.add_argument("--stable", type=int, default=180,
                    help="stop once the rewrite has survived this long")
    ap.add_argument("--interval", type=int, default=30,
                    help="seconds between checks while watching")
    ap.add_argument("--tmp", default="headline-payload.md")
    a = ap.parse_args()

    if a.body_file:
        sys.exit(offline(a))
    if not (a.repo and a.pr):
        ap.error("--repo and --pr are required unless --body-file is given")

    engine = load_engine(a.engine_dir)
    if engine is None:
        # Advisory, never blocking: Qodo's own headlines are still there and correct.
        print("headline_rewrite: nothing to do, leaving the review as Qodo wrote it")
        sys.exit(0)

    deadline = time.monotonic() + a.wait
    while True:
        state = apply_once(a.repo, a.pr, engine, a.cache, a.tmp, a.force)
        if state != "no-review" or time.monotonic() >= deadline:
            break
        print("headline_rewrite: no findings comment yet, waiting", flush=True)
        time.sleep(15)

    print("headline_rewrite: " + state, flush=True)
    if state not in ("applied", "already"):
        sys.exit(0)

    # Qodo rewrites its comment on every re-review, which reverts the headlines.
    # Watch for the marker going missing and re-rewrite the fresh body.
    watch_until = time.monotonic() + a.watch
    survived_since = time.monotonic()
    while time.monotonic() < watch_until:
        time.sleep(a.interval)
        review = find_review_comment(a.repo, a.pr)
        if review is None:
            continue
        if MARKER in (review.get("body") or ""):
            if time.monotonic() - survived_since >= a.stable:
                print("headline_rewrite: headlines stable, done")
                return
            continue
        print("headline_rewrite: headlines were reverted, re-applying", flush=True)
        if apply_once(a.repo, a.pr, engine, a.cache, a.tmp) != "applied":
            print("headline_rewrite: re-apply failed, will retry next interval",
                  flush=True)
        survived_since = time.monotonic()

    print("headline_rewrite: watch window ended; a later re-review reverts the "
          "headlines until the next push re-applies them")


if __name__ == "__main__":
    main()
