"""Check research metric/oracle arithmetic without installing research dependencies in runtime."""

from research.ranking_evaluation import metrics
from research.solver_evaluation import cases, oracle_subsets
from smartrecon.evaluation.ground_truth import GroundTruth, TruthEdge


def test_subset_oracle_keeps_distinct_equal_amount_participants() -> None:
    case = next(case for case in cases() if case.name == "equal_totals")
    assert oracle_subsets(case) == {(0, 2), (0, 3), (1, 2), (1, 3)}


def test_subset_oracle_does_not_equate_a_split_with_a_verified_link() -> None:
    case = next(case for case in cases() if case.name == "unique_split")
    assert oracle_subsets(case) == {(0, 1)}
    assert case.relation == "1:N"


def test_ranking_metrics_count_missing_truth_and_false_candidates() -> None:
    truth = GroundTruth(
        (TruthEdge("C1", "G1", "O1", "B1", 100, "ONE_TO_ONE"), TruthEdge("C2", "G2", "O2", "B2", 200, "ONE_TO_ONE")),
        {},
        {},
    )
    measured = metrics({"B1": ["wrong", "O1"], "B2": []}, truth)
    assert measured["candidate_recall"] == 0.5
    assert measured["precision_at_k"] == {"1": 0, "5": 0.1}
    assert measured["mrr"] == 0.25
    assert measured["false_candidates"] == 1
    assert measured["mean_candidates_per_query"] == 1
    assert measured["per_relation"]["ONE_TO_ONE"]["candidate_recall"] == 0.5
