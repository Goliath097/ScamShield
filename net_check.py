"""Diagnose why RDAP is failing. Run: python net_check.py"""

import socket

import requests

print("1. DNS resolution")
for host in ("rdap.org", "api.asi1.ai", "google.com"):
    try:
        print("   %-14s -> %s" % (host, socket.gethostbyname(host)))
    except Exception as err:
        print("   %-14s -> DNS FAILED (%s)" % (host, type(err).__name__))

print("\n2. HTTPS reachability")
targets = [
    ("general internet", "https://example.com"),
    ("ASI:One API host", "https://api.asi1.ai"),
    ("RDAP aggregator", "https://rdap.org/domain/google.com"),
    ("RDAP verisign", "https://rdap.verisign.com/com/v1/domain/GOOGLE.COM"),
]
for label, url in targets:
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "ScamShield/1.0"})
        print("   %-18s -> HTTP %s" % (label, r.status_code))
    except Exception as err:
        print("   %-18s -> FAILED (%s)" % (label, type(err).__name__))

print("\n3. Verdict")
print("   If DNS fails for rdap.org only        -> venue DNS filtering. Use phone hotspot.")
print("   If everything fails                   -> no internet / captive portal.")
print("   If only RDAP fails but others work    -> firewall blocks it. Use hotspot.")
print("   If all succeed                        -> transient; re-run forensics.py.")