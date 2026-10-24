"""
The actual evidence-gathering. Pure Python — no agents, no LLM.

Run it on its own to test:
    python forensics.py "Your SBI KYC expires today, update at http://sbi-kyc-update.in"
"""

import re
from datetime import datetime, timezone

import requests

RDAP = "https://rdap.org/domain/"
UA = {"User-Agent": "ScamShield/1.0 (Fetch-A-Thon 3.0)"}

# Brands impersonated in Indian scams, with their real domains.
KNOWN_BRANDS = {
    "sbi": "sbi.co.in",
    "statebank": "sbi.co.in",
    "hdfc": "hdfcbank.com",
    "icici": "icicibank.com",
    "axis": "axisbank.com",
    "kotak": "kotak.com",
    "paytm": "paytm.com",
    "phonepe": "phonepe.com",
    "gpay": "pay.google.com",
    "amazon": "amazon.in",
    "flipkart": "flipkart.com",
    "myntra": "myntra.com",
    "indiapost": "indiapost.gov.in",
    "bluedart": "bluedart.com",
    "dtdc": "dtdc.in",
    "fedex": "fedex.com",
    "irctc": "irctc.co.in",
    "uidai": "uidai.gov.in",
    "aadhaar": "uidai.gov.in",
    "incometax": "incometax.gov.in",
    "epfo": "epfindia.gov.in",
    "trai": "trai.gov.in",
    "cbi": "cbi.gov.in",
    "swiggy": "swiggy.com",
    "zomato": "zomato.com",
    "zepto": "zeptonow.com",
    "jio": "jio.com",
    "airtel": "airtel.in",
}

# Real UPI handles. A payment request to any of these is still worth flagging,
# but an unknown handle is more suspicious.
UPI_HANDLES = {
    "okaxis", "oksbi", "okhdfcbank", "okicici", "ybl", "ibl", "axl", "paytm",
    "apl", "upi", "sbi", "hdfcbank", "icici", "axisbank", "kotak", "fbl",
    "jupiteraxis", "superyes", "yesg", "airtel", "freecharge",
}

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
BARE_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|in|net|org|co|io|xyz|top|info|online|site|shop|live|club|me|app|link|cc|ru|tk))\b",
    re.I,
)
UPI_RE = re.compile(r"\b([a-z0-9][a-z0-9._-]{1,48})@([a-z]{2,24})\b", re.I)
PHONE_RE = re.compile(r"(?:\+91[\s-]?|\b)([6-9]\d{9})\b")
AMOUNT_RE = re.compile(r"(?:₹|Rs\.?\s?|INR\s?)\s?([\d,]+(?:\.\d{1,2})?)", re.I)

URGENCY_WORDS = [
    "urgent", "immediately", "within 24 hours", "last chance", "expires today",
    "account will be blocked", "suspended", "legal action", "arrest", "fir",
    "act now", "final notice", "verify now", "click here", "limited time",
    "congratulations", "you have won", "selected", "lucky winner",
    "processing fee", "registration fee", "refundable", "security deposit",
    "work from home", "earn daily", "part time job", "no experience",
]


def extract(text: str) -> dict:
    """Pull every actionable artefact out of the message."""
    urls = URL_RE.findall(text or "")
    domains = set()
    for u in urls:
        m = re.match(r"https?://([^/:?#]+)", u, re.I)
        if m:
            domains.add(m.group(1).lower().lstrip("www."))
    for d in BARE_DOMAIN_RE.findall(text or ""):
        domains.add(d.lower().lstrip("www."))

    upis = []
    for user, handle in UPI_RE.findall(text or ""):
        full = "%s@%s" % (user, handle)
        # crude email filter: real emails usually end in a TLD-bearing domain
        if handle.lower() in UPI_HANDLES or "." not in handle:
            upis.append(full)

    lowered = (text or "").lower()
    hits = [w for w in URGENCY_WORDS if w in lowered]

    return {
        "urls": urls[:8],
        "domains": sorted(domains)[:5],
        "upi_ids": upis[:5],
        "phones": PHONE_RE.findall(text or "")[:5],
        "amounts": AMOUNT_RE.findall(text or "")[:5],
        "urgency_hits": hits[:10],
    }


def lookalike_check(domain: str):
    """Does this domain borrow a known brand name without being the real one?"""
    host = domain.lower().lstrip("www.")
    for brand, official in KNOWN_BRANDS.items():
        if brand in host.replace("-", "").replace("_", ""):
            if host == official or host.endswith("." + official):
                return None  # it IS the official domain
            return "impersonates '%s' (real domain: %s)" % (brand, official)
    return None


