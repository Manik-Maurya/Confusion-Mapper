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


class _Collision(Exception):
    """Raised when a random draw makes two options identical. The unit is
    redrawn, so a student never sees the same answer twice in one list."""


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------

def _rs(x):
    if float(x).is_integer():
        return f"Rs {int(x):,}"
    return f"Rs {x:,.2f}"


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


def _frac(f):
    return f"{f.numerator}/{f.denominator}"


def _metres(cm):
    return _num(cm / 100) + " m"


# -----------------------------------------------------------------------------
# Question builders
# -----------------------------------------------------------------------------

def _mcq(qid, process, prompt, correct, distractors, rng):
    """distractors: list of (option, error_type, note)."""
    options = [correct] + [d[0] for d in distractors]
    if len(set(options)) != len(options) or any(not str(o).strip() for o in options):
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
            "no_credit": "Other responses, or no response.",
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
        wrong_plan = ("Plan B, because it has no monthly charge.", "CF",
                      "believes a plan with no fixed fee is always cheaper, without "
                      "checking the cost at this amount of data")
    else:
        wrong_plan = ("Plan A, because its rate per GB is lower.", "CF",
                      "believes the lower rate always wins, ignoring the fixed "
                      "monthly charge when little data is used")

    questions = [
        _mcq(f"{uid}_Q1", "employ",
             f"How much does Plan A cost in a month when the family uses {u1} GB?",
             _rs(fee + p * u1),
             [(_rs(p * u1), "PK", "multiplied the rate by the data used but left out "
                                  "the fixed monthly charge"),
              (_rs((fee + p) * u1), "CF", "charged the monthly fee again for every GB, "
                                          "treating the fixed charge as part of the rate"),
              (_rs(q * u1), "INT", "worked out the cost under Plan B, the right answer "
                                   "to a different question")], rng),
        _mcq(f"{uid}_Q2", "formulate",
             "Which expression gives the monthly cost of Plan A, in rupees, when x GB "
             "of data is used?",
             f"{fee} + {p}x",
             [(f"{p} + {fee}x", "CF", "swapped the fixed charge and the rate per GB"),
              (f"{q}x", "INT", "wrote the rule for Plan B instead of Plan A"),
              (f"{p}x", "PK", "kept the rate per GB but forgot the fixed monthly charge")],
             rng),
        _open(f"{uid}_Q3", "interpret",
              f"Next month Asha expects to use {u2} GB. Which plan should she choose to "
              f"pay less? Show the cost of both plans.",
              [f"Plan {cheaper}"],
              f"Plan {cheaper}, with both costs shown: Plan A {_rs(cost_a2)} and Plan B "
              f"{_rs(cost_b2)}, or another correct comparison of the two.",
              [wrong_plan,
               (f"Works out both plans for {u1} GB, the amount in Question 1.", "INT",
                f"answered for a different amount of data, not the {u2} GB asked about"),
               ("Works out the cost of one plan only and chooses it.", "PK",
                "started the comparison but did not finish it")],
              partial_credit=f"Plan {cheaper} with only one cost shown, or with a small "
                             f"slip in one cost that does not change the choice."),
    ]
    return {
        "unit_id": uid, "template": "data_plans", "title": "Mobile data plans",
        "content": "change_and_relationships", "context": "personal", "emphasis": None,
        "stimulus": (f"Asha's family is choosing a mobile data plan.\n\n"
                     f"Plan A costs Rs {fee} a month, plus Rs {p} for every GB of data used.\n\n"
                     f"Plan B has no monthly charge. It costs Rs {q} for every GB of data used."),
        "table": None,
        "data": {"fee": fee, "rate_a": p, "rate_b": q, "u1": u1, "u2": u2},
        "questions": questions,
    }


