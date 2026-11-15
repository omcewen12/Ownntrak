"""OwnnTrak by OSH Ventures: visual identity for the Streamlit app.

The look blends two things. The OSH Ventures palette (espresso, terracotta, clay,
ivory and sage, set in Plus Jakarta Sans with JetBrains Mono for small labels) and
the dark, glowing, frosted glass style of the reference designs. The OwnnTrak
wordmark is set in Comic Sans in pink, as a deliberate contrast.

Anything that comes from outside, such as company and person names from the
register, is HTML escaped before it is placed in markup.
"""
from __future__ import annotations

from html import escape

# OSH Ventures palette, taken from the OSH Ventures platform stylesheet
ESPRESSO = "#68382D"
TERRACOTTA = "#B96545"
CLAY = "#DCA77F"
IVORY = "#F3E8DA"
SAGE = "#849078"

# OwnnTrak additions
PINK = "#FF6FB5"
DEEP = "#150C09"
ROSE = "#C2457F"      # deeper end of the button gradient, keeps white text readable
CORAL = "#FF7A6B"     # high severity
SAGE_LIGHT = "#A3B396"

RAG_COLOURS = {"RED": "#FF6B5E", "AMBER": "#F5B24A", "GREEN": "#8FD694", "NA": "#BFB3A5"}
RAG_SYMBOLS = {"RED": "\u25B2", "AMBER": "\u25C6", "GREEN": "\u25CF", "NA": "\u25CB"}  # shape as well as colour