def _rdap_endpoints(domain: str):
    """Several RDAP sources — the aggregator first, then registry-specific ones."""
    tld = domain.rsplit(".", 1)[-1].lower()
    urls = ["https://rdap.org/domain/" + domain]
    if tld in ("com", "net"):
        urls.append("https://rdap.verisign.com/%s/v1/domain/%s" % (tld, domain.upper()))
    urls.append("https://rdap-bootstrap.arin.net/bootstrap/domain/" + domain)
    return urls


def domain_age(domain: str) -> dict:
    """Ask RDAP when the domain was registered. Free, no API key."""
    data = None
    errors = []
    for url in _rdap_endpoints(domain):
        try:
            r = requests.get(url, headers=UA, timeout=12)
            if r.status_code == 404:
                return {"ok": False, "note": "not found in RDAP (may be a subdomain or unregistered)"}
            r.raise_for_status()
            data = r.json()
            break
        except Exception as err:
            errors.append("%s:%s" % (url.split("/")[2], type(err).__name__))
    if data is None:
        return {"ok": False, "note": "RDAP unavailable (%s)" % "; ".join(errors)}

    registered = None
    for ev in data.get("events") or []:
        if ev.get("eventAction") in ("registration", "created"):
            registered = ev.get("eventDate")
            break
    if not registered:
        return {"ok": True, "note": "registration date not published"}

    try:
        dt = datetime.fromisoformat(registered.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
    except ValueError:
        return {"ok": True, "note": "registered %s" % registered[:10]}

    return {"ok": True, "registered": registered[:10], "age_days": days}


def investigate(text: str):
    """Returns (human-readable evidence block, compact indicator summary)."""
    found = extract(text)
    lines = ["EVIDENCE GATHERED", ""]
    flags = []

    # --- domains: the strongest signal we have -----------------------------
    if found["domains"]:
        lines.append("Domains found:")
        for d in found["domains"]:
            lines.append("  • %s" % d)
            fake = lookalike_check(d)
            if fake:
                lines.append("      LOOKALIKE: %s" % fake)
                flags.append("domain %s %s" % (d, fake))
            age = domain_age(d)
            if age.get("age_days") is not None:
                days = age["age_days"]
                lines.append("      Registered: %s (%d days ago)" % (age["registered"], days))
                if days < 90:
                    lines.append("      NEWLY REGISTERED — strong fraud signal")
                    flags.append("domain %s registered only %d days ago" % (d, days))
                else:
                    flags.append("domain %s is %d days old" % (d, days))
            else:
                lines.append("      Age: %s" % age.get("note", "unknown"))
                flags.append("domain %s age unknown (%s)" % (d, age.get("note", "")))
        lines.append("")
    else:
        lines += ["Domains found: none", ""]

    if found["urls"]:
        lines += ["Links in message:"] + ["  • %s" % u for u in found["urls"]] + [""]

    if found["upi_ids"]:
        lines.append("UPI IDs requested:")
        for u in found["upi_ids"]:
            handle = u.split("@")[-1].lower()
            known = "known handle" if handle in UPI_HANDLES else "UNRECOGNISED handle"
            lines.append("  • %s (%s)" % (u, known))
            flags.append("payment to UPI %s (%s)" % (u, known))
        lines.append("")

    if found["phones"]:
        lines += ["Phone numbers:"] + ["  • +91 %s" % p for p in found["phones"]] + [""]
        flags.append("%d phone number(s) given for contact" % len(found["phones"]))

    if found["amounts"]:
        lines += ["Money mentioned: " + ", ".join("₹" + a for a in found["amounts"]), ""]
        flags.append("asks for/offers money: " + ", ".join("₹" + a for a in found["amounts"]))

    if found["urgency_hits"]:
        lines += ["Pressure/lure language: " + ", ".join(found["urgency_hits"]), ""]
        flags.append("pressure language: " + ", ".join(found["urgency_hits"][:6]))

    if not flags:
        flags.append("no technical indicators found — message contains no links, payment IDs or pressure language")

    return "\n".join(lines).rstrip(), " | ".join(flags)


if __name__ == "__main__":
    import sys

    sample = " ".join(sys.argv[1:]) or (
        "URGENT: Your SBI account will be blocked today. Complete KYC at "
        "http://sbi-kyc-update.in or pay ₹499 verification to scamguy@okaxis. Call 9876543210."
    )
    ev, ind = investigate(sample)
    print(ev)
    print("\n--- INDICATORS ---\n" + ind)