def _unit_rainfall(rng, uid):
    months = ["June", "July", "August", "September"]
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

    questions = [
        _mcq(f"{uid}_Q1", "interpret", "In which month did the club record the most rain?",
             first,
             [(second, "PK", "picked a month with a lot of rain but did not compare all "
                             "four values"),
              (third, "RF", "no clear link to the numbers in the table"),
              (fourth, "CF", "confidently picked the smallest value, mixing up 'most' "
                             "and 'least'")], rng),
        _mcq(f"{uid}_Q2", "employ",
             "What was the mean (average) monthly rainfall from June to September?",
             f"{mean} mm",
             [(f"{total} mm", "PK", "added the four months but did not divide by 4"),
              (f"{_num(median)} mm", "INT", "found the median, a different kind of average"),
              (f"{_num(midrange)} mm", "CF", "believes the average is halfway between the "
                                             "biggest and smallest values")], rng),
        _complex(f"{uid}_Q3", "reason",
                 "Is each statement true or false? Use the table.",
                 [("July had more than twice as much rain as June.", july > 2 * june, "PK",
                   "compared the two numbers without working out twice the June value"),
                  ("The rainfall went up every month from June to September.", False, "CF",
                   "assumed the monsoon keeps getting heavier, without checking each month"),
                  (f"Altogether, the club recorded more than {threshold} mm of rain in these "
                   f"four months.", claim_true, "RF",
                   "did not add up the four months")]),
    ]
    return {
        "unit_id": uid, "template": "rainfall", "title": "Monsoon rain gauge",
        "content": "uncertainty_and_data", "context": "scientific", "emphasis": None,
        "stimulus": ("The science club of a village school in Uttar Pradesh read its rain "
                     "gauge every morning during the monsoon and added up the rain for each "
                     "month. (These numbers are made up for practice.)"),
        "table": _table(["Month", "Rainfall (mm)"], zip(months, vals)),
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
    verdict = "Yes" if enough else "No"

    questions = [
        _mcq(f"{uid}_Q1", "employ", "How many metres of fencing does the mason need?",
             f"{fence} m",
             [(f"{2 * (length + width)} m", "PK", "worked out the full distance around but "
                                                 "forgot to leave out the gate"),
              (f"{length * width} m", "INT", "found the area of the garden instead of the "
                                             "distance around it"),
              (f"{length + width - gate} m", "CF", "believes the distance around a rectangle "
                                                   "is just length plus width")], rng),
        _mcq(f"{uid}_Q2", "reason",
             f"The school plans a second garden whose length and width are both twice as "
             f"long ({2 * length} m by {2 * width} m). How does the area of the new garden "
             f"compare with the area of this one?",
             "It is 4 times as large.",
             [("It is 2 times as large.", "CF", "assumes area grows in the same proportion "
                                                "as the sides, a well-known misconception "
                                                "about scaling"),
              ("It is 8 times as large.", "INT", "used the rule for scaling a volume, right "
                                                 "for a different kind of quantity"),
              ("It is the same, because it is the same shape.", "RF",
               "no working link between the sides and the area")], rng),
        _open(f"{uid}_Q3", "interpret",
              f"The school has Rs {budget:,} for fencing. Is that enough? Show how you "
              f"decided.",
              [verdict],
              f"{verdict}. The fencing costs {rate} × {fence} = {_rs(cost)}, which is "
              f"{'less' if enough else 'more'} than Rs {budget:,}.",
              [(f"Multiplies Rs {rate} by the area ({length * width}) and gets "
                f"{_rs(rate * length * width)}.", "INT",
                "used the area instead of the fence length, the area and perimeter mix-up "
                "again"),
               (f"Finds the cost of one side only, {_rs(rate * length)}.", "PK",
                "started the calculation but did not cover the whole fence"),
               ("Says yes or no with no calculation.", "RF",
                "no link between the budget and the cost")],
              partial_credit="Works out a cost with one slip (for example forgets the gate) "
                             "and gives the conclusion that matches that cost."),
    ]
    return {
        "unit_id": uid, "template": "school_garden", "title": "Fencing the school garden",
        "content": "space_and_shape", "context": "occupational", "emphasis": None,
        "stimulus": (f"A mason is fencing a rectangular school garden that is {length} m long "
                     f"and {width} m wide. A gate {gate} m wide will be fitted in one side, "
                     f"and no fencing is needed where the gate goes. Fencing costs Rs {rate} "
                     f"per metre."),
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
             f"Which calculation gives the driving time, in hours, for the {dist} km?",
             f"{dist} ÷ {speed}",
             [(f"{speed} ÷ {dist}", "CF", "turned the division upside down"),
              (f"{dist} × {speed}", "INT", "used distance = speed × time, which answers a "
                                           "different question"),
              (f"{dist} − {speed}", "RF", "combined the two numbers with no link to how "
                                          "speed works")], rng),
        _mcq(f"{uid}_Q2", "employ", "At what time does the bus reach the district "
                                    "headquarters?",
             _clock(arrive),
             [(_clock(depart + drive), "PK", f"forgot to add the {stop}-minute stop"),
              (_clock(depart + misread + stop), "CF",
               f"read {_num(hours)} hours as {whole} hours {frac_digits} minutes, treating "
               f"the decimal part as minutes"),
              (_clock(depart + dist + stop), "RF", "used the distance in kilometres as if "
                                                   "it were minutes")], rng),
        _open(f"{uid}_Q3", "interpret",
              f"A poster says: \"Our bus drives at {speed} km/h, so the whole trip, stop "
              f"included, averages {speed} km/h.\" Is the poster right? Explain.",
              ["No"],
              f"No. The whole trip takes {drive + stop} minutes for {dist} km, so the "
              f"average for the whole trip is about {overall:.1f} km/h, less than {speed} "
              f"km/h, because the bus covers no distance during the stop. An explanation "
              f"without the number also gets full credit.",
              [(f"Yes, because the bus drives at {speed} km/h.", "PK",
                "knows what speed means but forgot that the stop adds time without "
                "adding distance"),
               (f"No, the average is {_num(speed / 2)} km/h, halfway between {speed} and 0.",
                "CF", "averaged the two speeds instead of dividing total distance by total "
                      "time"),
               (f"Works out {dist} ÷ {speed} again and says yes.", "INT",
                "repeated the driving-time calculation, which answers a different "
                "question")]),
    ]
    return {
        "unit_id": uid, "template": "bus_journey", "title": "Bus to the district headquarters",
        "content": "quantity", "context": "societal", "emphasis": None,
        "stimulus": (f"A government bus leaves the village at {_clock(depart)} for the "
                     f"district headquarters, {dist} km away. It drives at an average speed "
                     f"of {speed} km/h and makes one stop of {stop} minutes on the way."),
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

    questions = [
        _mcq(f"{uid}_Q1", "employ", f"What is the price of 1 kg of dal after the "
                                    f"{pct}% rise?",
             _rs(new),
             [(_rs(price * pct // 100), "PK", "found the increase but did not add it to "
                                              "the old price"),
              (_rs(price + pct), "CF", "added the percentage as if it were rupees"),
              (_rs(price - price * pct // 100), "INT", "applied a decrease instead of an "
                                                       "increase")], rng),
        _mcq(f"{uid}_Q2", "reason",
             f"The next month, the new price falls by {pct}%. Which statement about the "
             f"price after the fall is true?",
             f"It is {_rs(after_fall)}, less than the original {_rs(price)}.",
             [(f"It is {_rs(price)}, the same as the original price.", "CF",
               "believes a rise and a fall of the same percentage cancel out, a common and "
               "confident misconception"),
              (f"It is {_rs(new + new * pct // 100)}, even higher than before.", "INT",
               "applied another rise instead of a fall"),
              (f"It is {_rs(price - pct)}.", "RF", "subtracted the percentage from the "
                                                   "original price with no clear reason")],
             rng),
        _open(f"{uid}_Q3", "interpret",
              f"Rahul has Rs {money}. At the price after the rise ({_rs(new)} per kg), how "
              f"many whole kilograms of dal can he buy?",
              [str(kilos)],
              f"{kilos} kg. {money} ÷ {new} = {money / new:.2f}, and he cannot pay for "
              f"another whole kilogram.",
              [(f"{kilos + 1} kg", "CF", "rounded up as usual, but he does not have enough "
                                         "money for the last kilogram"),
               (f"{money / new:.2f} kg", "PK", "divided correctly but did not turn the "
                                               "result into whole kilograms"),
               (f"{money // price} kg", "INT", f"used the old price of {_rs(price)}")]),
    ]
    return {
        "unit_id": uid, "template": "dal_price", "title": "The price of dal",
        "content": "quantity", "context": "personal", "emphasis": None,
        "stimulus": (f"At the village shop, 1 kg of arhar dal cost {_rs(price)}. This month "
                     f"the price went up by {pct}%."),
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
        _mcq(f"{uid}_Q1", "employ", "What percentage of the class cycles to school?",
             f"{cycle * 100 // total}%",
             [(f"{cycle}%", "PK", "used the number of cyclists as if it were a percentage"),
              (f"{_num(walk * 100 / total)}%", "INT", "worked out the percentage for "
                                                     "walkers, a different group"),
              (f"{_num(cycle * 100 / (walk + cycle), 1)}%", "CF",
               "divided by the wrong total, only walkers and cyclists, instead of the whole "
               "class")], rng),
        _mcq(f"{uid}_Q2", "employ",
             "One student from the class is picked at random. What is the probability that "
             "this student comes by bus?",
             _frac(p_bus),
             [("1/4", "CF", "assumed the four ways of travelling are equally likely, "
                            "ignoring the counts"),
              (_frac(Fraction(bus, total - bus)), "INT", "compared bus users with everyone "
                                                         "else (odds) instead of with the "
                                                         "whole class"),
              (_frac(Fraction(total - bus, total)), "PK", "found the right total but counted "
                                                          "the students who do not take the "
                                                          "bus")], rng),
        _open(f"{uid}_Q3", "reason",
              "The headteacher looks at this table and says: \"Most students in our school "
              "walk to school.\" Give one reason why this conclusion might not be right.",
              [f"Fewer than half of this class walk ({walk} of {total}).",
               "One class may not represent the whole school."],
              f"Either reason: fewer than half of this class walk ({walk} of {total}), so "
              f"'most' is not true even for this class; or one class may not represent the "
              f"whole school.",
              [(f"She is right, because walking has the biggest number ({walk}).", "CF",
                "believes the biggest group must be a majority, more than half"),
               ("She is right, because many students like walking.", "RF",
                "an opinion with no link to the data"),
               (f"She is wrong, because only {cycle} students cycle.", "INT",
                "used a row of the table that does not bear on the claim")]),
    ]
    return {
        "unit_id": uid, "template": "travel_survey", "title": "How we get to school",
        "content": "uncertainty_and_data", "context": "societal", "emphasis": None,
        "stimulus": (f"Class 8 asked all {total} of its students how they usually come to "
                     f"school. (These numbers are made up for practice.)"),
        "table": _table(["How they come", "Number of students"],
                        [("Walk", walk), ("Bicycle", cycle), ("Bus", bus), ("Other", other)]),
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

    L, W, H = _num(lc / 100), _num(wc / 100), _num(hc / 100)
    questions = [
        _mcq(f"{uid}_Q1", "formulate",
             "Which calculation gives the number of litres the tank holds when full?",
             f"{L} × {W} × {H} × 1000",
             [(f"{L} × {W} × {H}", "PK", "found the volume in cubic metres but did not "
                                         "convert it to litres"),
              (f"{L} × {W} × {H} × 100", "CF", "used 1 cubic metre = 100 litres, a wrong "
                                               "conversion factor"),
              (f"2 × ({L} × {W} + {W} × {H} + {L} × {H}) × 1000", "INT",
               "used the area of the tank's faces instead of its volume")], rng),
        _mcq(f"{uid}_Q2", "employ",
             f"The full tank holds {cap:,} litres. The pump fills it at {rate} litres per "
             f"minute. How long does it take to fill the empty tank?",
             f"{minutes} minutes",
             [(f"{_num(minutes / 60)} minutes", "PK", "changed the answer to hours but kept "
                                                      "the word minutes"),
              (f"{cap * rate:,} minutes", "CF", "multiplied the capacity by the rate "
                                                "instead of dividing"),
              (f"{rate} minutes", "RF", "repeated a number from the question with no "
                                        "calculation")], rng),
        _open(f"{uid}_Q3", "interpret",
              f"Today the tank is half full. The family uses {use} litres of water a day. "
              f"For how many full days will this water last?",
              [str(days)],
              f"{days} days. Half the tank is {_num(half)} litres, and {_num(half)} ÷ {use} "
              f"= {half / use:.2f}, so the water lasts {days} full days.",
              [(f"{int(cap // use)} days", "INT", "used the full tank, the answer to a "
                                                  "different situation"),
               (f"{days + 1} days", "CF", "rounded up, but the water runs out during the "
                                          "last day"),
               (f"{half / use:.2f} days", "PK", "divided correctly but did not interpret the "
                                                "answer as whole days")]),
    ]
    return {
        "unit_id": uid, "template": "water_tank", "title": "The rooftop water tank",
        "content": "space_and_shape", "context": "occupational", "emphasis": None,
        "stimulus": (f"A plumber is fitting a water tank shaped like a cuboid on a house "
                     f"roof. Inside, it is {_metres(lc)} long, {_metres(wc)} wide and "
                     f"{_metres(hc)} high. 1 cubic metre holds 1,000 litres."),
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

    questions = [
        _mcq(f"{uid}_Q1", "employ", f"How many thousand cells does sample A have after "
                                    f"{h1} hours?",
             f"{a(h1):,} thousand",
             [(f"{a0 * 2 * h1:,} thousand", "CF", "treated doubling as multiplying by 2 "
                                                  "times the hours, linear thinking about "
                                                  "growth"),
              (f"{a(h1 - 1):,} thousand", "PK", "stopped one doubling early"),
              (f"{b(h1):,} thousand", "INT", "worked out the count for sample B instead of "
                                             "sample A")], rng),
        _mcq(f"{uid}_Q2", "reason",
             "After how many whole hours does sample A first have more cells than sample B?",
             f"After {overtake} hours",
             [(f"After {overtake - 1} hours", "PK", "stopped one hour early, before sample A "
                                                    "had overtaken"),
              ("Never, because sample B starts bigger.", "CF",
               "believes the sample that starts bigger stays ahead, ignoring how doubling "
               "speeds up"),
              (f"After {naive} hours", "INT", "compared sample A with sample B's starting "
                                              "size instead of its size at that hour")], rng),
        _complex(f"{uid}_Q3", "interpret", "Is each statement true or false?",
                 [("Sample A gains the same number of cells every hour.", False, "CF",
                   "assumed all growth is linear"),
                  ("Sample B gains the same number of cells every hour.", True, "PK",
                   f"did not connect 'gains {k} thousand cells every hour' with a constant "
                   f"amount"),
                  (f"After {h3} hours, sample A has more than twice as many cells as "
                   f"sample B.", a(h3) > 2 * b(h3), "RF",
                   "guessed without working out the two counts")]),
    ]
    return {
        "unit_id": uid, "template": "growth", "title": "Two kinds of growth",
        "content": "change_and_relationships", "context": "scientific",
        "emphasis": "growth phenomena",
        "stimulus": (f"In a computer model in the school lab, two samples of bacteria grow "
                     f"in different ways.\n\nSample A starts with {a0} thousand cells and "
                     f"doubles every hour.\n\nSample B starts with {b0} thousand cells and "
                     f"gains {k} thousand cells every hour."),
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


def generate_unit(template, seed=None, unit_index=1, max_attempts=500):
    """
    Build one unit from a named template. Same template and seed, same unit.

    If a random draw would make two options identical, or an answer messy,
    the unit is redrawn from the same random stream, so the result is
    still fully determined by the seed.
    """
    if template not in TEMPLATES:
        raise ValueError(f"unknown template {template!r}, available: {sorted(TEMPLATES)}")
    rng = random.Random(seed)
    uid = f"PISA_{template.upper()}_{unit_index:04d}"
    for _ in range(max_attempts):
        try:
            unit = TEMPLATES[template](rng, uid)
        except _Collision:
            continue
        validate_unit(unit)
        return unit
    raise RuntimeError(f"could not build a clean {template} unit in {max_attempts} draws")


def generate_units(n, content=None, context=None, templates=None, seed=None):
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
    return [generate_unit(names[i % len(names)], seed=master.randrange(2 ** 31),
                          unit_index=i + 1) for i in range(n)]


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


def _cfi(code):
    return f"{code}, {TAXONOMY[code]['name']}"


def format_booklet(units, title="Maths in real life: practice units"):
    """The student booklet: situations and questions, no answers, no labels."""
    lines = [f"# {title}", "",
             "Read each situation carefully, then answer the questions about it. "
             "Show your working where the question asks you to.", "",
             f"*{DISCLAIMER}*", ""]
    for n, u in enumerate(units, start=1):
        lines += [f"## Unit {n}: {u['title']}", ""]
        lines += u["stimulus"].split("\n") + [""]
        if u.get("table"):
            lines += _md_table(u["table"]) + [""]
        for m, q in enumerate(u["questions"], start=1):
            lines += [f"**Question {n}.{m}.** {q['prompt']}", ""]
            if q["format"] == "multiple_choice":
                lines += [f"{o['letter']}. {o['text']}  " for o in q["options"]] + [""]
            elif q["format"] == "complex_multiple_choice":
                lines += ["| Statement | True | False |", "|---|---|---|"]
                lines += [f"| {s['text']} | [ ] | [ ] |" for s in q["statements"]] + [""]
            else:
                lines += ["Answer: ____________________________________________", "",
                          "Working:", "", "", ""]
    return "\n".join(lines).rstrip() + "\n"


def format_answer_key(units, title="Maths in real life: practice units"):
    """
    The teacher's key. For every question: the answer, and for every wrong
    answer, the CFI category and what a child who gave it probably thinks.
    Pass the same title as the booklet it goes with.
    """
    cov = coverage(units)
    lines = [f"# {title}: teacher's key with CFI diagnosis", "", f"*{DISCLAIMER}*", "",
             "Every wrong option, wrong true/false judgement and common wrong written "
             "answer below is labelled with a Confusion Fingerprint Index category: "
             "RF (Recall Failure), PK (Partial Knowledge), CF (Confabulation, a confident "
             "misconception), INT (Interference, the right answer to a different "
             "question). Use the labels to decide what to reteach, not just who got it "
             "wrong.", "", "## What this set covers", "",
             "| Dimension | Questions |", "|---|---|"]
    for dim, names in (("content", CONTENT_CATEGORIES), ("context", CONTEXTS),
                       ("process", PROCESSES), ("format", FORMATS)):
        parts = [f"{names[k]} {v}" for k, v in sorted(cov[dim].items())]
        lines.append(f"| {dim.capitalize()} | {', '.join(parts)} |")
    lines.append("")

    for n, u in enumerate(units, start=1):
        tag = f"{CONTENT_CATEGORIES[u['content']]}, {CONTEXTS[u['context']]} context"
        if u.get("emphasis"):
            tag += f", PISA 2022 emphasis on {u['emphasis']}"
        lines += [f"## Unit {n}: {u['title']}", "", f"*{tag}. Unit ID {u['unit_id']}.*", ""]
        for m, q in enumerate(u["questions"], start=1):
            lines += [f"### Question {n}.{m} ({PROCESSES[q['process']]}, "
                      f"{FORMATS[q['format']].lower()})", ""]
            if q["format"] == "multiple_choice":
                lines += [f"**Answer: {q['key']}** ({q['correct_answer']})", "",
                          "| If a child picks | Answer | What it suggests |", "|---|---|---|"]
                by_text = {d["option"]: d for d in q["distractors"]}
                for o in q["options"]:
                    if o["text"] in by_text:
                        d = by_text[o["text"]]
                        lines.append(f"| {o['letter']} | {o['text']} | "
                                     f"{_cfi(d['error_type'])}: {d['note']} |")
                lines.append("")
            elif q["format"] == "complex_multiple_choice":
                lines += ["| Statement | Answer | If a child gets it wrong |", "|---|---|---|"]
                for s in q["statements"]:
                    w = s["if_wrong"]
                    lines.append(f"| {s['text']} | {'True' if s['answer'] else 'False'} | "
                                 f"{_cfi(w['error_type'])}: {w['note']} |")
                lines += ["", "Full credit for all statements right.", ""]
            else:
                sc = q["scoring"]
                lines += [f"**Full credit:** {sc['full_credit']}", ""]
                if sc.get("partial_credit"):
                    lines += [f"**Partial credit:** {sc['partial_credit']}", ""]
                lines += [f"**No credit:** {sc['no_credit']}", "",
                          "| Common wrong answer | What it suggests |", "|---|---|"]
                for w in q["common_wrong_answers"]:
                    lines.append(f"| {w['answer']} | {_cfi(w['error_type'])}: {w['note']} |")
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
                key = (f"option {ans}", text, d["error_type"], d["note"])
                tallies[idx][key] = tallies[idx].get(key, 0) + 1
            elif fmt == "complex_multiple_choice":
                all_right = True
                for k, s in enumerate(q["statements"]):
                    if (ans[k] == "T") != s["answer"]:
                        all_right = False
                        w = s["if_wrong"]
                        errors[w["error_type"]] += 1
                        key = (f"row {k + 1} marked {'True' if ans[k] == 'T' else 'False'}",
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
                    key = (f"written answer coded {code}",
                           match["answer"] if match else "",
                           code,
                           match["note"] if match else "matched a common wrong answer")
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

    return {
        "n_students":     len(students),
        "max_score":      max_score,
        "mean_score":     sum(s["score"] for s in students) / len(students),
        "students":       students,
        "questions":      question_rows,
        "misconceptions": misconceptions,
        "class_errors":   class_errors,
        "class_cfi":      _cfi_indices(class_errors),
    }


def _pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def format_class_report(result, top=5, title="Class report: what to reteach first"):
    """A teacher-facing Markdown report from score_responses()."""
    r = result
    lines = [f"# {title}", "",
             f"{r['n_students']} student{'' if r['n_students'] == 1 else 's'}. Average "
             f"score {r['mean_score']:.1f} out of "
             f"{r['max_score']}.", ""]

    lines += ["## What to reteach first", ""]
    if not r["misconceptions"]:
        lines += ["No diagnosed wrong answers. Either the class did very well, or the "
                  "answers have not been entered yet.", ""]
    for m in r["misconceptions"][:top]:
        what = f" ({m['detail']})" if m["detail"] else ""
        lines += [f"**{m['label']}, {m['answer']}{what}: {m['count']} of {r['n_students']} "
                  f"students, {_cfi_name(m['error_type'])}.** {m['note'][0].upper()}"
                  f"{m['note'][1:]}.", ""]

    lines += ["## The class's error profile", "",
              "| Type | Wrong answers | What usually helps |", "|---|---|---|"]
    for c in ERROR_TYPES:
        lines.append(f"| {_cfi_name(c)} | {r['class_errors'][c]} | {RETEACH_HINTS[c]} |")
    lines += ["", "These are suggestions, you know your class better than any table does.", ""]

    lines += ["## Question by question", "",
              "| Question | Answered | Fully right | Most common wrong answer |",
              "|---|---|---|---|"]
    for qr in r["questions"]:
        common = (f"{qr['wrong'][0]['answer']} ({qr['wrong'][0]['error_type']}, "
                  f"{qr['wrong'][0]['count']})" if qr["wrong"] else "")
        right = _pct(qr["n_full"] / qr["n_answered"]) if qr["n_answered"] else "n/a"
        lines.append(f"| {qr['label']} {qr['unit_title']} | {qr['n_answered']} | {right} | "
                     f"{common} |")
    lines.append("")

    lines += ["## Student by student", "",
              "| Student | Score | RF | PK | CF | INT | Most common error |",
              "|---|---|---|---|---|---|---|"]
    for s in r["students"]:
        e = s["errors"]
        lines.append(f"| {s['student_id']} | {s['score']} / {s['max_score']} | {e['RF']} | "
                     f"{e['PK']} | {e['CF']} | {e['INT']} | {s['dominant_error'] or ''} |")
    lines.append("")

    cfi = r["class_cfi"]
    lines += ["## For researchers", "",
              f"Class Confusion Fingerprint Index: CFI-CF {_pct(cfi['CFI-CF'])}, "
              f"CFI-INT {_pct(cfi['CFI-INT'])}, CFI-RF {_pct(cfi['CFI-RF'])}. Per-student "
              f"values are in the JSON output of `confusion-mapper pisa-score`. CFI-CF is "
              f"CF errors over all diagnosed errors, CFI-INT is INT over INT plus RF, CFI-RF "
              f"is RF over all diagnosed errors. The labels come from the item templates, "
              f"decided before any child answered, not from coding the answers afterwards.", ""]
    return "\n".join(lines).rstrip() + "\n"


def _cfi_name(code):
    return f"{code}, {TAXONOMY[code]['name']}"


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
    """Every template, per_template times, plus the labels the page needs."""
    units = []
    for t_index, name in enumerate(TEMPLATES):
        for k in range(per_template):
            u = generate_unit(name, seed=10000 + 1000 * t_index + k, unit_index=k + 1)
            u.pop("data", None)          # raw numbers are for the tests, not the page
            units.append(u)
    return {
        "pool_format":    1,
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
    }


def web_pool_json(pool=None):
    """The pool as compact JSON that is safe to put inside a <script> tag."""
    text = json.dumps(pool or build_web_pool(), ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/")
