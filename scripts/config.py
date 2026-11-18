# Conference/school configuration for hongjiang-qian.github.io

CONF_HTML = "conf.html"
FUND_HTML = "fund.html"
TEMPLATE_HTML = "index.html"

# Official sources.
APT_EVENTS_URL = "https://www.appliedprobability.org/community/events"
BERNOULLI_MEETINGS_URL = "https://www.bernoullisociety.org/meetings"
IEEE_CSS_FINANCIAL_URL = "https://www.ieeecss.org/conferences/financially-sponsored-conferences"

# SIAM meetings that are broad/flagship or especially relevant to applied mathematics,
# stochastic systems, computation, dynamics, or control.
SIAM_MAJOR_EVENT_URLS = [
    "https://www.siam.org/conferences-events/siam-conferences/cse27/",
    "https://www.siam.org/conferences-events/siam-conferences/ds27/",
    "https://www.siam.org/conferences-events/siam-conferences/iciam27/",
    "https://www.siam.org/conferences-events/siam-conferences/ct27/",
    "https://www.siam.org/conferences-events/siam-conferences/uq28/",
]

# Current JMM official page.
AMS_MAJOR_EVENT_URLS = [
    "https://meetings.ams.org/math/jmm2027/cfs.cgi",
]

# Only these large/community-wide series are accepted from broad community listings.
MAJOR_TITLE_PATTERNS = [
    r"\bJoint Mathematics Meetings\b",
    r"\bConference on Stochastic Processes and their Applications\b",
    r"\bStochastic Processes and their Applications\b",
    r"\bSPA\b",
    r"\bBernoulli[- ]IMS\b",
    r"\bWorld Congress in Probability and Statistics\b",
    r"\bInstitute of Mathematical Statistics Annual Meeting\b",
    r"\bIMS Annual Meeting\b",
    r"\bINFORMS Applied Probability Society\b",
    r"\bInternational Congress for Industrial and Applied Mathematics\b",
    r"\bICIAM\b",
    r"\bEuropean Meeting of Statisticians\b",
    r"\bWorld Statistics Congress\b",
]

# Schools are shown in a separate tab.
SCHOOL_TITLE_PATTERNS = [
    r"\bSummer School\b",
    r"\bWinter School\b",
    r"\bSpring School\b",
    r"\bResearch School\b",
    r"\bGraduate School\b",
    r"\bIntroductory School\b",
    r"\bSchool:\b",
    r"\bSchool on\b",
    r"\bProbability Lectures\b",
]

# Current JMM seed because the AMS proposal portal does not always print meeting
# dates/location in machine-readable form.
CURATED_SEED_EVENTS = [
    {
        "title": "2027 Joint Mathematics Meetings (JMM 2027)",
        "start_date": "2027-01-12",
        "end_date": "2027-01-15",
        "location": "Chicago, Illinois, U.S.",
        "organization": "AMS",
        "url": "https://meetings.ams.org/math/jmm2027/cfs.cgi",
        "event_type": "conference",
        "source": "AMS",
        "manual": False,
    },
]

# ----------------------------------------------------------------------
# Funding sources.
# These constants are required by scripts/update_funding.py.
# ----------------------------------------------------------------------

SIMONS_TRAVEL_LANDING = (
    "https://www.simonsfoundation.org/mathematics-physical-sciences/"
    "travel-support-for-mathematicians/"
)

NSF_CAREER_URL = (
    "https://www.nsf.gov/funding/opportunities/"
    "career-faculty-early-career-development-program"
)

NSF_MATHSCI_URL = (
    "https://www.nsf.gov/funding/opportunities/"
    "mps-mathsci-mps-mathematical-sciences-research-programs"
)

SIMONS_TARGETED_MPS_URL = (
    "https://www.simonsfoundation.org/funding/targeted-grants-in-mps/"
)
