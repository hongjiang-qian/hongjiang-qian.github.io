"""Configuration for automatic Conferences and Funding pages."""

CONFERENCE_SOURCES = [
    {"name": "Applied Probability Trust", "url": "https://www.appliedprobability.org/community/events", "parser": "apt"},
    {"name": "Bernoulli Society", "url": "https://www.bernoullisociety.org/meetings", "parser": "bernoulli"},
]

CONFERENCE_KEYWORDS = [
    "probability", "probabilistic", "stochastic", "random", "spde",
    "partial differential equation", "diffusion", "markov", "mean-field",
    "mean field", "control", "filtering", "large deviation",
    "moderate deviation", "rare event", "monte carlo", "interacting",
    "queue", "statistical physics", "statistical mechanics",
]
CONFERENCE_EXCLUDE_KEYWORDS = ["undergraduate", "job fair"]

CONFERENCE_PAGE_TITLE = "Conferences and Schools"
CONFERENCE_PAGE_INTRO = (
    "A selected list of upcoming conferences, workshops, and schools in probability, "
    "stochastic analysis, stochastic control, SPDEs, and related areas."
)
FUNDING_PAGE_TITLE = "Funding Opportunities"
FUNDING_PAGE_INTRO = (
    "A selected list of external research and travel funding opportunities relevant "
    "to mathematics and the mathematical sciences."
)

# External funding only. No Wayne State/internal funding.
FUNDING_PROGRAMS = [
    {
        "id": "simons-travel",
        "title": "Travel Support for Mathematicians",
        "sponsor": "Simons Foundation",
        "url": "https://www.simonsfoundation.org/funding/travel-support-for-mathematicians-2027/",
        "kind": "Research and travel support",
        "parser": "simons_travel",
    },
    {
        "id": "nsf-career",
        "title": "Faculty Early Career Development Program (CAREER)",
        "sponsor": "U.S. National Science Foundation",
        "url": "https://www.nsf.gov/funding/opportunities/career-faculty-early-career-development-program",
        "kind": "Early-career research and education",
        "parser": "nsf_career",
    },
    {
        "id": "nsf-mps-mathsci",
        "title": "MPS Mathematical Sciences Research Programs (MPS MathSci)",
        "sponsor": "U.S. National Science Foundation",
        "url": "https://www.nsf.gov/funding/opportunities/mps-mathsci-mps-mathematical-sciences-research-programs",
        "kind": "Mathematical sciences research",
        "parser": "nsf_anytime",
    },
    {
        "id": "simons-targeted-mps",
        "title": "Targeted Grants in MPS",
        "sponsor": "Simons Foundation",
        "url": "https://www.simonsfoundation.org/funding/targeted-grants-in-mps/",
        "kind": "High-risk theoretical mathematics and physical sciences",
        "parser": "simons_rolling",
    },
]

CONFERENCE_JEMDOC = "conferences.jemdoc"
FUNDING_JEMDOC = "funding.jemdoc"
CONFERENCE_HTML = "conferences.html"
FUNDING_HTML = "funding.html"
