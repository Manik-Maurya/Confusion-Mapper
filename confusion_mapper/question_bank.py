"""
Built-in NCERT-style question bank (5 questions, 15 distractors).

Moved unmodified from the "SECTION 2, BUILT-IN QUESTION BANK" block of the
pre-2.6.0 single-file confusion_mapper.py during the v2.6.0 package
reorganization. No values changed.
"""

BUILTIN_QUESTIONS = [
    {
        "id":            "Q001",
        "topic":         "Photosynthesis",
        "class_level":   7,
        "question_text": "Where does photosynthesis primarily take place in a plant cell?",
        "correct_answer":"Chloroplast",
        "distractors": [
            {
                "option":     "Mitochondria",
                "error_type": "CF",
                "note":       "Student confuses the 'powerhouse' organelle, coherent but wrong",
            },
            {
                "option":     "Cell wall",
                "error_type": "PK",
                "note":       "Knows chlorophyll is in the cell somewhere but misses the organelle",
            },
            {
                "option":     "Vacuole",
                "error_type": "RF",
                "note":       "Random implausible guess, no logical connection",
            },
        ],
    },
    {
        "id":            "Q002",
        "topic":         "Nutrition in Plants",
        "class_level":   7,
        "question_text": "What gas do plants absorb from the atmosphere during photosynthesis?",
        "correct_answer":"Carbon dioxide (CO2)",
        "distractors": [
            {
                "option":     "Oxygen (O2)",
                "error_type": "CF",
                "note":       "Classic misconception, students confuse what plants absorb vs release",
            },
            {
                "option":     "Nitrogen (N2)",
                "error_type": "RF",
                "note":       "Random guess, no logical connection to photosynthesis",
            },
            {
                "option":     "Carbon monoxide (CO)",
                "error_type": "PK",
                "note":       "Student knows 'carbon' is involved but lacks the complete formula",
            },
        ],
    },
    {
        "id":            "Q003",
        "topic":         "Nutrition in Animals",
        "class_level":   7,
        "question_text": "Which organ in humans primarily digests proteins?",
        "correct_answer":"Stomach",
        "distractors": [
            {
                "option":     "Small intestine",
                "error_type": "INT",
                "note":       "Interference, small intestine digests fats, studied in the same session",
            },
            {
                "option":     "Liver",
                "error_type": "CF",
                "note":       "Confabulation, liver is prominent so students assign it all digestion",
            },
            {
                "option":     "Kidney",
                "error_type": "RF",
                "note":       "Recall Failure, just a body organ, no logical connection",
            },
        ],
    },
    {
        "id":            "Q004",
        "topic":         "Light and Optics",
        "class_level":   8,
        "question_text": "What happens to light when it moves from air into glass?",
        "correct_answer":"It slows down and bends toward the normal (refracts)",
        "distractors": [
            {
                "option":     "It speeds up and bends away from the normal",
                "error_type": "CF",
                "note":       "Common misconception, students reverse both the speed and direction",
            },
            {
                "option":     "It travels in the same direction but slower",
                "error_type": "PK",
                "note":       "Partial, knows it slows down but misses the bending/refraction part",
            },
            {
                "option":     "It reflects back into air",
                "error_type": "INT",
                "note":       "Interference, reflection was studied in the same optics unit",
            },
        ],
    },
    {
        "id":            "Q005",
        "topic":         "Motion and Time",
        "class_level":   7,
        "question_text": "A car travels 60 km in 2 hours. What is its average speed?",
        "correct_answer":"30 km/h",
        "distractors": [
            {
                "option":     "120 km/h",
                "error_type": "CF",
                "note":       "Confabulation, student multiplies instead of divides (inverted formula)",
            },
            {
                "option":     "60 km/h",
                "error_type": "PK",
                "note":       "Partial, knows speed involves distance but ignores the time divisor",
            },
            {
                "option":     "62 km/h",
                "error_type": "RF",
                "note":       "Recall Failure, random number, no formula applied at all",
            },
        ],
    },
]


