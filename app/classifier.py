from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    industry: str
    subindustry: str | None
    confidence: float
    matched: tuple[str, ...]


# Conservative deterministic rules. Specific sector words auto-classify;
# genuinely ambiguous names stay in Other / Unclear for human review.
RULES: list[tuple[str, str | None, float, tuple[str, ...]]] = [
    ('Roads / Toll Roads', 'Roads / Highways', 0.96, (
        r'\btoll\s+road(s)?\b', r'\btollway(s)?\b', r'\bhighway(s)?\b',
        r'\bexpressway(s)?\b', r'\broad\s+project(s)?\b', r'\broad\s+infrastructure\b',
        r'\bbridge(s)?\b', r'\bBOT\b', r'\bHAM\b',
    )),
    ('Hotel / Hospitality', 'Hotels / Resorts', 0.96, (
        r'\bhotel(s)?\b', r'\bhospitality\b', r'\bresort(s)?\b', r'\bmotel(s)?\b',
        r'\bleisure\b', r'\btourism\b', r'\bconvention centre\b', r'\bconvention center\b',
    )),
    ('Realty / Construction', 'Real Estate', 0.93, (
        r'\brealt(y|or|ors)\b', r'\breal estate\b', r'\bdeveloper(s)?\b',
        r'\bproperties\b', r'\bhomes\b', r'\bhousing\b', r'\bapartment(s)?\b',
        r'\btownship(s)?\b', r'\bbuilders?\b', r'\bpromoters?\b', r'\bbuildworth\b',
    )),
    ('Infrastructure', 'Infrastructure / EPC', 0.91, (
        r'\binfrastructure\b', r'\binfra\b', r'\bEPC\b', r'\bpublic utility\b',
        r'\bpublic facility\b',
    )),
    ('Realty / Construction', 'Construction / EPC', 0.89, (
        r'\bconstruction(s)?\b', r'\bbuildcon\b', r'\bcivil works?\b',
    )),
    ('Power / Energy', None, 0.94, (
        r'\bpower\b', r'\benergy\b', r'\bsolar\b', r'\bwind\b', r'\bthermal\b',
        r'\belectricity\b', r'\brenewable(s)?\b', r'\bbatter(y|ies)\b', r'\benergy storage\b',
    )),
    ('Steel / Metals', None, 0.94, (
        r'\bsteel\b', r'\bispat\b', r'\bmetal(s)?\b', r'\bferro\b', r'\balloy(s)?\b',
        r'\bfoundr(y|ies)\b', r'\baluminium\b', r'\baluminum\b', r'\biron\b',
    )),
    ('Pharma / Healthcare', 'Healthcare', 0.94, (
        r'\bhospital(s)?\b', r'\bhealthcare\b', r'\bhealth care\b', r'\bmedical\b',
        r'\bdiagnostic(s)?\b', r'\bwellness\b', r'\bclinic(s)?\b',
    )),
    ('Pharma / Healthcare', 'Pharmaceuticals', 0.94, (
        r'\bpharma\b', r'\bpharmaceutical(s)?\b', r'\bremedies\b', r'\bdrugs?\b',
        r'\blife sciences?\b', r'\blaborator(y|ies)\b',
    )),
    ('Education', None, 0.93, (
        r'\beducation\b', r'\bpedagogy\b', r'\bschool(s)?\b', r'\bcollege(s)?\b',
        r'\bacadem(y|ies)\b', r'\blearning\b', r'\bedutech\b',
    )),
    ('Logistics / Transportation', None, 0.92, (
        r'\blogistics\b', r'\btransport(ation)?\b', r'\bfreight\b',
        r'\bwarehouse(s|ing)?\b', r'\bshipping\b', r'\bcargo\b',
    )),
    ('IT / Technology', None, 0.91, (
        r'\bsoftware\b', r'\btechnolog(y|ies)\b', r'\btech\s+services?\b',
        r'\binfotech\b', r'\bdigital\b', r'\bIT services\b', r'\bdata systems?\b',
    )),
    ('Textiles', None, 0.94, (
        r'\btextile(s)?\b', r'\bspinn(ing|ers?)\b', r'\bcotex\b', r'\bpoly-?yarn\b',
        r'\byarn\b', r'\bfabric(s)?\b', r'\bapparel(s)?\b', r'\bgarments?\b',
    )),
    ('Agriculture / Food', None, 0.92, (
        r'\bagro\b', r'\bagriculture\b', r'\bfood(s)?\b', r'\bseafood\b', r'\bdairy\b',
        r'\bmilk\b', r'\bsugar\b', r'\bvanaspati\b', r'\bprotein(s)?\b', r'\bedible\b',
        r'\brice\b', r'\bgrain(s)?\b',
    )),
    ('Chemicals', 'Plastics / Polymers', 0.91, (
        r'\bplastic(s)?\b', r'\bpolymer(s)?\b', r'\bresin(s)?\b',
    )),
    ('Chemicals', None, 0.92, (
        r'\bchemical(s)?\b', r'\bpetrochemical(s)?\b', r'\bfertilizer(s)?\b',
    )),
    ('Automotive', None, 0.92, (
        r'\bauto(motive)?\b', r'\bmotor(s)?\b', r'\bvehicle(s)?\b', r'\btyre(s)?\b',
        r'\bautomobile(s)?\b',
    )),
    ('Financial Services', None, 0.91, (
        r'\bfinancial services?\b', r'\bmicrofinance\b', r'\bsecurities\b',
        r'\bNBFC\b', r'\bfinance company\b', r'\bleasing\b',
    )),
    ('Mining', None, 0.92, (r'\bmining\b', r'\bminerals?\b', r'\bcoal\b', r'\bore\b')),
    ('Cement / Building Materials', None, 0.93, (
        r'\bcement\b', r'\bconcrete\b', r'\bceramic(s)?\b', r'\btiles?\b',
        r'\bgranite\b', r'\bgranito\b', r'\bmarble\b',
    )),
    ('Manufacturing', 'Packaging', 0.91, (
        r'\bpackaging\b', r'\bflexipack\b', r'\bflexible packaging\b',
    )),
    ('Manufacturing', 'Engineering', 0.88, (
        r'\bengineering\b', r'\bfabrication\b', r'\bmachinery\b', r'\bengineering works\b',
    )),
    ('Manufacturing', None, 0.84, (r'\bmanufactur(ing|er|ers)\b',)),
    ('Media / Entertainment', None, 0.90, (
        r'\btelevision\b', r'\bbroadcast(ing)?\b', r'\bmedia\b', r'\bentertainment\b',
        r'\bfilms?\b',
    )),
    ('Paper', None, 0.94, (r'\bpaper\b', r'\bpulp\b')),
    ('Retail / Consumer', None, 0.87, (
        r'\bretail\b', r'\bconsumer\b', r'\bappliances?\b', r'\bFMCG\b',
        r'\bdepartment store(s)?\b',
    )),
    ('Trading / Distribution', None, 0.82, (r'\btrading\b', r'\btraders?\b',)),
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
