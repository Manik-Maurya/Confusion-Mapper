"""
PISA-style maths units, with every wrong answer diagnosed.

PISA does not test maths as a list of sums. Each item is a small unit: a
real-world situation (a phone plan, a rain gauge, a bus timetable) and
then a few questions about it, each one checking a different part of
mathematical literacy. India took part once, in 2009, through schools in
Himachal Pradesh and Tamil Nadu, finished near the bottom, and the
government of the day blamed questions that were "out of context" for
Indian students. Whatever you think of that argument, the fix is not to
avoid this kind of question. It is to give children practice with it, in
situations they actually recognise.

So this module writes PISA-style units set in Indian contexts: rupees, a
monsoon rain gauge, a school garden, a bus to the district headquarters,
the price of dal. The structure follows the published PISA 2022
mathematics framework (pisa2022-maths.oecd.org):

  content     quantity, uncertainty and data, change and relationships,
              space and shape
  process     formulate, employ, interpret and evaluate, and mathematical
              reasoning (the 2022 framework's new emphasis)
  context     personal, occupational, societal, scientific
  formats     multiple choice, complex multiple choice (true/false rows),
              and constructed response with a scoring guide

The part that is ConfusionMapper's own: every wrong option, every wrong
true/false judgement and every common wrong written answer carries a CFI
label (RF, PK, CF, INT) and a one-line note on the thinking behind it. So
the teacher's key does not just say "B is wrong", it says what a child who
picked B probably believes.

What these items are not. They are original templates, not released PISA
items, they have not been field-tested, and they carry no difficulty
estimates. PISA is written for 15-year-olds. These use Class 7 to 9 NCERT
maths, so they fit students around Class 8 to 10. Numbers in the tables
are made up for practice and say so on the page.
"""

import csv
import io
import json
import math
import random
from fractions import Fraction

from .taxonomy import ERROR_TYPES, TAXONOMY


CONTENT_CATEGORIES = {
    "quantity":                 "Quantity",
    "uncertainty_and_data":     "Uncertainty and data",
    "change_and_relationships": "Change and relationships",
    "space_and_shape":          "Space and shape",
}
PROCESSES = {
    "formulate": "Formulate",
    "employ":    "Employ",
    "interpret": "Interpret and evaluate",
    "reason":    "Mathematical reasoning",
}
CONTEXTS = {
    "personal":     "Personal",
    "occupational": "Occupational",
    "societal":     "Societal",
    "scientific":   "Scientific",
}
FORMATS = {
    "multiple_choice":         "Multiple choice",
    "complex_multiple_choice": "Complex multiple choice",
    "constructed_response":    "Constructed response",
}

DISCLAIMER = ("PISA-style practice items written from original templates that "
              "follow the published PISA 2022 mathematics framework. They are not "
              "official PISA items and have not been field-tested. Numbers in "
              "tables are made up for practice.")


# The same names in Hindi. Drafts, like all the Hindi here: see
# docs/hindi-review.md for how a teacher can check and correct them.
CONTENT_CATEGORIES_HI = {
    "quantity":                 "मात्रा",
    "uncertainty_and_data":     "अनिश्चितता और आँकड़े",
    "change_and_relationships": "परिवर्तन और संबंध",
    "space_and_shape":          "स्थान और आकार",
}
PROCESSES_HI = {
    "formulate": "गणितीय रूप देना",
    "employ":    "गणित का उपयोग करना",
    "interpret": "व्याख्या और मूल्यांकन",
    "reason":    "गणितीय तर्क",
}
CONTEXTS_HI = {
    "personal":     "व्यक्तिगत",
    "occupational": "व्यावसायिक",
    "societal":     "सामाजिक",
    "scientific":   "वैज्ञानिक",
}
FORMATS_HI = {
    "multiple_choice":         "बहुविकल्पीय",
    "complex_multiple_choice": "सही/गलत वाले कथन",
    "constructed_response":    "लिखित उत्तर",
}
CFI_NAMES_HI = {
    "RF":  "याद न होना",
    "PK":  "अधूरी समझ",
    "CF":  "पक्की गलत धारणा",
    "INT": "दूसरे विषय का घालमेल",
}
DISCLAIMER_HI = ("PISA जैसे अभ्यास प्रश्न, जो PISA 2022 के प्रकाशित गणित ढाँचे पर आधारित "
                 "मौलिक साँचों से बनाए गए हैं। ये PISA के आधिकारिक प्रश्न नहीं हैं और इनका "
                 "क्षेत्र-परीक्षण नहीं हुआ है। तालिकाओं की संख्याएँ अभ्यास के लिए बनाई गई हैं।")
HINDI_DRAFT_NOTE = {
    "en": "The Hindi text is a draft translation. It has not yet been checked by a "
          "Hindi-medium maths teacher.",
    "hi": "हिन्दी पाठ अभी अनुवाद का प्रारूप है। किसी हिन्दी-माध्यम गणित शिक्षक ने इसे अभी "
          "जाँचा नहीं है। कोई शब्द अटपटा लगे तो बताइए।",
}


def _names(lang):
    """The display names for one language."""
    if lang == "hi":
        return {"content": CONTENT_CATEGORIES_HI, "process": PROCESSES_HI,
                "context": CONTEXTS_HI, "format": FORMATS_HI, "cfi": CFI_NAMES_HI,
                "hints": RETEACH_HINTS_HI, "disclaimer": DISCLAIMER_HI}
    return {"content": CONTENT_CATEGORIES, "process": PROCESSES, "context": CONTEXTS,
            "format": FORMATS, "cfi": {c: TAXONOMY[c]["name"] for c in ERROR_TYPES},
            "hints": RETEACH_HINTS, "disclaimer": DISCLAIMER}


def _lang_of(units):
    return units[0].get("lang", "en") if units else "en"


class _Collision(Exception):
    """Raised when a random draw makes two options identical. The unit is
    redrawn, so a student never sees the same answer twice in one list."""


# -----------------------------------------------------------------------------
# Two languages from one draw
# -----------------------------------------------------------------------------
#
# Every piece of text in a unit is written as a pair, English and Hindi, in
# the same place and from the same random numbers. The finished unit is then
# turned into one language. That way a Hindi booklet and an English booklet
# from the same seed have the same numbers, the same answer letters and the
# same key, so a bilingual class can share one answer sheet.
#
# The Hindi is a first draft. It has not yet been checked by a Hindi-medium
# maths teacher, and the booklet says so until it has.

LANGUAGES = ("en", "hi")


class T:
    """One piece of text in both languages."""
    __slots__ = ("en", "hi")

    def __init__(self, en, hi):
        self.en, self.hi = en, hi

    def get(self, lang):
        return self.hi if lang == "hi" else self.en

    def __eq__(self, other):
        return isinstance(other, T) and (self.en, self.hi) == (other.en, other.hi)

    def __hash__(self):
        return hash((self.en, self.hi))

    def __repr__(self):
        return f"T({self.en!r}, {self.hi!r})"


def _in(text, lang):
    return text.get(lang) if isinstance(text, T) else str(text)


def _localize(obj, lang):
    if isinstance(obj, T):
        return obj.get(lang)
    if isinstance(obj, dict):
        return {k: _localize(v, lang) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_localize(v, lang) for v in obj]
    return obj


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------

def _rs(x):
    if float(x).is_integer():
        return f"Rs {int(x):,}"
    return f"Rs {x:,.2f}"


def _rs_hi(x):
    if float(x).is_integer():
        return f"₹{int(x):,}"
    return f"₹{x:,.2f}"


def _money(x):
    return T(_rs(x), _rs_hi(x))


def _num(x, places=2):
    """12 stays 12, 12.5 stays 12.5, 12.3333 becomes 12.33."""
    x = float(x)
    if x.is_integer():
        return f"{int(x):,}"
    return f"{x:,.{places}f}".rstrip("0").rstrip(".")


def _clock(minutes):
    h, m = divmod(int(minutes), 60)
    suffix = "am" if h < 12 else "pm"
    return f"{h % 12 or 12}:{m:02d} {suffix}"


def _clock_hi(minutes):
    h, m = divmod(int(minutes), 60)
    part = "सुबह" if h < 12 else "दोपहर" if h < 16 else "शाम" if h < 19 else "रात"
    return f"{part} {h % 12 or 12}:{m:02d} बजे"


def _time(minutes):
    return T(_clock(minutes), _clock_hi(minutes))


def _frac(f):
    return f"{f.numerator}/{f.denominator}"


def _metres(cm):
    return _num(cm / 100) + " m"


def _metres_hi(cm):
    return _num(cm / 100) + " मी"


# -----------------------------------------------------------------------------
# Question builders
# -----------------------------------------------------------------------------

def _mcq(qid, process, prompt, correct, distractors, rng):
    """distractors: list of (option, error_type, note)."""
    options = [correct] + [d[0] for d in distractors]
    for lang in LANGUAGES:
        texts = [_in(o, lang) for o in options]
        if len(set(texts)) != len(texts) or any(not t.strip() for t in texts):
            raise _Collision
    order = list(options)
    rng.shuffle(order)
    letters = "ABCDEF"
    return {
        "qid": qid, "process": process, "format": "multiple_choice", "prompt": prompt,
        "correct_answer": correct,
        "distractors": [{"option": o, "error_type": e, "note": n} for o, e, n in distractors],
        "options": [{"letter": letters[i], "text": o} for i, o in enumerate(order)],
        "key": letters[order.index(correct)],
    }


def _complex(qid, process, prompt, statements):
    """statements: list of (text, is_true, error_type, note_if_wrong)."""
    return {
        "qid": qid, "process": process, "format": "complex_multiple_choice", "prompt": prompt,
        "statements": [{"text": t, "answer": bool(a),
                        "if_wrong": {"error_type": e, "note": n}} for t, a, e, n in statements],
    }


def _open(qid, process, prompt, accepted, full_credit, common_wrong, partial_credit=None):
    """common_wrong: list of (answer, error_type, note)."""
    return {
        "qid": qid, "process": process, "format": "constructed_response", "prompt": prompt,
        "scoring": {
            "accepted_answers": list(accepted),
            "full_credit": full_credit,
            "partial_credit": partial_credit,
            "no_credit": T("Other responses, or no response.",
                           "अन्य उत्तर, या कोई उत्तर नहीं।"),
        },
        "common_wrong_answers": [{"answer": a, "error_type": e, "note": n}
                                 for a, e, n in common_wrong],
    }


def _table(columns, rows):
    return {"columns": list(columns), "rows": [list(r) for r in rows]}


# -----------------------------------------------------------------------------
# Unit templates
# -----------------------------------------------------------------------------
#
# Each template is f(rng, uid) -> unit. Numbers are drawn so that every
# correct answer is exact (no rupees with eleven decimal places), and each
# unit keeps its raw numbers under "data" so the tests can recompute every
# answer independently instead of trusting the template.