SEVERITY_COLOURS = {
    "HIGH": CORAL,
    "MEDIUM": CLAY,
    "LOW": SAGE_LIGHT,
    "INFO": "#BFB3A5",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@500&family=Comic+Neue:wght@700&display=swap');

:root {
  --ot-espresso: #68382D;
  --ot-terracotta: #B96545;
  --ot-clay: #DCA77F;
  --ot-ivory: #F3E8DA;
  --ot-sage: #849078;
  --ot-pink: #FF6FB5;
  --ot-deep: #150C09;
  --ot-glass: rgba(243, 232, 218, 0.06);
  --ot-glass-strong: rgba(243, 232, 218, 0.10);
  --ot-border: rgba(243, 232, 218, 0.14);
}

.stApp {
  color: var(--ot-ivory);
  background:
    radial-gradient(620px 440px at 10% 6%, rgba(185, 101, 69, 0.50), transparent 62%),
    radial-gradient(540px 440px at 92% 14%, rgba(255, 111, 181, 0.30), transparent 62%),
    radial-gradient(720px 520px at 72% 96%, rgba(220, 167, 127, 0.22), transparent 62%),
    radial-gradient(520px 420px at 4% 92%, rgba(132, 144, 120, 0.20), transparent 62%),
    var(--ot-deep);
  background-attachment: fixed;
}

.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp button, .stApp input, .stApp textarea {
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
}
.stApp h1, .stApp h2, .stApp h3 { color: var(--ot-ivory); font-weight: 600; letter-spacing: -0.025em; }

[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 1180px; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #2B1612 0%, #170D0A 100%);
  border-right: 1px solid var(--ot-border);
}

/* Wordmark: OwnnTrak in Comic Sans, pink. Comic Neue is the fallback where Comic Sans is not installed. */
.ot-wordmark, .ot-wordmark-sm {
  font-family: "Comic Sans MS", "Comic Sans", "Comic Neue", "Chalkboard SE", "Marker Felt", sans-serif;
  color: var(--ot-pink);
  font-weight: 700;
  line-height: 1;
}
.ot-wordmark { font-size: clamp(2.8rem, 8vw, 4.4rem); letter-spacing: -0.01em; text-shadow: 0 0 30px rgba(255, 111, 181, 0.38); }
.ot-wordmark-sm { font-size: 1.7rem; text-shadow: 0 0 18px rgba(255, 111, 181, 0.35); }

/* "by OSH Ventures" uses the OSH Ventures typography */
.ot-byline, .ot-byline-sm {
  font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
  font-weight: 600;
  color: var(--ot-clay);
  letter-spacing: 0.04em;
}
.ot-byline { font-size: 1.05rem; margin-top: 0.45rem; }
.ot-byline-sm { font-size: 0.78rem; margin-top: 0.25rem; display: block; }
.ot-side-brand { padding: 0.2rem 0 1.1rem 0; border-bottom: 1px solid var(--ot-border); margin-bottom: 1rem; }

.ot-eyebrow {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 0.7rem; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 500;
  color: var(--ot-clay); margin-bottom: 0.9rem;
}

/* Hero */
.ot-hero {
  position: relative; overflow: hidden;
  background: var(--ot-glass); border: 1px solid var(--ot-border); border-radius: 28px;
  padding: 2.2rem 2.4rem; margin-bottom: 1.4rem;
  backdrop-filter: blur(18px) saturate(120%); -webkit-backdrop-filter: blur(18px) saturate(120%);
  box-shadow: 0 18px 50px -24px rgba(0, 0, 0, 0.7);
}
.ot-hero::before {
  content: ""; position: absolute; top: -45%; right: -12%; width: 62%; height: 150%;
  background: radial-gradient(closest-side, rgba(255, 111, 181, 0.50), rgba(185, 101, 69, 0.40) 55%, transparent 78%);
  filter: blur(22px); pointer-events: none;
}
.ot-hero::after {
  content: ""; position: absolute; bottom: -60%; left: -8%; width: 45%; height: 130%;
  background: radial-gradient(closest-side, rgba(220, 167, 127, 0.26), transparent 75%);
  filter: blur(24px); pointer-events: none;
}
.ot-hero > * { position: relative; z-index: 1; }
.ot-tagline { max-width: 36rem; margin: 1.1rem 0 1.2rem 0; color: rgba(243, 232, 218, 0.82); font-size: 1.02rem; line-height: 1.6; }
.ot-pills { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.ot-pill, .ot-chip {
  display: inline-block; padding: 0.32rem 0.8rem; border-radius: 999px; font-size: 0.78rem; font-weight: 500;
  background: var(--ot-glass-strong); border: 1px solid var(--ot-border); color: var(--ot-ivory);
}

/* Company header */
.ot-company { background: var(--ot-glass); border: 1px solid var(--ot-border); border-radius: 22px; padding: 1.3rem 1.5rem; margin: 0.4rem 0 1rem 0;
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
.ot-company-name { font-size: 1.55rem; font-weight: 600; letter-spacing: -0.02em; color: var(--ot-ivory); margin-bottom: 0.7rem; }
.ot-chips { display: flex; flex-wrap: wrap; gap: 0.45rem; }
.ot-chip-ok { border-color: rgba(163, 179, 150, 0.5); color: #A3B396; }
.ot-chip-bad { border-color: rgba(255, 122, 107, 0.55); color: #FF7A6B; }

/* Stat cards */
.ot-stat { background: var(--ot-glass); border: 1px solid var(--ot-border); border-radius: 20px; padding: 1rem 1.2rem;
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
.ot-stat-label { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 0.66rem; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(243, 232, 218, 0.62); }
.ot-stat-value { font-size: 2.1rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.15; margin-top: 0.3rem; }

/* RAG cards */
.ot-rag { background: var(--ot-glass); border: 1px solid var(--ot-border); border-top: 3px solid var(--accent, var(--ot-clay)); border-radius: 20px;
  padding: 1rem 1.1rem; min-height: 8.2rem; backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
.ot-rag-overall { box-shadow: 0 0 46px -16px var(--accent); background: linear-gradient(160deg, var(--ot-glass-strong), var(--ot-glass)); }
.ot-rag-label { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 0.64rem; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(243, 232, 218, 0.66); }
.ot-rag-pill { display: inline-block; margin-top: 0.45rem; padding: 0.18rem 0.7rem; border-radius: 999px; font-weight: 700; font-size: 0.82rem;
  color: var(--accent); border: 1px solid var(--accent); background: rgba(0, 0, 0, 0.18); letter-spacing: 0.04em; }
.ot-rag-big { font-size: 2.2rem; font-weight: 700; letter-spacing: -0.03em; color: var(--accent); line-height: 1.1; margin-top: 0.3rem; }
.ot-rag-reason { color: rgba(243, 232, 218, 0.8); font-size: 0.86rem; line-height: 1.45; margin-top: 0.55rem; }

/* Flag cards */
.ot-flag { display: flex; gap: 0.9rem; align-items: flex-start; background: var(--ot-glass); border: 1px solid var(--ot-border);
  border-left: 4px solid var(--accent, var(--ot-clay)); border-radius: 16px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
.ot-sev { flex: 0 0 auto; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 0.64rem; letter-spacing: 0.1em; font-weight: 500;
  padding: 0.25rem 0.6rem; border-radius: 999px; color: var(--accent); border: 1px solid var(--accent); margin-top: 0.1rem; }
.ot-flag-title { font-weight: 600; color: var(--ot-ivory); }
.ot-flag-detail { color: rgba(243, 232, 218, 0.78); font-size: 0.92rem; line-height: 1.5; margin-top: 0.2rem; }

/* Widgets */
.stTabs [data-baseweb="tab-list"] { gap: 0.3rem; background: var(--ot-glass); border: 1px solid var(--ot-border); border-radius: 999px; padding: 0.3rem; }
.stTabs [data-baseweb="tab"] { border-radius: 999px; padding: 0.4rem 1.05rem; color: rgba(243, 232, 218, 0.72); height: auto; }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, #B96545, #C2457F); color: #FFFFFF; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #B96545, #C2457F); color: #FFFFFF; border: none; border-radius: 999px; font-weight: 600;
  padding: 0.55rem 1.4rem; box-shadow: 0 10px 26px -12px rgba(194, 69, 127, 0.7);
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover { filter: brightness(1.1); }
[data-testid="stDownloadButton"] button, [data-testid="stBaseButton-secondary"] {
  background: var(--ot-glass-strong); border: 1px solid var(--ot-border); color: var(--ot-ivory); border-radius: 999px;
}
[data-testid="stExpander"] { background: var(--ot-glass); border: 1px solid var(--ot-border); border-radius: 16px; }

@media (max-width: 640px) {
  .ot-hero { padding: 1.5rem 1.3rem; border-radius: 22px; }
  .ot-stat-value { font-size: 1.7rem; }
}
"""


def _safe(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def css_block() -> str:
    return f"<style>{CSS}</style>"


def sidebar_brand() -> str:
    return (
        '<div class="ot-side-brand"><span class="ot-wordmark-sm">OwnnTrak</span>'
        '<span class="ot-byline-sm">by OSH Ventures</span></div>'
    )


def hero() -> str:
    pills = ["Public data only", "Ranges, not guesses", "Flags where the trail goes cold"]
    return (
        '<div class="ot-hero">'
        '<div class="ot-eyebrow">Ownership intelligence</div>'
        '<div class="ot-wordmark">OwnnTrak</div>'
        '<div class="ot-byline">by OSH Ventures</div>'
        '<p class="ot-tagline">Trace who really owns and controls a UK company. Follow the chain up through '
        "holding companies, see each person's likely ownership as a range, and spot where the trail goes cold.</p>"
        '<div class="ot-pills">' + "".join(f'<span class="ot-pill">{_safe(p)}</span>' for p in pills) + "</div>"
        "</div>"
    )


def stat_card(label: str, value, colour: str) -> str:
    return (
        f'<div class="ot-stat"><div class="ot-stat-label">{_safe(label)}</div>'
        f'<div class="ot-stat-value" style="color:{_safe(colour)}">{_safe(value)}</div></div>'
    )


def company_header(name, number, status, source, generated_at) -> str:
    active = (status or "").casefold() == "active"
    status_class = "ot-chip ot-chip-ok" if active else "ot-chip ot-chip-bad"
    chips = [
        f'<span class="ot-chip">{_safe(number)}</span>',
        f'<span class="{status_class}">{_safe(status or "status unknown")}</span>',
        f'<span class="ot-chip">{_safe(source)}</span>',
        f'<span class="ot-chip">{_safe(generated_at)}</span>',
    ]
    return (
        f'<div class="ot-company"><div class="ot-company-name">{_safe(name)}</div>'
        f'<div class="ot-chips">{"".join(chips)}</div></div>'
    )


def rag_card(label: str, rag: str, reasons: list, overall: bool = False) -> str:
    colour = RAG_COLOURS.get(rag, RAG_COLOURS["NA"])
    symbol = RAG_SYMBOLS.get(rag, RAG_SYMBOLS["NA"])
    text = _safe("; ".join(reasons)) if reasons else ""
    head = f'<div class="ot-rag-label">{_safe(label)}</div>'
    if overall:
        body = f'<div class="ot-rag-big">{symbol} {_safe(rag)}</div>'
        if reasons:
            text = "Driven by " + text.lower() if text else text
    else:
        body = f'<span class="ot-rag-pill">{symbol} {_safe(rag)}</span>'
    css_class = "ot-rag ot-rag-overall" if overall else "ot-rag"
    return f'<div class="{css_class}" style="--accent:{colour}">{head}{body}<div class="ot-rag-reason">{text}</div></div>'


def flag_card(severity: str, title: str, detail: str) -> str:
    accent = SEVERITY_COLOURS.get(severity, SEVERITY_COLOURS["INFO"])
    return (
        f'<div class="ot-flag" style="--accent:{accent}"><span class="ot-sev">{_safe(severity)}</span>'
        f'<div><div class="ot-flag-title">{_safe(title)}</div>'
        f'<div class="ot-flag-detail">{_safe(detail)}</div></div></div>'
    )
