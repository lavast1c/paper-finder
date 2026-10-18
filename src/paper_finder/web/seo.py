"""Public, crawlable pages: the part of the site search engines can index.

The app itself (``/`` and ``/search``) is a JS page behind the email-code login,
so a crawler only ever sees its sign-in box. These pages are plain server-rendered
HTML -- one per subject, per topic (paginated) and per question paper -- built
from the anon-callable ``public_*`` RPCs (migration 0021) with the publishable
key, so they need no login and no JavaScript to read. They reuse the app's
header/footer markup and ``style.css`` so they look like the rest of the site.

Pure stdlib + ``paper_finder.topics`` / ``config`` -- importable on Vercel, where
PyMuPDF is deliberately absent. The Supabase call is an injected ``Reader`` so
tests run without a network.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

from paper_finder.config import SESSIONS, SITE_URL
from paper_finder.topics import BY_CODE, TAXONOMIES, Taxonomy, Topic

# ``reader(rpc_name, params) -> rows`` -- one PostgREST RPC call.
Reader = Callable[[str, dict], list[dict]]

PAGE_SIZE = 50  # matches public_topic_questions' server-side cap
CACHE_SECONDS = 3600  # in-process cache of the paper list / topic counts
AUTHOR = "Vihaan Talluri"
CONTACT_EMAIL = "vihaantalluriwork@gmail.com"
SITE_NAME = "Paper Analyser"
OG_IMAGE = f"{SITE_URL}/static/og-image.png"

# Byte-identical to the pre-paint theme bootstrap in topics.html/index.html, so
# app.py's CSP hashes it the same way (it hashes this constant explicitly).
THEME_SCRIPT = """
    // Apply a saved theme choice before first paint (no flash). Absent =
    // time-of-day default: light 06:00-18:59, dark otherwise (not OS).
    try {
      var t = localStorage.getItem("paper-finder.theme");
      if (t === "dark" || t === "light") {
        document.documentElement.dataset.theme = t;
      } else {
        var h = new Date().getHours();
        document.documentElement.dataset.theme = h >= 6 && h < 19 ? "light" : "dark";
      }
    } catch (e) {
      document.documentElement.dataset.theme = "light";
    }
  """

_PAPER_STEM = re.compile(r"^\d{4}_[smw]\d{2}_qp_\d{2}$")
# Break a flattened structured question before its part labels: " (a) " / " (ii) ".
_PART_LABEL = re.compile(r" (?=\((?:[a-h]|i{1,3}|iv|vi{0,3}|ix|x)\) )")


def supabase_reader(url: str, key: str, *, timeout: float = 10) -> Reader:
    """A :data:`Reader` that POSTs to ``{url}/rest/v1/rpc/<name>`` as anon."""

    def read(name: str, params: dict) -> list[dict]:
        request = urllib.request.Request(
            f"{url}/rest/v1/rpc/{name}",
            data=json.dumps(params).encode(),
            headers={"apikey": key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    return read


def slugify(text: str) -> str:
    """``"Probability & Statistics 1"`` -> ``"probability-and-statistics-1"``."""
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def subject_slug(tax: Taxonomy) -> str:
    return f"{tax.subject_code}-{slugify(tax.subject_name)}"  # 9709-pure-mathematics-1


def topic_slug(topic: Topic) -> str:
    return f"{topic.code}-{slugify(topic.name)}"  # s07-waves


def subject_url(tax: Taxonomy) -> str:
    return f"/cie/{subject_slug(tax)}/"


def topic_url(tax: Taxonomy, topic: Topic, page: int = 1) -> str:
    base = f"{subject_url(tax)}{topic_slug(topic)}/"
    return base if page <= 1 else f"{base}?page={page}"


def paper_stem(filename: str) -> str:
    return filename[:-4] if filename.endswith(".pdf") else filename


def paper_url(filename: str) -> str:
    return f"/papers/{paper_stem(filename)}"


def taxonomy_of_topic(code: str) -> Taxonomy | None:
    for tax in TAXONOMIES:
        if any(t.code == code for t in tax.topics):
            return tax
    return None


def paper_label(row: dict) -> str:
    """``"May/June 2024 Paper 12"`` -- CIE's own paper+variant number."""
    session = SESSIONS.get(row["session"], row["session"])
    return f"{session} {row['year']} Paper {row['paper']}{row['variant']}"


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _n(count: int) -> str:
    return f"{count:,}"


