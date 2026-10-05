from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    industry: str
    subindustry: str | None
    confidence: float
    matched: tuple[str, ...]


RULES: list[tuple[str, str | None, float, tuple[str, ...]]] = [
    ('Roads / Toll Roads', 'Roads / Highways', 0.96, (r'\btoll\b', r'\bhighway\b', r'\bexpressway\b', r'\broad(s)?\b', r'\bbridge(s)?\b', r'\bBOT\b', r'\bHAM\b')),
    ('Hotel / Hospitality', 'Hotels / Resorts', 0.96, (r'\bhotel(s)?\b', r'\bhospitality\b', r'\bresort(s)?\b', r'\bmotel(s)?\b', r'\bconvention centre\b', r'\bconvention center\b')),
    ('Realty / Construction', 'Real Estate', 0.93, (r'\brealt(y|or|ors)\b', r'\breal estate\b', r'\bdeveloper(s)?\b', r'\bproperties\b', r'\bhomes\b', r'\bapartment(s)?\b', r'\btownship\b', r'\bbuildworth\b', r'\bbuilders\b')),
    ('Infrastructure', 'Infrastructure / EPC', 0.90, (r'\binfrastructure\b', r'\bEPC\b', r'\bpublic utility\b', r'\bpublic facility\b')),
    ('Realty / Construction', 'Construction / EPC', 0.88, (r'\bconstruction(s)?\b', r'\bbuildcon\b', r'\bprojects?\b')),
    ('Power / Energy', None, 0.94, (r'\bpower\b', r'\benergy\b', r'\bsolar\b', r'\bwind\b', r'\bthermal\b', r'\belectricity\b')),
    ('Steel / Metals', None, 0.94, (r'\bsteel\b', r'\bispat\b', r'\bmetal(s)?\b', r'\bferro\b', r'\balloy\b', r'\bfoundry\b')),
    ('Pharma / Healthcare', 'Healthcare', 0.96, (r'\bhospital\b', r'\bhealthcare\b', r'\bhealth care\b', r'\bmedical\b')),
    ('Pharma / Healthcare', 'Pharmaceuticals', 0.94, (r'\bpharma\b', r'\bpharmaceutical(s)?\b', r'\bremedies\b', r'\bdrugs?\b')),
    ('Logistics / Transportation', None, 0.92, (r'\blogistics\b', r'\btransport\b', r'\bfreight\b', r'\bwarehouse\b', r'\bshipping\b')),
    ('IT / Technology', None, 0.90, (r'\bsoftware\b', r'\btechnology\b', r'\bdigiconnect\b', r'\bdigital\b', r'\bIT services\b')),
    ('Textiles', None, 0.94, (r'\btextile(s)?\b', r'\bspinners?\b', r'\bpoly-?yarn\b', r'\byarn\b', r'\bapparel(s)?\b', r'\bgarments?\b')),
    ('Agriculture / Food', None, 0.92, (r'\bagro\b', r'\bfood(s)?\b', r'\bdairy\b', r'\bmilk\b', r'\bsugar\b', r'\bvanaspati\b', r'\bprotein(s)?\b')),
    ('Chemicals', None, 0.92, (r'\bchemical(s)?\b', r'\bpetrochemical(s)?\b')),
    ('Automotive', None, 0.92, (r'\bauto(motive)?\b', r'\bmotor(s)?\b', r'\bvehicle(s)?\b', r'\btyre(s)?\b')),
    ('Paper', None, 0.94, (r'\bpaper\b', r'\bpulp\b')),
    ('Retail / Consumer', None, 0.86, (r'\bretail\b', r'\bconsumer\b', r'\bappliances?\b', r'\bFMCG\b')),
]


def classify(*parts: str | None) -> Classification:
    text = ' '.join(p for p in parts if p).upper()
    best: Classification | None = None
    for industry, subindustry, confidence, patterns in RULES:
        matches = tuple(p for p in patterns if re.search(p, text, flags=re.IGNORECASE))
        if not matches:
            continue
        boosted = min(0.99, confidence + 0.01 * (len(matches) - 1))
        candidate = Classification(industry, subindustry, boosted, matches)
        if best is None or candidate.confidence > best.confidence:
            best = candidate
    return best or Classification('Other / Unclear', None, 0.20, ())