def _unit_data_plans(rng, uid):
    d = rng.choice([10, 15, 20, 25])
    breakeven = rng.choice([4, 5, 6, 8, 10, 12])
    fee = d * breakeven
    p = rng.choice([10, 12, 15, 20])
    q = p + d
    u1 = rng.choice([u for u in range(3, 16) if u != breakeven])
    u2 = rng.choice([u for u in range(2, 21) if abs(u - breakeven) >= 2])
    cost_a2, cost_b2 = fee + p * u2, q * u2
    cheaper = "A" if cost_a2 < cost_b2 else "B"

    if cheaper == "A":
        wrong_plan = (T("Plan B, because it has no monthly charge.",
                        "प्लान B, क्योंकि उसमें कोई मासिक शुल्क नहीं है।"), "CF",
                      T("believes a plan with no fixed fee is always cheaper, without "
                        "checking the cost at this amount of data",
                        "मानते हैं कि बिना तय शुल्क वाला प्लान हमेशा सस्ता होता है, इतने "
                        "डेटा पर खर्च जाँचे बिना"))
    else:
        wrong_plan = (T("Plan A, because its rate per GB is lower.",
                        "प्लान A, क्योंकि उसकी प्रति GB दर कम है।"), "CF",
                      T("believes the lower rate always wins, ignoring the fixed "
                        "monthly charge when little data is used",
                        "मानते हैं कि कम दर हमेशा फायदे की होती है, कम डेटा पर तय मासिक "
                        "शुल्क को अनदेखा करके"))

    questions = [
        _mcq(f"{uid}_Q1", "employ",
             T(f"How much does Plan A cost in a month when the family uses {u1} GB?",
               f"जब परिवार एक महीने में {u1} GB डेटा इस्तेमाल करता है, तो प्लान A का खर्च "
               f"कितना होगा?"),
             _money(fee + p * u1),
             [(_money(p * u1), "PK",
               T("multiplied the rate by the data used but left out "
                 "the fixed monthly charge",
                 "दर को इस्तेमाल हुए डेटा से गुणा किया, पर तय मासिक शुल्क जोड़ना भूल गए")),
              (_money((fee + p) * u1), "CF",
               T("charged the monthly fee again for every GB, "
                 "treating the fixed charge as part of the rate",
                 "मासिक शुल्क को हर GB पर फिर से लगा दिया, मानो तय शुल्क भी दर का हिस्सा हो")),
              (_money(q * u1), "INT",
               T("worked out the cost under Plan B, the right answer "
                 "to a different question",
                 "प्लान B का खर्च निकाला, जो किसी दूसरे प्रश्न का सही उत्तर है"))], rng),
        _mcq(f"{uid}_Q2", "formulate",
             T("Which expression gives the monthly cost of Plan A, in rupees, when x GB "
               "of data is used?",
               "x GB डेटा इस्तेमाल करने पर प्लान A का मासिक खर्च (रुपयों में) कौन-सा व्यंजक "
               "बताता है?"),
             f"{fee} + {p}x",
             [(f"{p} + {fee}x", "CF",
               T("swapped the fixed charge and the rate per GB",
                 "तय शुल्क और प्रति GB दर की जगह आपस में बदल दी")),
              (f"{q}x", "INT",
               T("wrote the rule for Plan B instead of Plan A",
                 "प्लान A की जगह प्लान B का नियम लिख दिया")),
              (f"{p}x", "PK",
               T("kept the rate per GB but forgot the fixed monthly charge",
                 "प्रति GB दर तो रखी, पर तय मासिक शुल्क भूल गए"))],
             rng),
        _open(f"{uid}_Q3", "interpret",
              T(f"Next month Asha expects to use {u2} GB. Which plan should she choose to "
                f"pay less? Show the cost of both plans.",
                f"अगले महीने आशा को लगभग {u2} GB डेटा इस्तेमाल करने की उम्मीद है। कम पैसे "
                f"देने के लिए उसे कौन-सा प्लान चुनना चाहिए? दोनों प्लान का खर्च दिखाइए।"),
              [T(f"Plan {cheaper}", f"प्लान {cheaper}")],
              T(f"Plan {cheaper}, with both costs shown: Plan A {_rs(cost_a2)} and Plan B "
                f"{_rs(cost_b2)}, or another correct comparison of the two.",
                f"प्लान {cheaper}, दोनों खर्च दिखाकर: प्लान A {_rs_hi(cost_a2)} और प्लान B "
                f"{_rs_hi(cost_b2)}, या दोनों की कोई और सही तुलना।"),
              [wrong_plan,
               (T(f"Works out both plans for {u1} GB, the amount in Question 1.",
                  f"दोनों प्लान का खर्च {u1} GB के लिए निकालते हैं, जो प्रश्न 1 की मात्रा है।"),
                "INT",
                T(f"answered for a different amount of data, not the {u2} GB asked about",
                  f"डेटा की दूसरी मात्रा के लिए उत्तर दिया, पूछे गए {u2} GB के लिए नहीं")),
               (T("Works out the cost of one plan only and chooses it.",
                  "केवल एक प्लान का खर्च निकालकर उसे चुन लेते हैं।"), "PK",
                T("started the comparison but did not finish it",
                  "तुलना शुरू की पर पूरी नहीं की"))],
              partial_credit=T(f"Plan {cheaper} with only one cost shown, or with a small "
                               f"slip in one cost that does not change the choice.",
                               f"प्लान {cheaper}, पर केवल एक खर्च दिखाया, या एक खर्च में "
                               f"छोटी-सी गलती जिससे चुनाव नहीं बदलता।")),
    ]
    return {
        "unit_id": uid, "template": "data_plans",
        "title": T("Mobile data plans", "मोबाइल डेटा प्लान"),
        "content": "change_and_relationships", "context": "personal", "emphasis": None,
        "stimulus": T(f"Asha's family is choosing a mobile data plan.\n\n"
                      f"Plan A costs Rs {fee} a month, plus Rs {p} for every GB of data used.\n\n"
                      f"Plan B has no monthly charge. It costs Rs {q} for every GB of data used.",
                      f"आशा का परिवार एक मोबाइल डेटा प्लान चुन रहा है।\n\n"
                      f"प्लान A में हर महीने ₹{fee} लगते हैं, और साथ में इस्तेमाल हुए हर GB "
                      f"डेटा के ₹{p}।\n\n"
                      f"प्लान B में कोई मासिक शुल्क नहीं है। इसमें इस्तेमाल हुए हर GB डेटा के "
                      f"₹{q} लगते हैं।"),
        "table": None,
        "data": {"fee": fee, "rate_a": p, "rate_b": q, "u1": u1, "u2": u2},
        "questions": questions,
    }


def _unit_rainfall(rng, uid):
    months = [T("June", "जून"), T("July", "जुलाई"), T("August", "अगस्त"),
              T("September", "सितंबर")]
    june, july = rng.randint(70, 140), rng.randint(210, 330)
    aug, sep = rng.randint(180, 320), rng.randint(90, 190)
    sep += (-(june + july + aug + sep)) % 4          # make the mean a whole number
    vals = [june, july, aug, sep]
    if len(set(vals)) < 4:
        raise _Collision
    total = sum(vals)
    mean = total // 4
    s = sorted(vals)
    median, midrange = (s[1] + s[2]) / 2, (s[0] + s[3]) / 2
    by_size = sorted(range(4), key=lambda i: -vals[i])
    first, second, third, fourth = (months[i] for i in by_size)

    delta = rng.choice([20, 30, 40, 50])
    claim_true = rng.random() < 0.5
    threshold = total - delta if claim_true else total + delta

    def mm(x):
        return T(f"{x} mm", f"{x} मिमी")

    questions = [
        _mcq(f"{uid}_Q1", "interpret",
             T("In which month did the club record the most rain?",
               "क्लब ने किस महीने में सबसे ज्यादा बारिश दर्ज की?"),
             first,
             [(second, "PK",
               T("picked a month with a lot of rain but did not compare all "
                 "four values",
                 "ज्यादा बारिश वाला महीना चुना, पर चारों मान आपस में नहीं मिलाए")),
              (third, "RF",
               T("no clear link to the numbers in the table",
                 "तालिका की संख्याओं से कोई साफ संबंध नहीं")),
              (fourth, "CF",
               T("confidently picked the smallest value, mixing up 'most' "
                 "and 'least'",
                 "पूरे विश्वास से सबसे छोटा मान चुन लिया, 'सबसे ज्यादा' और 'सबसे कम' में "
                 "उलझकर"))], rng),
        _mcq(f"{uid}_Q2", "employ",
             T("What was the mean (average) monthly rainfall from June to September?",
               "जून से सितंबर तक की औसत (माध्य) मासिक वर्षा कितनी थी?"),
             mm(mean),
             [(mm(total), "PK",
               T("added the four months but did not divide by 4",
                 "चारों महीनों को जोड़ा पर 4 से भाग नहीं दिया")),
              (mm(_num(median)), "INT",
               T("found the median, a different kind of average",
                 "माध्यिका निकाली, जो एक दूसरी तरह का औसत है")),
              (mm(_num(midrange)), "CF",
               T("believes the average is halfway between the "
                 "biggest and smallest values",
                 "मानते हैं कि औसत सबसे बड़े और सबसे छोटे मान के ठीक बीच में होता है"))],
             rng),
        _complex(f"{uid}_Q3", "reason",
                 T("Is each statement true or false? Use the table.",
                   "हर कथन सही है या गलत? तालिका का उपयोग कीजिए।"),
                 [(T("July had more than twice as much rain as June.",
                     "जुलाई में जून से दोगुनी से ज्यादा बारिश हुई।"), july > 2 * june, "PK",
                   T("compared the two numbers without working out twice the June value",
                     "दोनों संख्याएँ मिलाईं, पर जून के मान का दोगुना नहीं निकाला")),
                  (T("The rainfall went up every month from June to September.",
                     "जून से सितंबर तक हर महीने बारिश बढ़ती गई।"), False, "CF",
                   T("assumed the monsoon keeps getting heavier, without checking each month",
                     "मान लिया कि मानसून लगातार तेज होता जाता है, हर महीना जाँचे बिना")),
                  (T(f"Altogether, the club recorded more than {threshold} mm of rain in these "
                     f"four months.",
                     f"इन चार महीनों में क्लब ने कुल मिलाकर {threshold} मिमी से ज्यादा बारिश "
                     f"दर्ज की।"), claim_true, "RF",
                   T("did not add up the four months",
                     "चारों महीनों की बारिश नहीं जोड़ी"))]),
    ]
    return {
        "unit_id": uid, "template": "rainfall",
        "title": T("Monsoon rain gauge", "मानसून का वर्षामापी"),
        "content": "uncertainty_and_data", "context": "scientific", "emphasis": None,
        "stimulus": T("The science club of a village school in Uttar Pradesh read its rain "
                      "gauge every morning during the monsoon and added up the rain for each "
                      "month. (These numbers are made up for practice.)",
                      "उत्तर प्रदेश के एक गाँव के स्कूल के विज्ञान क्लब ने मानसून के दौरान हर "
                      "सुबह अपना वर्षामापी पढ़ा और हर महीने की बारिश जोड़ी। (ये संख्याएँ "
                      "अभ्यास के लिए बनाई गई हैं।)"),
        "table": _table([T("Month", "महीना"), T("Rainfall (mm)", "वर्षा (मिमी)")],
                        zip(months, vals)),
        "data": {"june": june, "july": july, "august": aug, "september": sep,
                 "threshold": threshold},
        "questions": questions,
    }


def _unit_school_garden(rng, uid):
    length = rng.randint(8, 20)
    width = rng.randint(4, length - 2)
    gate = rng.choice([1, 2])
    rate = rng.choice([40, 50, 60, 75, 80])
    fence = 2 * (length + width) - gate
    cost = rate * fence
    enough = rng.random() < 0.5
    budget = cost + rng.choice([100, 150, 200]) if enough else cost - rng.choice([100, 150, 200])
    verdict = T("Yes", "हाँ") if enough else T("No", "नहीं")

    def m(x):
        return T(f"{x} m", f"{x} मी")

    questions = [
        _mcq(f"{uid}_Q1", "employ",
             T("How many metres of fencing does the mason need?",
               "मिस्त्री को कितने मीटर बाड़ चाहिए?"),
             m(fence),
             [(m(2 * (length + width)), "PK",
               T("worked out the full distance around but "
                 "forgot to leave out the gate",
                 "पूरा परिमाप निकाला पर फाटक की लंबाई घटाना भूल गए")),
              (m(length * width), "INT",
               T("found the area of the garden instead of the "
                 "distance around it",
                 "बगीचे के चारों ओर की दूरी की जगह उसका क्षेत्रफल निकाल दिया")),
              (m(length + width - gate), "CF",
               T("believes the distance around a rectangle "
                 "is just length plus width",
                 "मानते हैं कि आयत का परिमाप केवल लंबाई और चौड़ाई का जोड़ होता है"))], rng),
        _mcq(f"{uid}_Q2", "reason",
             T(f"The school plans a second garden whose length and width are both twice as "
               f"long ({2 * length} m by {2 * width} m). How does the area of the new garden "
               f"compare with the area of this one?",
               f"स्कूल एक दूसरा बगीचा बनाना चाहता है जिसकी लंबाई और चौड़ाई दोनों दोगुनी हों "
               f"({2 * length} मी × {2 * width} मी)। नए बगीचे का क्षेत्रफल इस बगीचे के "
               f"क्षेत्रफल की तुलना में कितना है?"),
             T("It is 4 times as large.", "यह 4 गुना है।"),
             [(T("It is 2 times as large.", "यह 2 गुना है।"), "CF",
               T("assumes area grows in the same proportion "
                 "as the sides, a well-known misconception "
                 "about scaling",
                 "मानते हैं कि क्षेत्रफल भी भुजाओं के अनुपात में ही बढ़ता है, जो पैमाने के "
                 "बारे में एक जानी-मानी गलत धारणा है")),
              (T("It is 8 times as large.", "यह 8 गुना है।"), "INT",
               T("used the rule for scaling a volume, right "
                 "for a different kind of quantity",
                 "आयतन बढ़ाने वाला नियम लगाया, जो किसी दूसरी तरह की राशि के लिए सही है")),
              (T("It is the same, because it is the same shape.",
                 "यह उतना ही है, क्योंकि आकार वही है।"), "RF",
               T("no working link between the sides and the area",
                 "भुजाओं और क्षेत्रफल के बीच कोई काम का संबंध नहीं"))], rng),
        _open(f"{uid}_Q3", "interpret",
              T(f"The school has Rs {budget:,} for fencing. Is that enough? Show how you "
                f"decided.",
                f"स्कूल के पास बाड़ के लिए ₹{budget:,} हैं। क्या इतने पैसे काफी हैं? दिखाइए कि "
                f"आपने कैसे तय किया।"),
              [verdict],
              T(f"{verdict.en}. The fencing costs {rate} × {fence} = {_rs(cost)}, which is "
                f"{'less' if enough else 'more'} than Rs {budget:,}.",
                f"{verdict.hi}। बाड़ का खर्च {rate} × {fence} = {_rs_hi(cost)} है, जो "
                f"₹{budget:,} से {'कम' if enough else 'ज्यादा'} है।"),
              [(T(f"Multiplies Rs {rate} by the area ({length * width}) and gets "
                  f"{_rs(rate * length * width)}.",
                  f"₹{rate} को क्षेत्रफल ({length * width}) से गुणा करके "
                  f"{_rs_hi(rate * length * width)} पाते हैं।"), "INT",
                T("used the area instead of the fence length, the area and perimeter mix-up "
                  "again",
                  "बाड़ की लंबाई की जगह क्षेत्रफल लिया, फिर वही क्षेत्रफल और परिमाप की उलझन")),
               (T(f"Finds the cost of one side only, {_rs(rate * length)}.",
                  f"केवल एक भुजा का खर्च निकालते हैं, {_rs_hi(rate * length)}।"), "PK",
                T("started the calculation but did not cover the whole fence",
                  "हिसाब शुरू किया पर पूरी बाड़ का नहीं किया")),
               (T("Says yes or no with no calculation.",
                  "बिना हिसाब के हाँ या नहीं कह देते हैं।"), "RF",
                T("no link between the budget and the cost",
                  "बजट और खर्च के बीच कोई संबंध नहीं"))],
              partial_credit=T("Works out a cost with one slip (for example forgets the gate) "
                               "and gives the conclusion that matches that cost.",
                               "एक गलती के साथ खर्च निकालते हैं (जैसे फाटक भूल जाना) और उसी "
                               "खर्च के हिसाब से निष्कर्ष देते हैं।")),
    ]
    return {
        "unit_id": uid, "template": "school_garden",
        "title": T("Fencing the school garden", "स्कूल के बगीचे की बाड़"),
        "content": "space_and_shape", "context": "occupational", "emphasis": None,
        "stimulus": T(f"A mason is fencing a rectangular school garden that is {length} m long "
                      f"and {width} m wide. A gate {gate} m wide will be fitted in one side, "
                      f"and no fencing is needed where the gate goes. Fencing costs Rs {rate} "
                      f"per metre.",
                      f"एक मिस्त्री स्कूल के एक आयताकार बगीचे के चारों ओर बाड़ लगा रहा है। "
                      f"बगीचा {length} मी लंबा और {width} मी चौड़ा है। एक तरफ {gate} मी चौड़ा "
                      f"फाटक लगेगा, और फाटक वाली जगह पर बाड़ नहीं लगेगी। बाड़ का खर्च ₹{rate} "
                      f"प्रति मीटर है।"),
        "table": None,
        "data": {"length": length, "width": width, "gate": gate, "rate": rate,
                 "budget": budget},
        "questions": questions,
    }


