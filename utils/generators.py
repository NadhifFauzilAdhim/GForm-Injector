# utils/generators.py
# Random value generators for Google Form injection

import random
from datetime import datetime

# ---------------------------------------------------------------------------
# Core random generators
# ---------------------------------------------------------------------------


def get_random_likert(scale: int = 5) -> str:
    """
    Return a random Likert-scale value weighted toward the positive end.

    Args:
        scale: Maximum scale value (4 or 5).

    Returns:
        String representation of the chosen value.
    """
    if scale == 4:
        return random.choice(["3", "4", "4", "4"])
    # 5-point scale, weighted toward 4 and 5
    return random.choice(["3", "4", "4", "5", "5", "5"])


def get_random_likert_full(scale: int = 5) -> str:
    """
    Return a uniformly random Likert-scale value (1 to scale).

    Args:
        scale: Maximum value on the scale (e.g. 5 for 1-5).

    Returns:
        String integer from "1" to str(scale).
    """
    return str(random.randint(1, scale))


def get_random_age_range() -> str:
    """
    Return a random age-range string.

    Returns:
        Age range string, e.g. "30 - 40 Years".
    """
    options = [
        "Under 20 Years",
        "20 - 30 Years",
        "30 - 40 Years",
        "40 - 50 Years",
        "Over 50 Years",
    ]
    return random.choice(options)


def get_random_education() -> str:
    """
    Return a random education-level string.

    Returns:
        Education level string, e.g. "Bachelor's Degree".
    """
    options = [
        "No Formal Education",
        "Primary School",
        "Middle School",
        "High School / Vocational",
        "Associate Degree (D1/D2/D3)",
        "Bachelor's Degree (S1)",
        "Master's Degree (S2)",
        "Doctoral Degree (S3)",
    ]
    return random.choice(options)


def get_random_business_tenure() -> str:
    """
    Return a random business-tenure range string.

    Returns:
        Tenure range string, e.g. "3 - 5 Years".
    """
    options = [
        "Less than 1 Year",
        "1 - 2 Years",
        "2 - 3 Years",
        "3 - 5 Years",
        "5 - 10 Years",
        "More than 10 Years",
    ]
    return random.choice(options)


def get_random_gender() -> str:
    """
    Return a random gender string.

    Returns:
        "Male" or "Female".
    """
    return random.choice(["Male", "Female"])


def get_random_revenue_range() -> str:
    """
    Return a random annual revenue range string.

    Returns:
        Revenue range string, e.g. "$10,000 - $100,000".
    """
    options = [
        "Under $1,000",
        "$1,000 - $5,000",
        "$5,000 - $25,000",
        "$25,000 - $100,000",
        "$100,000 - $500,000",
        "Over $500,000",
    ]
    return random.choice(options)


def get_random_business_sector() -> str:
    """
    Return a random business sector string.

    Returns:
        Sector string, e.g. "Food & Beverage".
    """
    options = [
        "Food & Beverage",
        "Fashion & Apparel",
        "Handicrafts & Crafts",
        "Agriculture & Plantation",
        "Livestock & Fishery",
        "General Trade & Retail",
        "Services & Consulting",
        "Technology & Digital",
        "Health & Beauty",
        "Education & Training",
    ]
    return random.choice(options)


def get_random_yes_no() -> str:
    """Return a random Yes / No answer."""
    return random.choice(["Yes", "No"])


def get_random_frequency() -> str:
    """
    Return a random frequency string.

    Returns:
        e.g. "Often", "Sometimes", etc.
    """
    options = [
        "Always",
        "Often",
        "Sometimes",
        "Rarely",
        "Never",
    ]
    return random.choice(options)


def get_random_agreement() -> str:
    """
    Return a random agreement string.

    Returns:
        e.g. "Agree", "Strongly Agree", etc.
    """
    options = [
        "Strongly Disagree",
        "Disagree",
        "Neutral",
        "Agree",
        "Strongly Agree",
    ]
    return random.choice(options)


def get_random_satisfaction() -> str:
    """
    Return a random satisfaction level string.

    Returns:
        e.g. "Satisfied", "Very Satisfied", etc.
    """
    options = [
        "Very Dissatisfied",
        "Dissatisfied",
        "Neutral",
        "Satisfied",
        "Very Satisfied",
    ]
    return random.choice(options)


def get_random_integer(min_val: int = 1, max_val: int = 100) -> str:
    """
    Return a random integer string within the given range.

    Args:
        min_val: Minimum value (inclusive).
        max_val: Maximum value (inclusive).

    Returns:
        String representation of the random integer.
    """
    return str(random.randint(min_val, max_val))


def get_random_float(
    min_val: float = 0.0, max_val: float = 1.0, decimals: int = 2
) -> str:
    """
    Return a random float string within the given range.

    Args:
        min_val:  Minimum value (inclusive).
        max_val:  Maximum value (inclusive).
        decimals: Number of decimal places.

    Returns:
        String representation of the random float.
    """
    value = random.uniform(min_val, max_val)
    return f"{value:.{decimals}f}"