def _plural(count: int, word: str) -> str:
    return f"{_n(count)} {word}{'' if count == 1 else 's'}"


def _json_ld(data: dict) -> str:
    # "</" can't appear inside a <script> block, even a data block.
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def _breadcrumb_ld(crumbs: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": SITE_URL + href}
            for i, (name, href) in enumerate(crumbs, start=1)
        ],
    }


def website_ld() -> dict:
    """``WebSite`` + its ``Person`` author -- on the home and About pages."""
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": f"{SITE_URL}/#website",
                "url": f"{SITE_URL}/",
                "name": SITE_NAME,
                "description": (
                    "A free index of Cambridge International AS & A Level past paper "
                    "questions, sorted by syllabus topic and difficulty, with mark-scheme "
                    "answers."
                ),
                "inLanguage": "en",
                "author": {"@id": f"{SITE_URL}/about#author"},
            },
            {
                "@type": "Person",
                "@id": f"{SITE_URL}/about#author",
                "name": AUTHOR,
                "email": f"mailto:{CONTACT_EMAIL}",
                "url": f"{SITE_URL}/about",
            },
        ],
    }


@dataclass(frozen=True)
class Page:
    status: int
    html: str


_HEADER_CHROME = """  <canvas id="bg-dither" aria-hidden="true"></canvas>
  <svg class="glass-defs" aria-hidden="true" focusable="false">
    <defs>
      <filter id="glass-refraction" x="-25%" y="-25%" width="150%" height="150%"
              color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.006 0.011" numOctaves="2"
                      seed="17" result="noise"/>
        <feGaussianBlur in="noise" stdDeviation="1.1" result="soft"/>
        <feDisplacementMap in="SourceGraphic" in2="soft" scale="28"
                           xChannelSelector="R" yChannelSelector="G"/>
      </filter>
    </defs>
  </svg>
  <header>
    <div class="bar-inner">
      <p class="brand"><a href="/">Paper Analyser</a></p>
      <button type="button" id="theme-toggle" class="theme-toggle"
              aria-label="Switch to light mode" aria-pressed="false">
        <svg class="ic-sun" viewBox="0 0 24 24" width="20" height="20" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4"/>
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2
                   M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
        </svg>
        <svg class="ic-moon" viewBox="0 0 24 24" width="20" height="20" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round"
             stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
        </svg>
        <span id="theme-toggle-label">Dark mode</span>
      </button>
      <p class="corpus"></p>
      <nav class="topnav" aria-label="Site">
        <a href="/">Browse by topic</a>
        <a href="/search">Search</a>
      </nav>
    </div>
  </header>
"""

FOOTER_LINKS = (
    ("/cie/", "All subjects"),
    ("/about", "About"),
    ("/privacy", "Privacy"),
    ("/terms", "Terms"),
    ("/cookies", "Cookies"),
    ("/accessibility", "Accessibility"),
)


def footer_nav(current: str | None = None) -> str:
    current_attr = ' aria-current="page"'
    links = " ".join(
        f'<a href="{href}"{current_attr if href == current else ""}>{label}</a>'
        for href, label in FOOTER_LINKS
    )
    return f'<nav class="legal-nav" aria-label="Site pages">{links}</nav>'


def page_shell(
    *,
    path: str,
    title: str,
    description: str,
    body: str,
    json_ld: tuple[dict, ...] | list[dict] = (),
    head_extra: str = "",
    status: int = 200,
    index: bool = True,
) -> Page:
    """A full HTML page in the site's chrome. ``path`` is the canonical path."""
    canonical = SITE_URL + path
    robots = "" if index else '\n  <meta name="robots" content="noindex">'
    ld = "".join(f"\n  {_json_ld(d)}" for d in json_ld)
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description)}">{robots}
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:image" content="{OG_IMAGE}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">{head_extra}
  <script>{THEME_SCRIPT}</script>
  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
  <link rel="stylesheet" href="/static/style.css">{ld}