def _unit_bus_journey(rng, uid):
    speed = rng.choice([30, 40, 45, 50, 60])
    drive = rng.choice([45, 75, 90, 105, 150])          # minutes, never a whole hour
    if (speed * drive) % 60:
        raise _Collision
    dist = speed * drive // 60
    stop = rng.choice([10, 15, 20])
    depart = rng.randint(6, 14) * 60 + rng.choice([0, 15, 30, 45])
    arrive = depart + drive + stop

    hours = drive / 60
    whole = drive // 60
    frac_digits = round((hours - whole) * 100)
    misread = whole * 60 + frac_digits                  # 1.5 h read as 1 h 50 min
    overall = 60 * dist / (drive + stop)

    questions = [
        _mcq(f"{uid}_Q1", "formulate",
             T(f"Which calculation gives the driving time, in hours, for the {dist} km?",
               f"{dist} किमी चलने का समय घंटों में कौन-सी गणना बताती है?"),
             f"{dist} ÷ {speed}",
             [(f"{speed} ÷ {dist}", "CF",
               T("turned the division upside down", "भाग को उल्टा कर दिया")),
              (f"{dist} × {speed}", "INT",
               T("used distance = speed × time, which answers a "
                 "different question",
                 "दूरी = चाल × समय लगाया, जो किसी दूसरे प्रश्न का उत्तर देता है")),
              (f"{dist} − {speed}", "RF",
               T("combined the two numbers with no link to how "
                 "speed works",
                 "दोनों संख्याओं को ऐसे मिलाया जिसका चाल से कोई संबंध नहीं"))], rng),
        _mcq(f"{uid}_Q2", "employ",
             T("At what time does the bus reach the district "
               "headquarters?",
               "बस जिला मुख्यालय कितने बजे पहुँचती है?"),
             _time(arrive),
             [(_time(depart + drive), "PK",
               T(f"forgot to add the {stop}-minute stop",
                 f"{stop} मिनट का ठहराव जोड़ना भूल गए")),
              (_time(depart + misread + stop), "CF",
               T(f"read {_num(hours)} hours as {whole} hours {frac_digits} minutes, treating "
                 f"the decimal part as minutes",
                 f"{_num(hours)} घंटे को {whole} घंटे {frac_digits} मिनट पढ़ा, दशमलव वाले "
                 f"भाग को मिनट मानकर")),
              (_time(depart + dist + stop), "RF",
               T("used the distance in kilometres as if "
                 "it were minutes",
                 "किलोमीटर में दी दूरी को मिनट मान लिया"))], rng),
        _open(f"{uid}_Q3", "interpret",
              T(f"A poster says: \"Our bus drives at {speed} km/h, so the whole trip, stop "
                f"included, averages {speed} km/h.\" Is the poster right? Explain.",
                f"एक पोस्टर पर लिखा है: \"हमारी बस {speed} किमी/घंटा से चलती है, इसलिए "
                f"ठहराव मिलाकर पूरी यात्रा की औसत चाल भी {speed} किमी/घंटा है।\" क्या पोस्टर "
                f"सही है? समझाइए।"),
              [T("No", "नहीं")],
              T(f"No. The whole trip takes {drive + stop} minutes for {dist} km, so the "
                f"average for the whole trip is about {overall:.1f} km/h, less than {speed} "
                f"km/h, because the bus covers no distance during the stop. An explanation "
                f"without the number also gets full credit.",
                f"नहीं। {dist} किमी की पूरी यात्रा में {drive + stop} मिनट लगते हैं, इसलिए "
                f"पूरी यात्रा की औसत चाल लगभग {overall:.1f} किमी/घंटा है, जो {speed} किमी/घंटा "
                f"से कम है, क्योंकि ठहराव के समय बस कोई दूरी तय नहीं करती। संख्या के बिना सही "
                f"स्पष्टीकरण को भी पूरे अंक मिलेंगे।"),
              [(T(f"Yes, because the bus drives at {speed} km/h.",
                  f"हाँ, क्योंकि बस {speed} किमी/घंटा से चलती है।"), "PK",
                T("knows what speed means but forgot that the stop adds time without "
                  "adding distance",
                  "चाल का अर्थ जानते हैं, पर भूल गए कि ठहराव समय बढ़ाता है, दूरी नहीं")),
               (T(f"No, the average is {_num(speed / 2)} km/h, halfway between {speed} and 0.",
                  f"नहीं, औसत {_num(speed / 2)} किमी/घंटा है, {speed} और 0 के ठीक बीच।"),
                "CF",
                T("averaged the two speeds instead of dividing total distance by total "
                  "time",
                  "कुल दूरी को कुल समय से भाग देने की जगह दोनों चालों का औसत ले लिया")),
               (T(f"Works out {dist} ÷ {speed} again and says yes.",
                  f"फिर से {dist} ÷ {speed} निकालकर हाँ कहते हैं।"), "INT",
                T("repeated the driving-time calculation, which answers a different "
                  "question",
                  "चलने के समय वाली गणना दोहराई, जो किसी दूसरे प्रश्न का उत्तर है"))]),
    ]
    return {
        "unit_id": uid, "template": "bus_journey",
        "title": T("Bus to the district headquarters", "जिला मुख्यालय की बस"),
        "content": "quantity", "context": "societal", "emphasis": None,
        "stimulus": T(f"A government bus leaves the village at {_clock(depart)} for the "
                      f"district headquarters, {dist} km away. It drives at an average speed "
                      f"of {speed} km/h and makes one stop of {stop} minutes on the way.",
                      f"एक सरकारी बस {_clock_hi(depart)} गाँव से {dist} किमी दूर जिला "
                      f"मुख्यालय के लिए निकलती है। वह {speed} किमी/घंटा की औसत चाल से चलती "
                      f"है और रास्ते में एक बार {stop} मिनट के लिए रुकती है।"),
        "table": None,
        "data": {"speed": speed, "distance": dist, "stop": stop, "depart": depart},
        "questions": questions,
    }


