from dataclasses import dataclass


@dataclass
class EvalResult:
    case_id: str
    expected: list[str]
    actual: list[str]
    precision: float
    recall: float
    passed: bool


def score(expected: list[str], actual: list[str], threshold: float = 0.80) -> EvalResult:
    raise NotImplementedError  # placeholder — call score_case instead


def score_case(case_id: str, expected: list[str], actual: list[str], threshold: float = 0.80) -> EvalResult:
    expected_set = set(expected)
    actual_set = set(actual)

    if not expected_set and not actual_set:
        return EvalResult(case_id, expected, actual, 1.0, 1.0, True)

    tp = len(expected_set & actual_set)
    precision = tp / len(actual_set) if actual_set else 0.0
    recall = tp / len(expected_set) if expected_set else 1.0

    passed = precision >= threshold and recall >= threshold
    return EvalResult(case_id, expected, actual, precision, recall, passed)