</head>
<body>
{_HEADER_CHROME}
  <main id="main">
    <article class="legal pub">
{body}
    </article>
  </main>

  <footer>
    <p class="footer-note">
      Paper Analyser is an independent index to help students organize revision
      papers. It is not affiliated with, endorsed by, or sponsored by Cambridge
      University Press &amp; Assessment or any other examination board.
    </p>
    <p class="footer-note">
      Questions and mark-scheme answers are &copy; Cambridge University Press &amp;
      Assessment, reproduced for students&rsquo; study and reference. To request
      removal of any material, email
      <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.
    </p>
    {footer_nav(path)}
  </footer>

  <script src="/static/dither.js" defer></script>
  <script src="/static/common.js" defer></script>
</body>
</html>
"""
    return Page(status, doc)


def _crumbs_html(crumbs: list[tuple[str, str]]) -> str:
    items = []
    for i, (name, href) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            items.append(f'<li><a href="{_e(href)}" aria-current="page">{_e(name)}</a></li>')
        else:
            items.append(f'<li><a href="{_e(href)}">{_e(name)}</a></li>')
    return f'      <nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(items)}</ol></nav>'


def _app_link(params: dict, label: str) -> str:
    return f'<p class="pub-cta"><a href="/?{_e(urlencode(params))}">{_e(label)}</a></p>'


def _question_text(text: str, is_mcq: bool) -> str:
    if not is_mcq:
        text = _PART_LABEL.sub("\n", text)
    return _e(text.strip())


def _meta_line(row: dict) -> str:
    bits = []
    if row.get("marks"):
        bits.append(_plural(row["marks"], "mark"))
    if row.get("difficulty"):
        bits.append(f"Difficulty {row['difficulty']}/5")
    bits.append("Multiple choice" if row.get("is_mcq") else "Written answer")
    return f'<p class="pub-meta">{" · ".join(_e(b) for b in bits)}</p>'


def _answer_html(row: dict) -> str:
    answer = (row.get("answer_text") or "").strip()
    if not answer:
        return '<p class="pub-meta">No published answer for this question.</p>'
    if row.get("is_mcq"):
        return f'<p class="pub-answer"><strong>Answer: {_e(answer)}</strong></p>'
    return (
        '<details class="pub-answer"><summary>Mark scheme answer</summary>'
        f'<div class="pub-text">{_e(answer)}</div></details>'
    )


class PublicSite:
    """Renders the public pages from a :data:`Reader`.

    The paper list and topic counts change only on ``publish``, so they're held
    in-process for :data:`CACHE_SECONDS`; Vercel's CDN caches the rendered pages
    on top of that (see the ``Cache-Control`` set in ``app.py``).
    """

    def __init__(self, reader: Reader, *, clock: Callable[[], float] = time.monotonic):
        self._read = reader
        self._clock = clock
        self._cache: dict[str, tuple[float, object]] = {}

    def _cached(self, key: str, load: Callable[[], object]):
        hit = self._cache.get(key)
        now = self._clock()
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
        value = load()
        self._cache[key] = (now, value)
        return value

    def papers(self) -> list[dict]:
        return self._cached("papers", lambda: self._read("public_papers", {}))

    def topic_counts(self) -> dict[str, int]:
        return self._cached(
            "topic_counts",
            lambda: {r["code"]: r["question_count"] for r in self._read("public_topic_counts", {})},
        )

    def subject_papers(self, tax: Taxonomy) -> list[dict]:
        return [p for p in self.papers() if p["subject_name"] == tax.subject_name]

    @staticmethod
    def find_subject(slug: str) -> Taxonomy | None:
        return next((t for t in TAXONOMIES if subject_slug(t) == slug), None)

    @staticmethod
    def find_topic(tax: Taxonomy, slug: str) -> Topic | None:
        return next((t for t in tax.topics if topic_slug(t) == slug), None)

    # --- pages ---------------------------------------------------------------

    def hub(self) -> Page:
        papers = self.papers()
        total_q = sum(p["question_count"] for p in papers)
        years = [p["year"] for p in papers] or [0]
        crumbs = [("Home", "/"), ("All subjects", "/cie/")]
        rows = []
        for tax in TAXONOMIES:
            sp = self.subject_papers(tax)
            q = sum(p["question_count"] for p in sp)
            rows.append(
                f'<li><a href="{subject_url(tax)}">{_e(tax.subject_name)} '
                f"({tax.subject_code})</a> "
                f'<span class="pub-meta">{_plural(q, "question")} · '
                f"{_plural(len(sp), 'paper')} · {_plural(len(tax.topics), 'topic')}</span></li>"
            )
        faq = [
            (
                "What is Paper Analyser?",
                f"A free index of {_n(total_q)} Cambridge International AS & A Level "
                f"past paper questions from {_n(len(papers))} papers ({min(years)}-"
                f"{max(years)}). Every question is sorted into its syllabus topic, rated "
                "for difficulty and paired with its mark-scheme answer.",
            ),
            (
                "Which subjects are covered?",
                "Physics (9702), Chemistry (9701), Biology (9700), Economics (9708), "
                "Computer Science (9618), Mathematics (9709: Pure 1, Pure 3, Mechanics, "
                "Probability & Statistics 1 and 2) and Further Mathematics (9231: all four "
                "papers).",
            ),
            (
                "How do I find which past paper a question came from?",
                "Type a few words of the question into the search page. It returns the "
                "exact paper (subject, year, session, paper and variant), the question "
                "number and the answer.",
            ),
            (
                "How are the difficulty ratings decided?",
                "Each question was read and rated from 1 (easiest) to 5 (hardest) relative "
                "to other questions in the same subject. Multiple-choice and written papers "
                "are rated on separate scales.",
            ),
            (
                "Is Paper Analyser free?",
                "Yes. These public pages need no account. Searching and the flashcard "
                "browser need a free sign-in with an emailed code.",
            ),
            (
                "Is this an official Cambridge website?",
                "No. Paper Analyser is an independent student project by "
                f"{AUTHOR} and is not affiliated with Cambridge University Press & "
                "Assessment.",
            ),
        ]
        faq_html = "".join(f"<h3>{_e(q)}</h3><p>{_e(a)}</p>" for q, a in faq)
        body = f"""{_crumbs_html(crumbs)}
      <h1>Cambridge AS &amp; A Level past paper questions by topic</h1>
      <p class="pub-lead">Paper Analyser is a free index of {_n(total_q)} Cambridge
        International AS &amp; A Level past paper questions from {_n(len(papers))} papers
        ({min(years)}&ndash;{max(years)}), sorted by syllabus topic and difficulty, each with
        its mark-scheme answer. Pick a subject to browse its topics and papers.</p>
      <h2>Subjects</h2>
      <ul class="pub-list">{"".join(rows)}</ul>
      {_app_link({}, "Open the flashcard browser and question search")}
      <h2>Frequently asked questions</h2>
      {faq_html}"""
        faq_ld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {"@type": "Answer", "text": a},
                }
                for q, a in faq
            ],
        }
        return page_shell(
            path="/cie/",
            title="Cambridge AS & A Level Past Paper Questions by Topic",
            description=(
                f"{_n(total_q)} Cambridge International AS & A Level past paper questions "
                "sorted by topic and difficulty, with mark-scheme answers. Physics, "
                "Chemistry, Biology, Maths, Economics, Computer Science."
            ),
            body=body,
            json_ld=[_breadcrumb_ld(crumbs), faq_ld],
        )

    def subject(self, slug: str) -> Page:
        tax = self.find_subject(slug)
        if tax is None:
            return not_found()
        papers = self.subject_papers(tax)
        counts = self.topic_counts()
        total_q = sum(p["question_count"] for p in papers)
        years = [p["year"] for p in papers] or [0]
        crumbs = [("Home", "/"), ("All subjects", "/cie/"), (tax.subject_name, subject_url(tax))]
        topics = "".join(
            f'<li><a href="{topic_url(tax, t)}">{t.number}. {_e(t.name)}</a> '
            f'<span class="pub-meta">{_plural(counts.get(t.code, 0), "question")}</span></li>'
            for t in tax.topics
        )
        by_year: dict[int, list[dict]] = {}
        for p in papers:
            by_year.setdefault(p["year"], []).append(p)
        paper_blocks = "".join(
            f'<h3>{year}</h3><ul class="pub-cols">'
            + "".join(
                f'<li><a href="{paper_url(p["filename"])}">{_e(paper_label(p))}</a></li>'
                for p in rows
            )
            + "</ul>"
            for year, rows in sorted(by_year.items(), reverse=True)
        )
        name = f"{tax.subject_name} ({tax.subject_code})"
        body = f"""{_crumbs_html(crumbs)}
      <h1>Cambridge {_e(name)} past paper questions by topic</h1>
      <p class="pub-lead">{_n(total_q)} Cambridge International AS &amp; A Level
        {_e(name)} past paper questions from {_n(len(papers))} papers
        ({min(years)}&ndash;{max(years)}), each with its mark-scheme answer, grouped into
        {len(tax.topics)} syllabus topics.</p>
      <h2>Topics</h2>
      <ul class="pub-list">{topics}</ul>
      {_app_link({"subject": tax.subject_name}, f"Practise {tax.subject_name} as flashcards")}
      <h2>Past papers</h2>
      {paper_blocks}"""
        return page_shell(
            path=subject_url(tax),
            title=f"{tax.subject_name} {tax.subject_code} Past Paper Questions by Topic",
            description=(
                f"{_n(total_q)} Cambridge {name} past paper questions from "
                f"{min(years)}-{max(years)}, sorted into {len(tax.topics)} topics with "
                "mark-scheme answers and difficulty ratings."
            ),
            body=body,
            json_ld=[_breadcrumb_ld(crumbs)],
        )

    def topic(self, subject_slug_: str, slug: str, page: int = 1) -> Page:
        tax = self.find_subject(subject_slug_)
        topic = self.find_topic(tax, slug) if tax else None
        if topic is None or page < 1:
            return not_found()
        rows = self._read(
            "public_topic_questions",
            {"code": topic.code, "max_results": PAGE_SIZE, "skip": (page - 1) * PAGE_SIZE},
        )
        total = rows[0]["total_count"] if rows else self.topic_counts().get(topic.code, 0)
        pages = max(1, -(-total // PAGE_SIZE))
        if page > pages:
            return not_found()
        crumbs = [
            ("Home", "/"),
            ("All subjects", "/cie/"),
            (tax.subject_name, subject_url(tax)),
            (topic.name, topic_url(tax, topic)),
        ]
        items = "".join(
            f"""<section class="pub-q">
        <h2><a href="{paper_url(r["filename"])}">{_e(paper_label(r))}</a>,
          Question {r["question_number"]}</h2>
        {_meta_line(r)}
        <div class="pub-text">{_question_text(r["question_text"], r.get("is_mcq"))}</div>
        {_answer_html(r)}
      </section>"""
            for r in rows
        )
        subsections = "".join(f"<li>{_e(s)}</li>" for s in topic.subsections)
        nav, head = _pager(tax, topic, page, pages)
        suffix = f" (page {page} of {pages})" if pages > 1 else ""
        body = f"""{_crumbs_html(crumbs)}
      <h1>{_e(topic.name)}: {_e(tax.subject_name)} {tax.subject_code} past paper
        questions{_e(suffix)}</h1>
      <p class="pub-lead">{_plural(total, "question")} on {_e(topic.name)} from
        Cambridge International AS &amp; A Level {_e(tax.subject_name)} past papers, newest
        first, each with its mark-scheme answer and a difficulty rating.</p>
      {f'<ul class="pub-sub">{subsections}</ul>' if subsections else ""}
      {
            _app_link(
                {"subject": tax.subject_name, "topics": topic.code},
                "Practise this topic as flashcards",
            )
        }
      {items}
      {nav}"""
        title = f"{topic.name} – {tax.subject_name} {tax.subject_code} Past Paper Questions"
        if page > 1:
            title += f" (Page {page})"
        return page_shell(
            path=topic_url(tax, topic, page),
            title=title,
            description=(
                f"{_plural(total, 'past paper question')} on {topic.name} for Cambridge "
                f"{tax.subject_name} ({tax.subject_code}), with mark-scheme answers and "
                "difficulty ratings."
            ),
            body=body,
            json_ld=[_breadcrumb_ld(crumbs)],
            head_extra=head,
        )

    def paper(self, stem: str) -> Page:
        if not _PAPER_STEM.match(stem):
            return not_found()
        filename = f"{stem}.pdf"
        meta = next((p for p in self.papers() if p["filename"] == filename), None)
        tax = taxonomy_for_paper(meta) if meta else None
        if meta is None or tax is None:
            return not_found()
        rows = self._read("public_paper_questions", {"fname": filename})
        label = paper_label(meta)
        crumbs = [
            ("Home", "/"),
            ("All subjects", "/cie/"),
            (tax.subject_name, subject_url(tax)),
            (label, paper_url(filename)),
        ]
        items = []
        for r in rows:
            topics = [BY_CODE[c] for c in (r.get("topic_codes") or []) if c in BY_CODE]
            topic_links = ", ".join(
                f'<a href="{topic_url(tax, t)}">{_e(t.name)}</a>'
                for t in topics
                if taxonomy_of_topic(t.code) is tax
            )
            items.append(
                f"""<section class="pub-q">
        <h2>Question {r["question_number"]}</h2>
        {_meta_line(r)}
        {f'<p class="pub-meta">Topic: {topic_links}</p>' if topic_links else ""}
        <div class="pub-text">{_question_text(r["question_text"], r.get("is_mcq"))}</div>
        {_answer_html(r)}
      </section>"""
            )
        name = f"{tax.subject_name} {tax.subject_code}"
        body = f"""{_crumbs_html(crumbs)}
      <h1>Cambridge {_e(name)} {_e(label)}: questions and answers</h1>
      <p class="pub-lead">All {_plural(len(rows), "question")} from the Cambridge
        International AS &amp; A Level {_e(name)} {_e(label)} question paper
        (<code>{_e(stem)}</code>), each with its mark-scheme answer, topic and difficulty
        rating.</p>
      {
            _app_link(
                {"subject": tax.subject_name, "year": meta["year"], "season": meta["session"]},
                "Practise this session as flashcards",
            )
        }
      {"".join(items)}"""
        return page_shell(
            path=paper_url(filename),
            title=f"{tax.subject_code} {label} ({stem}) – {tax.subject_name} Q&A",
            description=(
                f"Cambridge {name} {label} ({stem}): all {_plural(len(rows), 'question')} "
                "with mark-scheme answers, topics and difficulty ratings."
            ),
            body=body,
            json_ld=[_breadcrumb_ld(crumbs)],
        )

    # --- machine-readable files ---------------------------------------------

    def sitemap(self) -> str:
        counts = self.topic_counts()
        paths = ["/", "/search", "/cie/", "/about", *(h for h, _ in FOOTER_LINKS[2:])]
        for tax in TAXONOMIES:
            paths.append(subject_url(tax))
            for t in tax.topics:
                pages = max(1, -(-counts.get(t.code, 0) // PAGE_SIZE))
                paths.extend(topic_url(tax, t, n) for n in range(1, pages + 1))
        paths.extend(paper_url(p["filename"]) for p in self.papers() if p["question_count"])
        urls = "".join(f"<url><loc>{_e(SITE_URL + p)}</loc></url>\n" for p in paths)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}</urlset>\n"
        )


def taxonomy_for_paper(meta: dict) -> Taxonomy | None:
    return next((t for t in TAXONOMIES if t.subject_name == meta["subject_name"]), None)


def _pager(tax: Taxonomy, topic: Topic, page: int, pages: int) -> tuple[str, str]:
    """(visible prev/next nav, <link rel=prev/next> head tags)."""
    if pages <= 1:
        return "", ""
    links, head = [], ""
    if page > 1:
        href = topic_url(tax, topic, page - 1)
        links.append(f'<a href="{_e(href)}" rel="prev">&larr; Newer questions</a>')
        head += f'\n  <link rel="prev" href="{_e(SITE_URL + href)}">'
    links.append(f"<span>Page {page} of {pages}</span>")
    if page < pages:
        href = topic_url(tax, topic, page + 1)
        links.append(f'<a href="{_e(href)}" rel="next">Older questions &rarr;</a>')
        head += f'\n  <link rel="next" href="{_e(SITE_URL + href)}">'
    return f'<nav class="pub-pager" aria-label="Pages">{"".join(links)}</nav>', head


def not_found() -> Page:
    body = f"""{_crumbs_html([("Home", "/"), ("All subjects", "/cie/")])}
      <h1>Page not found</h1>
      <p class="pub-lead">There&rsquo;s no page at this address. Browse
        <a href="/cie/">all subjects</a> or <a href="/">open Paper Analyser</a>.</p>"""
    return page_shell(
        path="/cie/",
        title="Page not found – Paper Analyser",
        description="This page doesn't exist.",
        body=body,
        status=404,
        index=False,
    )


def about() -> Page:
    crumbs = [("Home", "/"), ("About", "/about")]
    body = f"""{_crumbs_html(crumbs)}
      <h1>About Paper Analyser</h1>
      <p class="pub-lead">Paper Analyser is a free study tool for Cambridge International
        AS &amp; A Level students, built and run by {AUTHOR}. It tells you which past paper
        a question came from and lets you practise every past question on a topic, with
        its mark-scheme answer.</p>

      <h2>Who made it</h2>
      <p>I&rsquo;m {AUTHOR}, a student who got tired of hunting through dozens of PDFs
        to find questions on the one topic I needed to revise. Paper Analyser is an
        independent, non-commercial personal project: no ads, no tracking, nothing
        to buy.</p>

      <h2>What it does</h2>
      <ul>
        <li><strong>Find the source of a question.</strong> Type a few words and get the
          exact paper (subject, year, session, paper and variant), the question number
          and the answer.</li>
        <li><strong>Browse by topic.</strong> Every question is sorted into its syllabus
          topic, so you can practise one topic across every year as flashcards.</li>
        <li><strong>Pick your difficulty.</strong> Every question is rated from 1 to 5
          relative to the rest of its subject, so you can warm up or push yourself.</li>
      </ul>

      <h2>How the questions are prepared</h2>
      <p>Questions and answers are extracted from the published question papers and
        mark schemes, then matched up question by question. Written questions were
        labelled with their syllabus topics and difficulty by reading each one;
        multiple-choice papers were topic-labelled by their usual position in the paper,
        which is right most but not all of the time. If you spot a wrong label, email
        me.</p>

      <h2>Coverage</h2>
      <p>Physics (9702), Chemistry (9701), Biology (9700), Economics (9708), Computer
        Science (9618), Mathematics (9709) and Further Mathematics (9231), from 2020
        onward. See <a href="/cie/">all subjects</a> for exact counts.</p>

      <h2>Contact and removal requests</h2>
      <p>Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> with corrections,
        suggestions or questions. Past paper questions and mark schemes are copyright
        Cambridge University Press &amp; Assessment. If you are a rights holder and want
        any material removed, email me and I&rsquo;ll take it down promptly.</p>

      <h2>Not affiliated with Cambridge</h2>
      <p>Paper Analyser is not affiliated with, endorsed by, or sponsored by Cambridge
        University Press &amp; Assessment or any other examination board.</p>"""
    return page_shell(
        path="/about",
        title=f"About Paper Analyser – by {AUTHOR}",
        description=(
            f"Paper Analyser is a free, independent study tool for Cambridge AS & A Level "
            f"past papers, built by {AUTHOR}. How it works, what it covers and how to get "
            "in touch."
        ),
        body=body,
        json_ld=[_breadcrumb_ld(crumbs), website_ld()],
    )


def robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /pdf/\n"
        "Disallow: /figure/\n"
        "\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


def llms_txt() -> str:
    subjects = "\n".join(
        f"- [{tax.subject_name} ({tax.subject_code})]({SITE_URL}{subject_url(tax)}): "
        f"{len(tax.topics)} syllabus topics, every past paper question with its answer"
        for tax in TAXONOMIES
    )
    return f"""# {SITE_NAME}

> A free index of Cambridge International (CIE) AS & A Level past paper questions,
> sorted by syllabus topic and difficulty (1-5), each with its mark-scheme answer.
> Built and run by {AUTHOR} as an independent student project; not affiliated with
> Cambridge University Press & Assessment.

Every subject, topic and question paper has a plain-HTML public page. The
flashcard browser (`/`) and keyword search (`/search`) need a free email sign-in.

## Start here

- [All subjects]({SITE_URL}/cie/): subject list, coverage and FAQ
- [About]({SITE_URL}/about): who runs the site, how questions are labelled and rated
- [Sitemap]({SITE_URL}/sitemap.xml): every subject, topic and paper page

## Subjects

{subjects}

## Contact

{CONTACT_EMAIL}
"""