def _unit_dal_price(rng, uid):
    price = rng.choice([80, 100, 120, 125, 140, 150, 160, 200])
    pct = rng.choice([10, 20, 25])
    if (price * pct) % 100 or (price * (100 + pct) * (100 - pct)) % 10000:
        raise _Collision
    new = price + price * pct // 100
    if (new * pct) % 100:
        raise _Collision
    after_fall = price * (100 + pct) * (100 - pct) // 10000
    kilos = rng.randint(2, 6)
    money = new * kilos + rng.randint(1, new - 1)
    if money // price == kilos:
        raise _Collision

    def kg(x):
        return T(f"{x} kg", f"{x} किग्रा")

    questions = [
        _mcq(f"{uid}_Q1", "employ",
             T(f"What is the price of 1 kg of dal after the "
               f"{pct}% rise?",
               f"{pct}% बढ़ने के बाद 1 किग्रा दाल का भाव कितना है?"),
             _money(new),
             [(_money(price * pct // 100), "PK",
               T("found the increase but did not add it to "
                 "the old price",
                 "बढ़ोतरी निकाली पर उसे पुराने भाव में नहीं जोड़ा")),
              (_money(price + pct), "CF",
               T("added the percentage as if it were rupees",
                 "प्रतिशत को रुपये मानकर जोड़ दिया")),
              (_money(price - price * pct // 100), "INT",
               T("applied a decrease instead of an "
                 "increase",
                 "बढ़ोतरी की जगह कमी लगा दी"))], rng),
        _mcq(f"{uid}_Q2", "reason",
             T(f"The next month, the new price falls by {pct}%. Which statement about the "
               f"price after the fall is true?",
               f"अगले महीने नया भाव {pct}% घट जाता है। घटने के बाद के भाव के बारे में "
               f"कौन-सा कथन सही है?"),
             T(f"It is {_rs(after_fall)}, less than the original {_rs(price)}.",
               f"भाव {_rs_hi(after_fall)} है, जो शुरू के {_rs_hi(price)} से कम है।"),
             [(T(f"It is {_rs(price)}, the same as the original price.",
                 f"भाव {_rs_hi(price)} है, बिलकुल शुरू जितना।"), "CF",
               T("believes a rise and a fall of the same percentage cancel out, a common and "
                 "confident misconception",
                 "मानते हैं कि उतने ही प्रतिशत की बढ़ोतरी और कमी एक-दूसरे को बराबर कर देती "
                 "हैं, यह एक आम और पक्की गलत धारणा है")),
              (T(f"It is {_rs(new + new * pct // 100)}, even higher than before.",
                 f"भाव {_rs_hi(new + new * pct // 100)} है, पहले से भी ज्यादा।"), "INT",
               T("applied another rise instead of a fall",
                 "कमी की जगह एक और बढ़ोतरी लगा दी")),
              (T(f"It is {_rs(price - pct)}.", f"भाव {_rs_hi(price - pct)} है।"), "RF",
               T("subtracted the percentage from the "
                 "original price with no clear reason",
                 "बिना किसी साफ कारण के प्रतिशत को शुरू के भाव से घटा दिया"))],
             rng),
        _open(f"{uid}_Q3", "interpret",
              T(f"Rahul has Rs {money}. At the price after the rise ({_rs(new)} per kg), how "
                f"many whole kilograms of dal can he buy?",
                f"राहुल के पास ₹{money} हैं। बढ़े हुए भाव ({_rs_hi(new)} प्रति किग्रा) पर वह "
                f"पूरे कितने किलोग्राम दाल खरीद सकता है?"),
              [str(kilos)],
              T(f"{kilos} kg. {money} ÷ {new} = {money / new:.2f}, and he cannot pay for "
                f"another whole kilogram.",
                f"{kilos} किग्रा। {money} ÷ {new} = {money / new:.2f}, और वह एक और पूरा "
                f"किलोग्राम नहीं खरीद सकता।"),
              [(kg(kilos + 1), "CF",
                T("rounded up as usual, but he does not have enough "
                  "money for the last kilogram",
                  "आदत के अनुसार ऊपर पूर्णांकित किया, पर आखिरी किलोग्राम के लिए उसके पास "
                  "पैसे नहीं हैं")),
               (kg(f"{money / new:.2f}"), "PK",
                T("divided correctly but did not turn the "
                  "result into whole kilograms",
                  "भाग सही किया, पर उत्तर को पूरे किलोग्राम में नहीं बदला")),
               (kg(money // price), "INT",
                T(f"used the old price of {_rs(price)}",
                  f"पुराना भाव {_rs_hi(price)} ले लिया"))]),
    ]
    return {
        "unit_id": uid, "template": "dal_price",
        "title": T("The price of dal", "दाल का भाव"),
        "content": "quantity", "context": "personal", "emphasis": None,
        "stimulus": T(f"At the village shop, 1 kg of arhar dal cost {_rs(price)}. This month "
                      f"the price went up by {pct}%.",
                      f"गाँव की दुकान पर 1 किग्रा अरहर दाल का भाव {_rs_hi(price)} था। इस "
                      f"महीने भाव {pct}% बढ़ गया।"),
        "table": None,
        "data": {"price": price, "percent": pct, "money": money},
        "questions": questions,
    }


def _unit_travel_survey(rng, uid):
    total = rng.choice([40, 50])
    walk = rng.randint(math.ceil(total * 0.3), total // 2 - 1)
    step = 2 if total == 40 else 1                       # keeps the cycling % whole
    cycle = rng.choice([c for c in range(4, walk) if c % step == 0])
    bus = rng.randint(3, walk - 1)
    other = total - walk - cycle - bus
    if not 2 <= other < walk or len({walk, cycle, bus, other}) < 4:
        raise _Collision

    p_bus = Fraction(bus, total)
    questions = [
        _mcq(f"{uid}_Q1", "employ",
             T("What percentage of the class cycles to school?",
               "कक्षा के कितने प्रतिशत विद्यार्थी साइकिल से स्कूल आते हैं?"),
             f"{cycle * 100 // total}%",
             [(f"{cycle}%", "PK",
               T("used the number of cyclists as if it were a percentage",
                 "साइकिल वालों की संख्या को ही प्रतिशत मान लिया")),
              (f"{_num(walk * 100 / total)}%", "INT",
               T("worked out the percentage for "
                 "walkers, a different group",
                 "पैदल आने वालों का प्रतिशत निकाला, जो एक दूसरा समूह है")),
              (f"{_num(cycle * 100 / (walk + cycle), 1)}%", "CF",
               T("divided by the wrong total, only walkers and cyclists, instead of the whole "
                 "class",
                 "पूरी कक्षा की जगह गलत कुल से भाग दिया, केवल पैदल और साइकिल वालों से"))],
             rng),
        _mcq(f"{uid}_Q2", "employ",
             T("One student from the class is picked at random. What is the probability that "
               "this student comes by bus?",
               "कक्षा से एक विद्यार्थी को बिना देखे (यादृच्छिक रूप से) चुना जाता है। इस "
               "विद्यार्थी के बस से आने की प्रायिकता क्या है?"),
             _frac(p_bus),
             [("1/4", "CF",
               T("assumed the four ways of travelling are equally likely, "
                 "ignoring the counts",
                 "मान लिया कि आने के चारों तरीके बराबर संभव हैं, संख्याओं को अनदेखा करके")),
              (_frac(Fraction(bus, total - bus)), "INT",
               T("compared bus users with everyone "
                 "else (odds) instead of with the "
                 "whole class",
                 "बस वालों की तुलना पूरी कक्षा की जगह बाकी सब से की")),
              (_frac(Fraction(total - bus, total)), "PK",
               T("found the right total but counted "
                 "the students who do not take the "
                 "bus",
                 "कुल सही लिया, पर उन विद्यार्थियों को गिना जो बस से नहीं आते"))], rng),
        _open(f"{uid}_Q3", "reason",
              T("The headteacher looks at this table and says: \"Most students in our school "
                "walk to school.\" Give one reason why this conclusion might not be right.",
                "प्रधानाध्यापक यह तालिका देखकर कहते हैं: \"हमारे स्कूल के ज्यादातर विद्यार्थी "
                "पैदल आते हैं।\" एक कारण बताइए कि यह निष्कर्ष गलत क्यों हो सकता है।"),
              [T(f"Fewer than half of this class walk ({walk} of {total}).",
                 f"इस कक्षा में भी आधे से कम विद्यार्थी पैदल आते हैं ({total} में से {walk})।"),
               T("One class may not represent the whole school.",
                 "हो सकता है कि एक कक्षा पूरे स्कूल जैसी न हो।")],
              T(f"Either reason: fewer than half of this class walk ({walk} of {total}), so "
                f"'most' is not true even for this class; or one class may not represent the "
                f"whole school.",
                f"इनमें से कोई भी कारण: इस कक्षा में भी आधे से कम विद्यार्थी पैदल आते हैं "
                f"({total} में से {walk}), इसलिए 'ज्यादातर' इस कक्षा के लिए भी सही नहीं है; "
                f"या हो सकता है कि एक कक्षा पूरे स्कूल जैसी न हो।"),
              [(T(f"She is right, because walking has the biggest number ({walk}).",
                  f"वे सही हैं, क्योंकि पैदल वालों की संख्या ({walk}) सबसे ज्यादा है।"), "CF",
                T("believes the biggest group must be a majority, more than half",
                  "मानते हैं कि सबसे बड़ा समूह जरूर आधे से ज्यादा होगा")),
               (T("She is right, because many students like walking.",
                  "वे सही हैं, क्योंकि बहुत से विद्यार्थियों को पैदल चलना पसंद है।"), "RF",
                T("an opinion with no link to the data",
                  "आँकड़ों से बिना जुड़ी एक राय")),
               (T(f"She is wrong, because only {cycle} students cycle.",
                  f"वे गलत हैं, क्योंकि केवल {cycle} विद्यार्थी साइकिल से आते हैं।"), "INT",
                T("used a row of the table that does not bear on the claim",
                  "तालिका की वह पंक्ति ली जिसका इस दावे से कोई लेना-देना नहीं"))]),
    ]
    return {
        "unit_id": uid, "template": "travel_survey",
        "title": T("How we get to school", "हम स्कूल कैसे आते हैं"),
        "content": "uncertainty_and_data", "context": "societal", "emphasis": None,
        "stimulus": T(f"Class 8 asked all {total} of its students how they usually come to "
                      f"school. (These numbers are made up for practice.)",
                      f"कक्षा 8 ने अपने सभी {total} विद्यार्थियों से पूछा कि वे आमतौर पर स्कूल "
                      f"कैसे आते हैं। (ये संख्याएँ अभ्यास के लिए बनाई गई हैं।)"),
        "table": _table([T("How they come", "कैसे आते हैं"),
                         T("Number of students", "विद्यार्थियों की संख्या")],
                        [(T("Walk", "पैदल"), walk), (T("Bicycle", "साइकिल"), cycle),
                         (T("Bus", "बस"), bus), (T("Other", "अन्य"), other)]),
        "data": {"total": total, "walk": walk, "cycle": cycle, "bus": bus, "other": other},
        "questions": questions,
    }


def _unit_water_tank(rng, uid):
    lc = rng.choice([100, 150, 200, 250])
    wc = rng.choice([100, 120, 150, 200])
    hc = rng.choice([80, 100, 120, 150])
    cap = lc * wc * hc // 1000                           # 1 litre = 1000 cubic cm
    rate = rng.choice([20, 25, 40, 50])
    if cap % rate:
        raise _Collision
    minutes = cap // rate
    use = rng.choice([100, 120, 150, 180, 200, 250])
    half = cap / 2
    days = int(half // use)
    if days < 1 or half % use == 0 or int(cap // use) == days:
        raise _Collision

    def mins(x):
        return T(f"{x} minutes", f"{x} मिनट")

    def day_count(x):
        return T(f"{x} days", f"{x} दिन")

    L, W, H = _num(lc / 100), _num(wc / 100), _num(hc / 100)
    questions = [
        _mcq(f"{uid}_Q1", "formulate",
             T("Which calculation gives the number of litres the tank holds when full?",
               "भरी हुई टंकी में कितने लीटर पानी आता है, यह कौन-सी गणना बताती है?"),
             f"{L} × {W} × {H} × 1000",
             [(f"{L} × {W} × {H}", "PK",
               T("found the volume in cubic metres but did not "
                 "convert it to litres",
                 "आयतन घन मीटर में निकाला पर उसे लीटर में नहीं बदला")),
              (f"{L} × {W} × {H} × 100", "CF",
               T("used 1 cubic metre = 100 litres, a wrong "
                 "conversion factor",
                 "1 घन मीटर = 100 लीटर मान लिया, जो गलत रूपांतरण है")),
              (f"2 × ({L} × {W} + {W} × {H} + {L} × {H}) × 1000", "INT",
               T("used the area of the tank's faces instead of its volume",
                 "टंकी के आयतन की जगह उसके फलकों का क्षेत्रफल लिया"))], rng),
        _mcq(f"{uid}_Q2", "employ",
             T(f"The full tank holds {cap:,} litres. The pump fills it at {rate} litres per "
               f"minute. How long does it take to fill the empty tank?",
               f"भरी टंकी में {cap:,} लीटर पानी आता है। पंप इसे {rate} लीटर प्रति मिनट की दर "
               f"से भरता है। खाली टंकी भरने में कितना समय लगेगा?"),
             mins(minutes),
             [(mins(_num(minutes / 60)), "PK",
               T("changed the answer to hours but kept "
                 "the word minutes",
                 "उत्तर को घंटों में बदल दिया पर इकाई मिनट ही लिखी")),
              (mins(f"{cap * rate:,}"), "CF",
               T("multiplied the capacity by the rate "
                 "instead of dividing",
                 "क्षमता को दर से भाग देने की जगह गुणा कर दिया")),
              (mins(rate), "RF",
               T("repeated a number from the question with no "
                 "calculation",
                 "बिना गणना के प्रश्न की एक संख्या दोहरा दी"))], rng),
        _open(f"{uid}_Q3", "interpret",
              T(f"Today the tank is half full. The family uses {use} litres of water a day. "
                f"For how many full days will this water last?",
                f"आज टंकी आधी भरी है। परिवार हर दिन {use} लीटर पानी इस्तेमाल करता है। यह "
                f"पानी पूरे कितने दिन चलेगा?"),
              [str(days)],
              T(f"{days} days. Half the tank is {_num(half)} litres, and {_num(half)} ÷ {use} "
                f"= {half / use:.2f}, so the water lasts {days} full days.",
                f"{days} दिन। आधी टंकी में {_num(half)} लीटर पानी है, और {_num(half)} ÷ {use} "
                f"= {half / use:.2f}, इसलिए पानी पूरे {days} दिन चलेगा।"),
              [(day_count(int(cap // use)), "INT",
                T("used the full tank, the answer to a "
                  "different situation",
                  "पूरी भरी टंकी ली, जो किसी दूसरी स्थिति का उत्तर है")),
               (day_count(days + 1), "CF",
                T("rounded up, but the water runs out during the "
                  "last day",
                  "ऊपर पूर्णांकित किया, पर पानी आखिरी दिन के बीच में ही खत्म हो जाता है")),
               (day_count(f"{half / use:.2f}"), "PK",
                T("divided correctly but did not interpret the "
                  "answer as whole days",
                  "भाग सही किया पर उत्तर को पूरे दिनों में नहीं समझा"))]),
    ]
    return {
        "unit_id": uid, "template": "water_tank",
        "title": T("The rooftop water tank", "छत की पानी की टंकी"),
        "content": "space_and_shape", "context": "occupational", "emphasis": None,
        "stimulus": T(f"A plumber is fitting a water tank shaped like a cuboid on a house "
                      f"roof. Inside, it is {_metres(lc)} long, {_metres(wc)} wide and "
                      f"{_metres(hc)} high. 1 cubic metre holds 1,000 litres.",
                      f"एक प्लंबर घर की छत पर घनाभ के आकार की पानी की टंकी लगा रहा है। अंदर "
                      f"से यह {_metres_hi(lc)} लंबी, {_metres_hi(wc)} चौड़ी और {_metres_hi(hc)} "
                      f"ऊँची है। 1 घन मीटर में 1,000 लीटर पानी आता है।"),
        "table": None,
        "data": {"length_cm": lc, "width_cm": wc, "height_cm": hc, "pump_rate": rate,
                 "daily_use": use},
        "questions": questions,
    }


def _unit_growth(rng, uid):
    a0 = rng.choice([2, 3, 4, 5])
    b0 = rng.choice([40, 50, 60, 80, 100])
    k = rng.choice([10, 15, 20, 25])

    def a(h):
        return a0 * 2 ** h

    def b(h):
        return b0 + k * h

    overtake = next(h for h in range(1, 40) if a(h) > b(h))
    naive = next(h for h in range(1, 40) if a(h) > b0)
    if not 3 <= overtake <= 8 or naive in (overtake, overtake - 1):
        raise _Collision
    h1 = rng.choice([3, 4, 5])
    h3 = overtake + 2

    def thousand(x):
        return T(f"{x:,} thousand", f"{x:,} हजार")

    def after(x):
        return T(f"After {x} hours", f"{x} घंटे बाद")

    questions = [
        _mcq(f"{uid}_Q1", "employ",
             T(f"How many thousand cells does sample A have after "
               f"{h1} hours?",
               f"{h1} घंटे बाद नमूना A में कितनी हजार कोशिकाएँ होंगी?"),
             thousand(a(h1)),
             [(thousand(a0 * 2 * h1), "CF",
               T("treated doubling as multiplying by 2 "
                 "times the hours, linear thinking about "
                 "growth",
                 "दोगुना होने को घंटों के 2 गुने से गुणा करना समझा, यानी वृद्धि को सीधी "
                 "रेखा जैसा सोचा")),
              (thousand(a(h1 - 1)), "PK",
               T("stopped one doubling early", "एक बार दोगुना करना पहले ही रुक गए")),
              (thousand(b(h1)), "INT",
               T("worked out the count for sample B instead of "
                 "sample A",
                 "नमूना A की जगह नमूना B की गिनती निकाल दी"))], rng),
        _mcq(f"{uid}_Q2", "reason",
             T("After how many whole hours does sample A first have more cells than sample B?",
               "कितने पूरे घंटों के बाद नमूना A में पहली बार नमूना B से ज्यादा कोशिकाएँ "
               "होंगी?"),
             after(overtake),
             [(after(overtake - 1), "PK",
               T("stopped one hour early, before sample A "
                 "had overtaken",
                 "एक घंटा पहले रुक गए, जब नमूना A अभी आगे नहीं निकला था")),
              (T("Never, because sample B starts bigger.",
                 "कभी नहीं, क्योंकि नमूना B शुरू में बड़ा है।"), "CF",
               T("believes the sample that starts bigger stays ahead, ignoring how doubling "
                 "speeds up",
                 "मानते हैं कि जो नमूना शुरू में बड़ा है वह हमेशा आगे रहेगा, यह भूलकर कि "
                 "दोगुना होना कितना तेज होता जाता है")),
              (after(naive), "INT",
               T("compared sample A with sample B's starting "
                 "size instead of its size at that hour",
                 "नमूना A की तुलना उस घंटे के नमूना B से करने की जगह उसके शुरुआती आकार से "
                 "की"))], rng),
        _complex(f"{uid}_Q3", "interpret",
                 T("Is each statement true or false?", "हर कथन सही है या गलत?"),
                 [(T("Sample A gains the same number of cells every hour.",
                     "नमूना A में हर घंटे उतनी ही कोशिकाएँ जुड़ती हैं।"), False, "CF",
                   T("assumed all growth is linear",
                     "मान लिया कि हर वृद्धि एक जैसी (रैखिक) होती है")),
                  (T("Sample B gains the same number of cells every hour.",
                     "नमूना B में हर घंटे उतनी ही कोशिकाएँ जुड़ती हैं।"), True, "PK",
                   T(f"did not connect 'gains {k} thousand cells every hour' with a constant "
                     f"amount",
                     f"'हर घंटे {k} हजार कोशिकाएँ जुड़ती हैं' को एक समान मात्रा से नहीं "
                     f"जोड़ा")),
                  (T(f"After {h3} hours, sample A has more than twice as many cells as "
                     f"sample B.",
                     f"{h3} घंटे बाद नमूना A में नमूना B से दोगुनी से ज्यादा कोशिकाएँ हैं।"),
                   a(h3) > 2 * b(h3), "RF",
                   T("guessed without working out the two counts",
                     "दोनों गिनतियाँ निकाले बिना अनुमान लगाया"))]),
    ]
    return {
        "unit_id": uid, "template": "growth",
        "title": T("Two kinds of growth", "बढ़ने के दो तरीके"),
        "content": "change_and_relationships", "context": "scientific",
        "emphasis": T("growth phenomena", "वृद्धि की घटनाएँ"),
        "stimulus": T(f"In a computer model in the school lab, two samples of bacteria grow "
                      f"in different ways.\n\nSample A starts with {a0} thousand cells and "
                      f"doubles every hour.\n\nSample B starts with {b0} thousand cells and "
                      f"gains {k} thousand cells every hour.",
                      f"स्कूल की प्रयोगशाला के एक कंप्यूटर मॉडल में बैक्टीरिया के दो नमूने अलग-"
                      f"अलग तरीकों से बढ़ते हैं।\n\nनमूना A में शुरू में {a0} हजार कोशिकाएँ हैं "
                      f"और हर घंटे ये दोगुनी हो जाती हैं।\n\nनमूना B में शुरू में {b0} हजार "
                      f"कोशिकाएँ हैं और हर घंटे इसमें {k} हजार कोशिकाएँ जुड़ जाती हैं।"),
        "table": None,
        "data": {"a0": a0, "b0": b0, "k": k, "h1": h1, "h3": h3},
        "questions": questions,
    }


TEMPLATES = {
    "data_plans":    _unit_data_plans,
    "rainfall":      _unit_rainfall,
    "school_garden": _unit_school_garden,
    "bus_journey":   _unit_bus_journey,
    "dal_price":     _unit_dal_price,
    "travel_survey": _unit_travel_survey,
    "water_tank":    _unit_water_tank,
    "growth":        _unit_growth,
}

# content and context of each template, so filters work without building units
_TEMPLATE_TAGS = {
    "data_plans":    ("change_and_relationships", "personal"),
    "rainfall":      ("uncertainty_and_data", "scientific"),
    "school_garden": ("space_and_shape", "occupational"),
    "bus_journey":   ("quantity", "societal"),
    "dal_price":     ("quantity", "personal"),
    "travel_survey": ("uncertainty_and_data", "societal"),
    "water_tank":    ("space_and_shape", "occupational"),
    "growth":        ("change_and_relationships", "scientific"),
}


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

def validate_unit(unit):
    """Raise ValueError if a unit is malformed. Returns True otherwise."""
    for key in ("unit_id", "title", "content", "context", "stimulus", "questions"):
        if key not in unit:
            raise ValueError(f"unit is missing {key!r}")
    if unit["content"] not in CONTENT_CATEGORIES:
        raise ValueError(f"unknown content category {unit['content']!r}")
    if unit["context"] not in CONTEXTS:
        raise ValueError(f"unknown context {unit['context']!r}")
    if unit.get("lang", "en") not in LANGUAGES:
        raise ValueError(f"unknown language {unit.get('lang')!r}, available: {list(LANGUAGES)}")
    if not unit["questions"]:
        raise ValueError("a unit needs at least one question")
    for q in unit["questions"]:
        if q.get("process") not in PROCESSES:
            raise ValueError(f"{q.get('qid')}: unknown process {q.get('process')!r}")
        fmt = q.get("format")
        if fmt == "multiple_choice":
            texts = [o["text"] for o in q["options"]]
            if len(set(texts)) != len(texts):
                raise ValueError(f"{q['qid']}: two options are identical")
            if q["correct_answer"] not in texts:
                raise ValueError(f"{q['qid']}: the correct answer is not among the options")
            key_text = next(o["text"] for o in q["options"] if o["letter"] == q["key"])
            if key_text != q["correct_answer"]:
                raise ValueError(f"{q['qid']}: the key letter does not point at the answer")
            for d in q["distractors"]:
                _check_label(q["qid"], d)
        elif fmt == "complex_multiple_choice":
            for s in q["statements"]:
                if not isinstance(s["answer"], bool):
                    raise ValueError(f"{q['qid']}: statement answers must be True or False")
                _check_label(q["qid"], s["if_wrong"])
        elif fmt == "constructed_response":
            if not q["scoring"]["accepted_answers"] or not q["scoring"]["full_credit"]:
                raise ValueError(f"{q['qid']}: constructed response needs a scoring guide")
            for w in q["common_wrong_answers"]:
                _check_label(q["qid"], w)
        else:
            raise ValueError(f"{q.get('qid')}: unknown format {fmt!r}")
    return True


def _check_lang(lang):
    if lang not in LANGUAGES:
        raise ValueError(f"unknown language {lang!r}, available: {list(LANGUAGES)}")


def _check_label(qid, entry):
    if entry.get("error_type") not in ERROR_TYPES:
        raise ValueError(f"{qid}: error type {entry.get('error_type')!r} is not one of "
                         f"{ERROR_TYPES}")
    if not str(entry.get("note", "")).strip():
        raise ValueError(f"{qid}: every wrong answer needs a note on the thinking behind it")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def list_templates():
    """[(name, content, context), ...] for every unit template."""
    return [(name, *_TEMPLATE_TAGS[name]) for name in TEMPLATES]


def generate_unit(template, seed=None, unit_index=1, max_attempts=500, lang="en"):
    """
    Build one unit from a named template. Same template and seed, same unit.

    If a random draw would make two options identical, or an answer messy,
    the unit is redrawn from the same random stream, so the result is
    still fully determined by the seed.

    lang is "en" or "hi". The language never touches the random stream, so
    the Hindi and English units from one seed are the same unit: same
    numbers, same option order, same key.
    """
    if template not in TEMPLATES:
        raise ValueError(f"unknown template {template!r}, available: {sorted(TEMPLATES)}")
    _check_lang(lang)
    rng = random.Random(seed)
    uid = f"PISA_{template.upper()}_{unit_index:04d}"
    for _ in range(max_attempts):
        try:
            raw = TEMPLATES[template](rng, uid)
        except _Collision:
            continue
        unit = _localize(raw, lang)
        if lang != "en":
            unit["lang"] = lang
        validate_unit(unit)
        return unit
    raise RuntimeError(f"could not build a clean {template} unit in {max_attempts} draws")


def generate_units(n, content=None, context=None, templates=None, seed=None, lang="en"):
    """
    Build n units, cycling through the templates that match the filters so
    the set stays balanced. With more units than templates, templates come
    round again with fresh numbers.

    Args:
        n (int): number of units.
        content, context (list[str] | None): keep only templates in these
            content categories / contexts.
        templates (list[str] | None): or name the templates directly.
        seed (int | None): one seed for the whole set.
        lang (str): "en" or "hi". The same seed gives the same set in both.
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    for value, allowed, label in ((content, CONTENT_CATEGORIES, "content category"),
                                  (context, CONTEXTS, "context")):
        for v in value or []:
            if v not in allowed:
                raise ValueError(f"unknown {label} {v!r}, available: {sorted(allowed)}")
    names = list(templates) if templates else list(TEMPLATES)
    for name in names:
        if name not in TEMPLATES:
            raise ValueError(f"unknown template {name!r}, available: {sorted(TEMPLATES)}")
    names = [t for t in names
             if (not content or _TEMPLATE_TAGS[t][0] in content)
             and (not context or _TEMPLATE_TAGS[t][1] in context)]
    if not names:
        raise ValueError("no template matches those filters")
    master = random.Random(seed)
    _check_lang(lang)
    return [generate_unit(names[i % len(names)], seed=master.randrange(2 ** 31),
                          unit_index=i + 1, lang=lang) for i in range(n)]


def coverage(units):
    """How many questions fall in each content category, context, process and format."""
    out = {"content": {}, "context": {}, "process": {}, "format": {}}
    for u in units:
        for q in u["questions"]:
            for key, value in (("content", u["content"]), ("context", u["context"]),
                               ("process", q["process"]), ("format", q["format"])):
                out[key][value] = out[key].get(value, 0) + 1
    return out


def units_to_item_bank(units, class_level=8):
    """
    Turn the multiple-choice questions into the plain item format used by
    the rest of ConfusionMapper (run_session, generate-bank, validate), so
    a PISA unit can go straight into a CFI coding session. The stimulus is
    included in question_text, since a PISA question makes no sense without
    it.
    """
    bank = []
    for u in units:
        context = _plain_stimulus(u)
        for q in u["questions"]:
            if q["format"] != "multiple_choice":
                continue
            bank.append({
                "id":             q["qid"],
                "topic":          u["title"],
                "class_level":    class_level,
                "question_text":  f"{context}\n\n{q['prompt']}",
                "correct_answer": q["correct_answer"],
                "distractors":    [dict(d) for d in q["distractors"]],
            })
    return bank


def save_units(units, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(units, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def load_units(path):
    with open(path, "r", encoding="utf-8") as f:
        units = json.load(f)
    if not isinstance(units, list):
        raise ValueError(f"{path}: expected a list of units")
    for u in units:
        validate_unit(u)
    return units


# -----------------------------------------------------------------------------
# Booklet and answer key
# -----------------------------------------------------------------------------

def _md_table(table):
    lines = ["| " + " | ".join(table["columns"]) + " |",
             "|" + "---|" * len(table["columns"])]
    for row in table["rows"]:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return lines


def _plain_stimulus(unit):
    text = unit["stimulus"]
    if unit.get("table"):
        rows = [", ".join(f"{c}: {v}" for c, v in zip(unit["table"]["columns"], r))
                for r in unit["table"]["rows"]]
        text += "\n" + "\n".join(rows)
    return text


def _cfi(code, lang="en"):
    return f"{code}, {_names(lang)['cfi'][code]}"


BOOKLET_TITLE = {"en": "Maths in real life: practice units",
                 "hi": "रोजमर्रा की जिंदगी में गणित: अभ्यास इकाइयाँ"}

_BOOKLET = {
    "en": {"intro": "Read each situation carefully, then answer the questions about it. "
                    "Show your working where the question asks you to.",
           "unit": "Unit", "question": "Question",
           "tf_head": "| Statement | True | False |",
           "answer_line": "Answer: ____________________________________________",
           "working": "Working:"},
    "hi": {"intro": "हर स्थिति को ध्यान से पढ़िए, फिर उसके बारे में पूछे गए प्रश्नों के उत्तर "
                    "दीजिए। जहाँ प्रश्न में कहा गया हो, वहाँ अपना हल भी लिखिए।",
           "unit": "इकाई", "question": "प्रश्न",
           "tf_head": "| कथन | सही | गलत |",
           "answer_line": "उत्तर: ____________________________________________",
           "working": "हल:"},
}


def format_booklet(units, title=None):
    """The student booklet: situations and questions, no answers, no labels.
    The language follows the units."""
    lang = _lang_of(units)
    S, N = _BOOKLET[lang], _names(lang)
    title = title or BOOKLET_TITLE[lang]
    lines = [f"# {title}", "", S["intro"], "", f"*{N['disclaimer']}*", ""]
    if lang != "en":
        lines += [f"*{HINDI_DRAFT_NOTE[lang]}*", ""]
    for n, u in enumerate(units, start=1):
        lines += [f"## {S['unit']} {n}: {u['title']}", ""]
        lines += u["stimulus"].split("\n") + [""]
        if u.get("table"):
            lines += _md_table(u["table"]) + [""]
        for m, q in enumerate(u["questions"], start=1):
            lines += [f"**{S['question']} {n}.{m}.** {q['prompt']}", ""]
            if q["format"] == "multiple_choice":
                lines += [f"{o['letter']}. {o['text']}  " for o in q["options"]] + [""]
            elif q["format"] == "complex_multiple_choice":
                lines += [S["tf_head"], "|---|---|---|"]
                lines += [f"| {s['text']} | [ ] | [ ] |" for s in q["statements"]] + [""]
            else:
                lines += [S["answer_line"], "", S["working"], "", "", ""]
    return "\n".join(lines).rstrip() + "\n"


_KEY = {
    "en": {
        "heading": "{title}: teacher's key with CFI diagnosis",
        "explain": "Every wrong option, wrong true/false judgement and common wrong written "
                   "answer below is labelled with a Confusion Fingerprint Index category: "
                   "RF (Recall Failure), PK (Partial Knowledge), CF (Confabulation, a confident "
                   "misconception), INT (Interference, the right answer to a different "
                   "question). Use the labels to decide what to reteach, not just who got it "
                   "wrong.",
        "covers": "## What this set covers", "cov_head": "| Dimension | Questions |",
        "dims": {"content": "Content", "context": "Context", "process": "Process",
                 "format": "Format"},
        "context_word": "{name} context", "emphasis": ", PISA 2022 emphasis on {e}",
        "unit_id": "*{tag}. Unit ID {uid}.*", "unit": "Unit", "question": "Question",
        "answer": "**Answer: {key}** ({text})",
        "mc_head": "| If a child picks | Answer | What it suggests |",
        "tf_head": "| Statement | Answer | If a child gets it wrong |",
        "true": "True", "false": "False",
        "tf_full": "Full credit for all statements right.",
        "full": "**Full credit:**", "partial": "**Partial credit:**", "none": "**No credit:**",
        "cw_head": "| Common wrong answer | What it suggests |",
    },
    "hi": {
        "heading": "{title} (शिक्षक के लिए उत्तर कुंजी, CFI निदान के साथ)",
        "explain": "नीचे हर गलत विकल्प, सही/गलत वाले हर गलत निर्णय और हर आम गलत लिखित उत्तर "
                   "पर Confusion Fingerprint Index (CFI) की एक श्रेणी लिखी है: RF (याद न "
                   "होना), PK (अधूरी समझ), CF (पक्की गलत धारणा, यानी पूरे विश्वास वाली गलत "
                   "समझ), INT (दूसरे विषय का घालमेल, यानी किसी दूसरे प्रश्न का सही उत्तर)। इन "
                   "श्रेणियों से तय कीजिए कि क्या दोबारा पढ़ाना है, केवल यह नहीं कि किसका "
                   "उत्तर गलत था।",
        "covers": "## यह सेट किन चीजों को शामिल करता है", "cov_head": "| आयाम | प्रश्न |",
        "dims": {"content": "विषय-वस्तु", "context": "संदर्भ", "process": "प्रक्रिया",
                 "format": "प्रारूप"},
        "context_word": "{name} संदर्भ", "emphasis": ", PISA 2022 में विशेष ध्यान: {e}",
        "unit_id": "*{tag}। इकाई ID {uid}।*", "unit": "इकाई", "question": "प्रश्न",
        "answer": "**उत्तर: {key}** ({text})",
        "mc_head": "| अगर बच्चा चुने | उत्तर | इससे क्या पता चलता है |",
        "tf_head": "| कथन | उत्तर | अगर बच्चा गलत करे |",
        "true": "सही", "false": "गलत",
        "tf_full": "सभी कथन सही होने पर ही पूरे अंक।",
        "full": "**पूरे अंक:**", "partial": "**आंशिक अंक:**", "none": "**कोई अंक नहीं:**",
        "cw_head": "| आम गलत उत्तर | इससे क्या पता चलता है |",
    },
}


def format_answer_key(units, title=None):
    """
    The teacher's key. For every question: the answer, and for every wrong
    answer, the CFI category and what a child who gave it probably thinks.
    Pass the same title as the booklet it goes with. The language follows
    the units.
    """
    lang = _lang_of(units)
    K, N = _KEY[lang], _names(lang)
    title = title or BOOKLET_TITLE[lang]
    cov = coverage(units)
    lines = ["# " + K["heading"].format(title=title), "", f"*{N['disclaimer']}*", ""]
    if lang != "en":
        lines += [f"*{HINDI_DRAFT_NOTE[lang]}*", ""]
    lines += [K["explain"], "", K["covers"], "", K["cov_head"], "|---|---|"]
    for dim in ("content", "context", "process", "format"):
        names = N[dim]
        parts = [f"{names[k]} {v}" for k, v in sorted(cov[dim].items())]
        lines.append(f"| {K['dims'][dim]} | {', '.join(parts)} |")
    lines.append("")

    for n, u in enumerate(units, start=1):
        tag = f"{N['content'][u['content']]}, " + \
              K["context_word"].format(name=N["context"][u["context"]])
        if u.get("emphasis"):
            tag += K["emphasis"].format(e=u["emphasis"])
        lines += [f"## {K['unit']} {n}: {u['title']}", "",
                  K["unit_id"].format(tag=tag, uid=u["unit_id"]), ""]
        for m, q in enumerate(u["questions"], start=1):
            fmt_name = N["format"][q["format"]]
            if lang == "en":
                fmt_name = fmt_name.lower()
            lines += [f"### {K['question']} {n}.{m} ({N['process'][q['process']]}, "
                      f"{fmt_name})", ""]
            if q["format"] == "multiple_choice":
                lines += [K["answer"].format(key=q["key"], text=q["correct_answer"]), "",
                          K["mc_head"], "|---|---|---|"]
                by_text = {d["option"]: d for d in q["distractors"]}
                for o in q["options"]:
                    if o["text"] in by_text:
                        d = by_text[o["text"]]
                        lines.append(f"| {o['letter']} | {o['text']} | "
                                     f"{_cfi(d['error_type'], lang)}: {d['note']} |")
                lines.append("")
            elif q["format"] == "complex_multiple_choice":
                lines += [K["tf_head"], "|---|---|---|"]
                for s in q["statements"]:
                    w = s["if_wrong"]
                    lines.append(f"| {s['text']} | {K['true'] if s['answer'] else K['false']} | "
                                 f"{_cfi(w['error_type'], lang)}: {w['note']} |")
                lines += ["", K["tf_full"], ""]
            else:
                sc = q["scoring"]
                lines += [f"{K['full']} {sc['full_credit']}", ""]
                if sc.get("partial_credit"):
                    lines += [f"{K['partial']} {sc['partial_credit']}", ""]
                lines += [f"{K['none']} {sc['no_credit']}", "",
                          K["cw_head"], "|---|---|"]
                for w in q["common_wrong_answers"]:
                    lines.append(f"| {w['answer']} | {_cfi(w['error_type'], lang)}: "
                                 f"{w['note']} |")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# -----------------------------------------------------------------------------
# Scoring a class
# -----------------------------------------------------------------------------
#
# A worksheet is only half the job. The other half is the teacher sitting
# with thirty answer sheets and deciding what to teach on Monday. So the
# teacher types (or the web page collects) one row per child, and this turns
# it into a short list of the misconceptions that came up most, plus each
# child's Confusion Fingerprint Index for anyone using this in research.
#
# How answers are written, one cell per question:
#   multiple choice          a letter: A, B, C or D
#   true/false rows          one letter per row, in order: for example TFT
#   written answers          full, partial, none, or the CFI code of the
#                            common wrong answer it matched: RF, PK, CF, INT
#   blank cell               no response
#
# Points: 1 for a multiple-choice question, 1 for a true/false question with
# every row right, and for a written answer 2 for full credit and 1 for
# partial credit where the scoring guide has a partial-credit level,
# otherwise 1 for full credit.
#
# The CFI indices use the definitions already in this package:
#   CFI-CF  = CF errors / all diagnosed errors
#   CFI-INT = INT errors / (INT + RF errors)
#   CFI-RF  = RF errors / all diagnosed errors
# An index is None when its denominator is zero.

WRITTEN_CODES = ("full", "partial", "none") + tuple(c.lower() for c in ERROR_TYPES)

RETEACH_HINTS = {
    "RF":  "There is little to build on yet. Reteach the idea from the start with a "
           "concrete example before giving more practice.",
    "PK":  "The direction is right but steps are missing. A short worked example or a "
           "checklist of the steps usually closes the gap.",
    "CF":  "A confident wrong belief. More practice alone will not shift it. Show a case "
           "where the belief gives an obviously wrong answer and talk it through.",
    "INT": "An idea from a neighbouring topic is getting in the way. Put the two ideas "
           "side by side and contrast when each one applies.",
}

RETEACH_HINTS_HI = {
    "RF":  "अभी आगे बढ़ाने लायक आधार कम है। और अभ्यास देने से पहले किसी ठोस उदाहरण के साथ "
           "विचार को शुरू से दोबारा पढ़ाइए।",
    "PK":  "दिशा सही है पर कुछ चरण छूट रहे हैं। एक छोटा हल किया हुआ उदाहरण या चरणों की एक "
           "सूची आमतौर पर यह कमी पूरी कर देती है।",
    "CF":  "एक पक्की गलत धारणा। केवल और अभ्यास से यह नहीं बदलेगी। ऐसा उदाहरण दिखाइए जिसमें "
           "यह धारणा साफ-साफ गलत उत्तर देती है, और उस पर बात कीजिए।",
    "INT": "पास के किसी विषय का विचार बीच में आ रहा है। दोनों विचारों को साथ रखिए और "
           "दिखाइए कि कौन-सा कब लागू होता है।",
}

# How a wrong answer is described in the report. The codes on the answer
# sheet (A to D, T and F, full, partial, none, RF, PK, CF, INT) stay the same
# in both languages, so one sheet works for a class that mixes the two.
_ANSWER_WORDS = {
    "en": {"option": "option {a}", "row": "row {k} marked {tf}", "true": "True",
           "false": "False", "written": "written answer coded {code}",
           "matched": "matched a common wrong answer"},
    "hi": {"option": "विकल्प {a}", "row": "पंक्ति {k} को '{tf}' बताया", "true": "सही",
           "false": "गलत", "written": "लिखित उत्तर, कोड {code}",
           "matched": "एक आम गलत उत्तर से मेल खाया"},
}


def question_labels(units):
    """[("Q1.1", unit, question), ...] in booklet order."""
    return [(f"Q{n}.{m}", u, q) for n, u in enumerate(units, start=1)
            for m, q in enumerate(u["questions"], start=1)]


def response_sheet_csv(units, n_students=30):
    """A blank answer sheet as CSV text: student_id, then one column per question."""
    labels = [lab for lab, _, _ in question_labels(units)]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["student_id"] + labels)
    for i in range(1, n_students + 1):
        w.writerow([f"S{i:02d}"] + [""] * len(labels))
    return out.getvalue()


def load_responses_csv(path):
    """Read a filled-in answer sheet. Rows with no student_id are skipped."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "student_id" not in reader.fieldnames:
            raise ValueError(f"{path}: the first column must be student_id")
        return [row for row in reader if (row.get("student_id") or "").strip()]


def _parse_answer(cell, label, q):
    """Return None for blank, or the normalised answer. Raise on nonsense."""
    raw = "".join(str(cell or "").split()).upper()
    if not raw:
        return None
    fmt = q["format"]
    if fmt == "multiple_choice":
        letters = [o["letter"] for o in q["options"]]
        if raw not in letters:
            raise ValueError(f"{label}: {cell!r} is not one of {', '.join(letters)}")
        return raw
    if fmt == "complex_multiple_choice":
        n = len(q["statements"])
        if len(raw) != n or any(c not in "TF" for c in raw):
            raise ValueError(f"{label}: {cell!r} should be {n} letters, T or F, one per "
                             f"row, for example {('TFT' * n)[:n]}")
        return raw
    code = raw.lower()
    if code not in WRITTEN_CODES:
        raise ValueError(f"{label}: {cell!r} should be full, partial, none, RF, PK, CF or INT")
    if code == "partial" and not q["scoring"].get("partial_credit"):
        raise ValueError(f"{label}: this question has no partial-credit level")
    return code


def _max_points(q):
    if q["format"] == "constructed_response" and q["scoring"].get("partial_credit"):
        return 2
    return 1


def _cfi_indices(errors):
    total = sum(errors.values())
    return {
        "CFI-CF":  errors["CF"] / total if total else None,
        "CFI-INT": errors["INT"] / (errors["INT"] + errors["RF"])
                   if errors["INT"] + errors["RF"] else None,
        "CFI-RF":  errors["RF"] / total if total else None,
    }


def score_responses(units, responses):
    """
    Score a class.

    Args:
        units (list[dict]): the units the class sat, in booklet order.
        responses (list[dict]): one dict per child, with "student_id" and a
            key per question label ("Q1.1", "Q1.2", ...). Missing keys and
            blank cells count as no response. A row with no answers at all
            is skipped, the child was probably absent or not entered yet.

    Returns:
        dict with students, questions, misconceptions (every wrong answer
        given, most common first), class_errors and class_cfi.
    """
    labels = question_labels(units)
    if not responses:
        raise ValueError("no students to score")
    lang = _lang_of(units)
    W = _ANSWER_WORDS[lang]
    max_score = sum(_max_points(q) for _, _, q in labels)

    question_rows = []
    tallies = []          # per question: answer -> count of wrong answers
    for idx, (label, u, q) in enumerate(labels):
        question_rows.append({"label": label, "qid": q["qid"], "unit_title": u["title"],
                              "format": q["format"], "n_answered": 0, "n_full": 0})
        tallies.append({})

    students, seen = [], set()
    class_errors = {c: 0 for c in ERROR_TYPES}
    for row in responses:
        sid = str(row.get("student_id", "")).strip()
        if not sid:
            continue
        if all(not str(row.get(label) or "").strip() for label, _, _ in labels):
            continue          # no answers at all: absent, or not entered yet
        if sid in seen:
            raise ValueError(f"student_id {sid!r} appears twice")
        seen.add(sid)
        score, errors = 0, {c: 0 for c in ERROR_TYPES}
        unclassified = no_response = 0
        for idx, (label, u, q) in enumerate(labels):
            try:
                ans = _parse_answer(row.get(label), label, q)
            except ValueError as e:
                raise ValueError(f"student {sid}, {e}")
            if ans is None:
                no_response += 1
                continue
            qr = question_rows[idx]
            qr["n_answered"] += 1
            fmt = q["format"]
            if fmt == "multiple_choice":
                if ans == q["key"]:
                    score += 1
                    qr["n_full"] += 1
                    continue
                text = next(o["text"] for o in q["options"] if o["letter"] == ans)
                d = next(d for d in q["distractors"] if d["option"] == text)
                errors[d["error_type"]] += 1
                key = (W["option"].format(a=ans), text, d["error_type"], d["note"])
                tallies[idx][key] = tallies[idx].get(key, 0) + 1
            elif fmt == "complex_multiple_choice":
                all_right = True
                for k, s in enumerate(q["statements"]):
                    if (ans[k] == "T") != s["answer"]:
                        all_right = False
                        w = s["if_wrong"]
                        errors[w["error_type"]] += 1
                        tf = W["true"] if ans[k] == "T" else W["false"]
                        key = (W["row"].format(k=k + 1, tf=tf),
                               s["text"], w["error_type"], w["note"])
                        tallies[idx][key] = tallies[idx].get(key, 0) + 1
                if all_right:
                    score += 1
                    qr["n_full"] += 1
            else:
                if ans == "full":
                    score += _max_points(q)
                    qr["n_full"] += 1
                elif ans == "partial":
                    score += 1
                elif ans == "none":
                    unclassified += 1
                else:
                    code = ans.upper()
                    errors[code] += 1
                    match = next((w for w in q["common_wrong_answers"]
                                  if w["error_type"] == code), None)
                    key = (W["written"].format(code=code),
                           match["answer"] if match else "",
                           code,
                           match["note"] if match else W["matched"])
                    tallies[idx][key] = tallies[idx].get(key, 0) + 1
        for c in ERROR_TYPES:
            class_errors[c] += errors[c]
        top = max(errors.values())
        leaders = [c for c in ERROR_TYPES if errors[c] == top]
        students.append({
            "student_id": sid, "score": score, "max_score": max_score,
            "errors": errors, "unclassified_wrong": unclassified,
            "no_response": no_response, "cfi": _cfi_indices(errors),
            "dominant_error": (leaders[0] if top and len(leaders) == 1
                               else ("mixed" if top else None)),
        })
    if not students:
        raise ValueError("no students to score")

    misconceptions = []
    for idx, (label, u, q) in enumerate(labels):
        wrong = sorted(({"answer": a, "detail": d, "error_type": e, "note": n, "count": c}
                        for (a, d, e, n), c in tallies[idx].items()),
                       key=lambda w: (-w["count"], w["answer"]))
        question_rows[idx]["wrong"] = wrong
        for w in wrong:
            misconceptions.append(dict(w, label=label, order=idx, prompt=q["prompt"]))
    misconceptions.sort(key=lambda m: (-m["count"], m["order"], m["answer"]))

    result = {
        "n_students":     len(students),
        "max_score":      max_score,
        "mean_score":     sum(s["score"] for s in students) / len(students),
        "students":       students,
        "questions":      question_rows,
        "misconceptions": misconceptions,
        "class_errors":   class_errors,
        "class_cfi":      _cfi_indices(class_errors),
    }
    if lang != "en":
        result["lang"] = lang
    return result


def _pct(x, lang="en"):
    if x is None:
        return "लागू नहीं" if lang == "hi" else "n/a"
    return f"{x * 100:.0f}%"


REPORT_TITLE = {"en": "Class report: what to reteach first",
                "hi": "कक्षा रिपोर्ट: पहले क्या दोबारा पढ़ाएँ"}

_REPORT = {
    "en": {
        "summary": "{n} student{s}. Average score {mean} out of {max}.",
        "first": "## What to reteach first",
        "none": "No diagnosed wrong answers. Either the class did very well, or the "
                "answers have not been entered yet.",
        "item": "**{label}, {answer}{what}: {count} of {n} students, {name}.** {note}.",
        "profile": "## The class's error profile",
        "profile_head": "| Type | Wrong answers | What usually helps |",
        "suggest": "These are suggestions, you know your class better than any table does.",
        "byq": "## Question by question",
        "byq_head": "| Question | Answered | Fully right | Most common wrong answer |",
        "bys": "## Student by student",
        "bys_head": "| Student | Score | RF | PK | CF | INT | Most common error |",
        "mixed": "mixed",
        "research": "## For researchers",
        "research_text": "Class Confusion Fingerprint Index: CFI-CF {cf}, CFI-INT {int}, "
                         "CFI-RF {rf}. Per-student values are in the JSON output of "
                         "`confusion-mapper pisa-score`. CFI-CF is CF errors over all "
                         "diagnosed errors, CFI-INT is INT over INT plus RF, CFI-RF is RF "
                         "over all diagnosed errors. The labels come from the item "
                         "templates, decided before any child answered, not from coding "
                         "the answers afterwards.",
    },
    "hi": {
        "summary": "{n} विद्यार्थी। औसत अंक {max} में से {mean}।",
        "first": "## पहले क्या दोबारा पढ़ाएँ",
        "none": "कोई निदान किया हुआ गलत उत्तर नहीं है। या तो कक्षा ने बहुत अच्छा किया, या "
                "उत्तर अभी दर्ज नहीं हुए हैं।",
        "item": "**{label}, {answer}{what}: {n} में से {count} विद्यार्थी, {name}।** {note}।",
        "profile": "## कक्षा की गलतियों की तस्वीर",
        "profile_head": "| प्रकार | गलत उत्तर | आमतौर पर क्या मदद करता है |",
        "suggest": "ये केवल सुझाव हैं। अपनी कक्षा को आप किसी भी तालिका से बेहतर जानते हैं।",
        "byq": "## प्रश्न-दर-प्रश्न",
        "byq_head": "| प्रश्न | उत्तर दिए | पूरी तरह सही | सबसे आम गलत उत्तर |",
        "bys": "## विद्यार्थी-दर-विद्यार्थी",
        "bys_head": "| विद्यार्थी | अंक | RF | PK | CF | INT | सबसे आम गलती |",
        "mixed": "मिली-जुली",
        "research": "## शोधकर्ताओं के लिए",
        "research_text": "कक्षा का Confusion Fingerprint Index: CFI-CF {cf}, CFI-INT {int}, "
                         "CFI-RF {rf}। हर विद्यार्थी के मान `confusion-mapper pisa-score` के "
                         "JSON आउटपुट में हैं। CFI-CF यानी सभी निदान की गई गलतियों में CF का "
                         "हिस्सा, CFI-INT यानी INT और RF को मिलाकर उनमें INT का हिस्सा, CFI-RF "
                         "यानी सभी निदान की गई गलतियों में RF का हिस्सा। ये श्रेणियाँ प्रश्नों के "
                         "साँचों में किसी भी बच्चे के उत्तर देने से पहले तय की गई थीं, उत्तरों "
                         "को बाद में कोड करके नहीं।",
    },
}


def _sentence(note, lang):
    """English notes start lower case in the key and become a sentence here."""
    return note[0].upper() + note[1:] if lang == "en" else note


def format_class_report(result, top=5, title=None):
    """A teacher-facing Markdown report from score_responses(). The language
    follows the units that were scored."""
    r = result
    lang = r.get("lang", "en")
    R, N = _REPORT[lang], _names(lang)
    title = title or REPORT_TITLE[lang]
    lines = [f"# {title}", "",
             R["summary"].format(n=r["n_students"], s="" if r["n_students"] == 1 else "s",
                                 mean=f"{r['mean_score']:.1f}", max=r["max_score"]), ""]

    lines += [R["first"], ""]
    if not r["misconceptions"]:
        lines += [R["none"], ""]
    for m in r["misconceptions"][:top]:
        what = f" ({m['detail']})" if m["detail"] else ""
        lines += [R["item"].format(label=m["label"], answer=m["answer"], what=what,
                                   count=m["count"], n=r["n_students"],
                                   name=_cfi_name(m["error_type"], lang),
                                   note=_sentence(m["note"], lang)), ""]

    lines += [R["profile"], "", R["profile_head"], "|---|---|---|"]
    for c in ERROR_TYPES:
        lines.append(f"| {_cfi_name(c, lang)} | {r['class_errors'][c]} | {N['hints'][c]} |")
    lines += ["", R["suggest"], ""]

    lines += [R["byq"], "", R["byq_head"], "|---|---|---|---|"]
    for qr in r["questions"]:
        common = (f"{qr['wrong'][0]['answer']} ({qr['wrong'][0]['error_type']}, "
                  f"{qr['wrong'][0]['count']})" if qr["wrong"] else "")
        right = (_pct(qr["n_full"] / qr["n_answered"], lang) if qr["n_answered"]
                 else _pct(None, lang))
        lines.append(f"| {qr['label']} {qr['unit_title']} | {qr['n_answered']} | {right} | "
                     f"{common} |")
    lines.append("")

    lines += [R["bys"], "", R["bys_head"], "|---|---|---|---|---|---|---|"]
    for s in r["students"]:
        e = s["errors"]
        dom = R["mixed"] if s["dominant_error"] == "mixed" else (s["dominant_error"] or "")
        lines.append(f"| {s['student_id']} | {s['score']} / {s['max_score']} | {e['RF']} | "
                     f"{e['PK']} | {e['CF']} | {e['INT']} | {dom} |")
    lines.append("")

    cfi = r["class_cfi"]
    lines += [R["research"], "",
              R["research_text"].format(cf=_pct(cfi["CFI-CF"], lang),
                                        int=_pct(cfi["CFI-INT"], lang),
                                        rf=_pct(cfi["CFI-RF"], lang)), ""]
    if lang != "en":
        lines += [f"*{HINDI_DRAFT_NOTE[lang]}*", ""]
    return "\n".join(lines).rstrip() + "\n"


def _cfi_name(code, lang="en"):
    return f"{code}, {_names(lang)['cfi'][code]}"


# -----------------------------------------------------------------------------
# The pool behind the web page
# -----------------------------------------------------------------------------
#
# worksheets/index.html is a single offline page for teachers. It does not
# reimplement the templates. It carries a fixed pool of units built here, so
# this file stays the only place an answer is ever computed, and the tests
# that recompute every answer cover the page too.

WEB_POOL_PER_TEMPLATE = 25


def build_web_pool(per_template=WEB_POOL_PER_TEMPLATE):
    """Every template, per_template times, in English and in Hindi, plus the
    labels the page needs. units_hi[i] is units[i] in Hindi: same unit_id,
    same numbers, same answer letters."""
    units, units_hi = [], []
    for t_index, name in enumerate(TEMPLATES):
        for k in range(per_template):
            for lang, bucket in (("en", units), ("hi", units_hi)):
                u = generate_unit(name, seed=10000 + 1000 * t_index + k, unit_index=k + 1,
                                  lang=lang)
                u.pop("data", None)      # raw numbers are for the tests, not the page
                bucket.append(u)
    names_hi = _names("hi")
    return {
        "pool_format":    2,
        "template_order": list(TEMPLATES),
        "tags":           {t: list(_TEMPLATE_TAGS[t]) for t in TEMPLATES},
        "content_names":  CONTENT_CATEGORIES,
        "context_names":  CONTEXTS,
        "process_names":  PROCESSES,
        "format_names":   FORMATS,
        "cfi_names":      {c: TAXONOMY[c]["name"] for c in ERROR_TYPES},
        "error_types":    list(ERROR_TYPES),
        "reteach_hints":  RETEACH_HINTS,
        "disclaimer":     DISCLAIMER,
        "units":          units,
        "hi": {
            "content_names": names_hi["content"],
            "context_names": names_hi["context"],
            "process_names": names_hi["process"],
            "format_names":  names_hi["format"],
            "cfi_names":     names_hi["cfi"],
            "reteach_hints": names_hi["hints"],
            "disclaimer":    names_hi["disclaimer"],
            "draft_note":    HINDI_DRAFT_NOTE["hi"],
            "units":         units_hi,
        },
    }


def web_pool_json(pool=None):
    """The pool as compact JSON that is safe to put inside a <script> tag."""
    text = json.dumps(pool or build_web_pool(), ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/")


# -----------------------------------------------------------------------------
# Did the reteaching work?
# -----------------------------------------------------------------------------
#
# The worksheets page can make a follow-up set: the same unit templates, with
# new numbers, so children cannot just remember last week's answers. To see
# whether a misconception went down, mistakes are matched across the two
# rounds by template, question position and CFI type, not by the exact
# question, because the numbers in the question have changed on purpose.

def _type_rates(units, result):
    """{(template, position, type): {count, answered, title, note}}"""
    out = {}
    for idx, (label, unit, q) in enumerate(question_labels(units)):
        qr = result["questions"][idx]
        pos = int(label.split(".")[1])
        out.setdefault((unit["template"], pos, None), {
            "count": 0, "answered": qr["n_answered"], "title": unit["title"], "note": ""})
        for w in qr["wrong"]:
            key = (unit["template"], pos, w["error_type"])
            entry = out.setdefault(key, {"count": 0, "answered": qr["n_answered"],
                                         "title": unit["title"], "note": w["note"]})
            entry["count"] += w["count"]
    return out


def compare_rounds(units_before, result_before, units_after, result_after):
    """
    Compare two scored rounds. Returns rows for every mistake type seen in
    either round, on every question the two sets share (same template and
    position), with the share of answering children who made it before and
    after, and the class's errors per child by type.
    """
    before = _type_rates(units_before, result_before)
    after = _type_rates(units_after, result_after)
    shared = {(t, p) for (t, p, e) in before if e is None} & \
             {(t, p) for (t, p, e) in after if e is None}
    rows = []
    for (t, p) in shared:
        types = {e for (tt, pp, e) in list(before) + list(after)
                 if (tt, pp) == (t, p) and e is not None}
        for e in types:
            b = before.get((t, p, e))
            a = after.get((t, p, e))
            nb = before[(t, p, None)]["answered"]
            na = after[(t, p, None)]["answered"]
            cb = b["count"] if b else 0
            ca = a["count"] if a else 0
            rows.append({
                "template": t, "position": p, "error_type": e,
                "title": after[(t, p, None)]["title"],
                "note": (a or b)["note"],
                "before_count": cb, "before_answered": nb,
                "before_rate": cb / nb if nb else None,
                "after_count": ca, "after_answered": na,
                "after_rate": ca / na if na else None,
            })
    rows.sort(key=lambda r: (-(r["before_rate"] or 0), r["template"], r["position"],
                             r["error_type"]))
    per_child = {}
    for e in ERROR_TYPES:
        per_child[e] = {
            "before": result_before["class_errors"][e] / result_before["n_students"],
            "after": result_after["class_errors"][e] / result_after["n_students"],
        }
    out = {"rows": rows, "errors_per_child": per_child,
           "n_before": result_before["n_students"], "n_after": result_after["n_students"]}
    if result_after.get("lang", "en") != "en":
        out["lang"] = result_after["lang"]
    return out


COMPARISON_TITLE = {"en": "Before and after reteaching",
                    "hi": "दोबारा पढ़ाने से पहले और बाद में"}

_COMPARISON = {
    "en": {
        "intro": "{nb} children in the first round, {na} in the follow-up. Questions are "
                 "matched by unit and position, so the numbers in them differ on purpose.",
        "nothing": "The two sets share no questions, so there is nothing to compare.",
        "head": "| Question | Mistake | First round | Follow-up |",
        "question": "{title}, question {p}", "of": "{c} of {n}",
        "per_child": "## Mistakes per child, by type",
        "per_child_head": "| Type | First round | Follow-up |",
        "caution": "A drop is encouraging but not proof. The follow-up questions are new, "
                   "children may differ between rounds, and small classes vary a lot by "
                   "chance.",
    },
    "hi": {
        "intro": "पहले दौर में {nb} बच्चे, फॉलो-अप दौर में {na}। प्रश्न इकाई और क्रम से मिलाए "
                 "गए हैं, इसलिए उनकी संख्याएँ जानबूझकर अलग हैं।",
        "nothing": "दोनों सेटों में कोई साझा प्रश्न नहीं है, इसलिए तुलना के लिए कुछ नहीं है।",
        "head": "| प्रश्न | गलती | पहला दौर | फॉलो-अप |",
        "question": "{title}, प्रश्न {p}", "of": "{n} में से {c}",
        "per_child": "## हर बच्चे पर गलतियाँ, प्रकार के अनुसार",
        "per_child_head": "| प्रकार | पहला दौर | फॉलो-अप |",
        "caution": "गलतियों का घटना उत्साह बढ़ाता है, पर यह सबूत नहीं है। फॉलो-अप के प्रश्न "
                   "नए हैं, दोनों दौर के बच्चे अलग हो सकते हैं, और छोटी कक्षाओं में संयोग से "
                   "बहुत उतार-चढ़ाव होता है।",
    },
}


def format_comparison(cmp, title=None):
    lang = cmp.get("lang", "en")
    C = _COMPARISON[lang]
    title = title or COMPARISON_TITLE[lang]
    lines = [f"# {title}", "", C["intro"].format(nb=cmp["n_before"], na=cmp["n_after"]), ""]
    if not cmp["rows"]:
        lines += [C["nothing"], ""]
    else:
        lines += [C["head"], "|---|---|---|---|"]
        for r in cmp["rows"]:
            before = C["of"].format(c=r["before_count"], n=r["before_answered"])
            after = C["of"].format(c=r["after_count"], n=r["after_answered"])
            lines.append(
                f"| {C['question'].format(title=r['title'], p=r['position'])} | "
                f"{_cfi_name(r['error_type'], lang)}: {r['note']} | "
                f"{before} ({_pct(r['before_rate'], lang)}) | "
                f"{after} ({_pct(r['after_rate'], lang)}) |")
        lines.append("")
    lines += [C["per_child"], "", C["per_child_head"], "|---|---|---|"]
    for e in ERROR_TYPES:
        v = cmp["errors_per_child"][e]
        lines.append(f"| {_cfi_name(e, lang)} | {v['before']:.2f} | {v['after']:.2f} |")
    lines += ["", C["caution"], ""]
    return "\n".join(lines).rstrip() + "\n"


# -----------------------------------------------------------------------------
# Checking the Hindi
# -----------------------------------------------------------------------------
#
# A translation nobody has checked should not pretend to be finished. This
# writes every English sentence next to its Hindi, one template at a time,
# so a Hindi-medium maths teacher can read down the page and mark what
# sounds wrong. docs/hindi-review.md is made by this function.

def translation_pairs(template, seed=0):
    """Every (English, Hindi) text pair in one unit of a template, in order,
    without repeats."""
    if template not in TEMPLATES:
        raise ValueError(f"unknown template {template!r}, available: {sorted(TEMPLATES)}")
    rng = random.Random(seed)
    uid = f"PISA_{template.upper()}_0001"
    for _ in range(500):
        try:
            raw = TEMPLATES[template](rng, uid)
            break
        except _Collision:
            continue
    out, seen = [], set()

    def walk(obj):
        if isinstance(obj, T):
            if (obj.en, obj.hi) not in seen:
                seen.add((obj.en, obj.hi))
                out.append((obj.en, obj.hi))
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)
    walk(raw)
    return out


def _cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def format_translation_review(seed=0):
    """A Markdown sheet with every English text and its Hindi, for review."""
    lines = ["# Hindi translation: review sheet", "",
             "Every piece of text in the PISA-style units, in English and in the Hindi draft, "
             "side by side. The Hindi was written for Hindi-medium schools in Uttar Pradesh "
             "and has not yet been checked by a Hindi-medium maths teacher. If a line sounds "
             "wrong, stiff or too bookish for a Class 8 child, write a better version in the "
             "last column and send it back (an issue on GitHub, or the email in the README). "
             "Numbers come from one example unit per template; in real units they change, "
             "the words do not.", "",
             "Answer letters A to D and the answer-sheet codes (T, F, full, partial, none, RF, "
             "PK, CF, INT) stay in English on purpose, so one answer sheet works for a class "
             "that uses both languages. Amounts are written ₹270 in Hindi and Rs 270 in "
             "English, and times as सुबह 7:30 बजे, so rows that differ only in that are left "
             "out.", "",
             "This file is made by `confusion_mapper.pisa.format_translation_review()`. The "
             "words on the web page itself (buttons, headings) are in the `I18N` block of "
             "worksheets/index.html.", ""]
    for name in TEMPLATES:
        pairs = translation_pairs(name, seed)
        title = next((p for p in pairs), ("", ""))
        lines += [f"## {name}: {title[0]} / {title[1]}", "",
                  "| English | हिन्दी | Better Hindi? |", "|---|---|---|"]
        lines += [f"| {_cell(en)} | {_cell(hi)} | |" for en, hi in pairs
                  if any("\u0900" <= ch <= "\u097f" for ch in hi)]
        lines.append("")
    lines += ["## Names used in the key and the report", "",
              "| English | हिन्दी | Better Hindi? |", "|---|---|---|"]
    tables = [(CONTENT_CATEGORIES, CONTENT_CATEGORIES_HI), (PROCESSES, PROCESSES_HI),
              (CONTEXTS, CONTEXTS_HI), (FORMATS, FORMATS_HI),
              ({c: TAXONOMY[c]["name"] for c in ERROR_TYPES}, CFI_NAMES_HI),
              (RETEACH_HINTS, RETEACH_HINTS_HI)]
    for en_table, hi_table in tables:
        lines += [f"| {_cell(en_table[k])} | {_cell(hi_table[k])} | |" for k in en_table]
    lines += [f"| {_cell(DISCLAIMER)} | {_cell(DISCLAIMER_HI)} | |",
              f"| {_cell(BOOKLET_TITLE['en'])} | {_cell(BOOKLET_TITLE['hi'])} | |",
              f"| {_cell(REPORT_TITLE['en'])} | {_cell(REPORT_TITLE['hi'])} | |",
              f"| {_cell(COMPARISON_TITLE['en'])} | {_cell(COMPARISON_TITLE['hi'])} | |", ""]
    return "\n".join(lines).rstrip() + "\n"