def get_random_timestamp() -> str:
    """
    Return a formatted current timestamp string.

    Returns:
        Timestamp in the format "YYYY-MM-DD HH:MM:SS".
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Registry – maps generator names to callables
# ---------------------------------------------------------------------------

GENERATOR_REGISTRY: dict[str, dict] = {
    "Likert (4-5) — Weighted Positive": {
        "func": get_random_likert,
        "kwargs": {"scale": 5},
        "description": "Randomly picks 3/4/5 with higher weight toward 4 and 5",
        "sample": lambda: get_random_likert(5),
    },
    "Likert (1-5) — Uniform": {
        "func": get_random_likert_full,
        "kwargs": {"scale": 5},
        "description": "Uniformly picks a value from 1 to 5",
        "sample": lambda: get_random_likert_full(5),
    },
    "Likert (1-4) — Uniform": {
        "func": get_random_likert_full,
        "kwargs": {"scale": 4},
        "description": "Uniformly picks a value from 1 to 4",
        "sample": lambda: get_random_likert_full(4),
    },
    "Age Range": {
        "func": get_random_age_range,
        "kwargs": {},
        "description": "Example: '30 - 40 Years'",
        "sample": get_random_age_range,
    },
    "Education Level": {
        "func": get_random_education,
        "kwargs": {},
        "description": 'Example: "Bachelor\'s Degree"',
        "sample": get_random_education,
    },
    "Business Tenure": {
        "func": get_random_business_tenure,
        "kwargs": {},
        "description": "Example: '3 - 5 Years'",
        "sample": get_random_business_tenure,
    },
    "Gender": {
        "func": get_random_gender,
        "kwargs": {},
        "description": "Male or Female",
        "sample": get_random_gender,
    },
    "Annual Revenue": {
        "func": get_random_revenue_range,
        "kwargs": {},
        "description": "Example: '$25,000 - $100,000'",
        "sample": get_random_revenue_range,
    },
    "Business Sector": {
        "func": get_random_business_sector,
        "kwargs": {},
        "description": "Example: 'Food & Beverage'",
        "sample": get_random_business_sector,
    },
    "Yes / No": {
        "func": get_random_yes_no,
        "kwargs": {},
        "description": "Randomly returns Yes or No",
        "sample": get_random_yes_no,
    },
    "Frequency": {
        "func": get_random_frequency,
        "kwargs": {},
        "description": "Example: 'Often', 'Sometimes'",
        "sample": get_random_frequency,
    },
    "Agreement Level": {
        "func": get_random_agreement,
        "kwargs": {},
        "description": "Example: 'Agree', 'Strongly Agree'",
        "sample": get_random_agreement,
    },
    "Satisfaction Level": {
        "func": get_random_satisfaction,
        "kwargs": {},
        "description": "Example: 'Satisfied', 'Very Satisfied'",
        "sample": get_random_satisfaction,
    },
    "Random Integer (1-10)": {
        "func": get_random_integer,
        "kwargs": {"min_val": 1, "max_val": 10},
        "description": "Random integer between 1 and 10",
        "sample": lambda: get_random_integer(1, 10),
    },
    "Current Timestamp": {
        "func": get_random_timestamp,
        "kwargs": {},
        "description": "Current time in YYYY-MM-DD HH:MM:SS format",
        "sample": get_random_timestamp,
    },
}


def call_generator(generator_name: str) -> str:
    """
    Call a generator by its registered name and return its result.

    Args:
        generator_name: Key in GENERATOR_REGISTRY.

    Returns:
        Generated value as string, or empty string if not found.
    """
    entry = GENERATOR_REGISTRY.get(generator_name)
    if entry is None:
        return ""
    func = entry["func"]
    kwargs = entry.get("kwargs", {})
    return func(**kwargs)


def get_generator_names() -> list[str]:
    """Return list of all registered generator names."""
    return list(GENERATOR_REGISTRY.keys())


def get_generator_description(generator_name: str) -> str:
    """
    Return the human-readable description for a generator.

    Args:
        generator_name: Key in GENERATOR_REGISTRY.

    Returns:
        Description string, or empty string if not found.
    """
    entry = GENERATOR_REGISTRY.get(generator_name)
    if entry is None:
        return ""
    return entry.get("description", "")


def get_generator_sample(generator_name: str) -> str:
    """
    Call the sample callable for a generator to produce a preview value.

    Args:
        generator_name: Key in GENERATOR_REGISTRY.

    Returns:
        Sample value string.
    """
    entry = GENERATOR_REGISTRY.get(generator_name)
    if entry is None:
        return ""
    sample_fn = entry.get("sample")
    if callable(sample_fn):
        return str(sample_fn())
    return ""
