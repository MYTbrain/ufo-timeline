from scripts.build_analysis_source_quality_review import (
    adjudicate_sentinel,
    coordinate_holdout,
    normalize_native_id,
    source_date,
)


def source_row(**values):
    return dict(No="64886", Description="NUFORC UFO Sighting 64886" + "A source-preserved, identity-matching descriptive account. " * 4,
                Occurred="1970-01-01 00:00 Local", Reported="2008-07-31 13:26 Pacific", Posted="2008-08-12",
                _file="frozen/nuforc.csv", _row=123, **values)


def candidate():
    return {"source_id": "S64886", "description": "A source-preserved, identity-matching descriptive account. " * 4}


def test_structured_date_retains_precision_and_rejects_targeted_sentinels():
    assert source_date("1970-01-01 00:00 Local") is None
    assert source_date("1900-01-01 00:00:00") is None
    assert source_date("Reported 2008-07-31") is None
    assert source_date("2008-02-31 00:00") is None
    assert source_date("2008-02-00")["datePrecision"] == "month"
    assert source_date("2008-02-00")["endDate"] == "2008-02-29"
    assert source_date("2008-00-00")["datePrecision"] == "year"
    assert source_date("2008-02-29 10:00 Local")["dateIso"] == "2008-02-29"
    assert normalize_native_id("S64886") == "64886"
    assert normalize_native_id("SS64886") == "SS64886"


def test_submission_date_and_incidental_narrative_year_are_not_occurrence_dates():
    decision = adjudicate_sentinel(candidate(), [source_row()], "NUFORC")
    assert decision["status"] == "unresolved_occurrence_date"
    assert decision["proposal"] is None
    assert decision["sourceObservations"][0]["fields"]["Reported"].startswith("2008")
    assert not decision["canonicalApplyAuthorized"]


def test_valid_occurrence_proposal_requires_identity_and_agreement():
    row = source_row()
    row["Occurred"] = "1980-05-10 18:00 Local"
    accepted = adjudicate_sentinel(candidate(), [row, dict(row, _file="second/frozen.csv")], "NUFORC")
    assert accepted["proposal"]["dateIso"] == "1980-05-10"
    assert accepted["dateRole"] == "source_structured_occurrence"
    assert not accepted["canonicalApplyAuthorized"]
    assert adjudicate_sentinel(dict(candidate(), source_id="S64887"), [row], "NUFORC")["proposal"] is None
    assert adjudicate_sentinel(dict(candidate(), description="A different event narrative"), [row], "NUFORC")["proposal"] is None
    assert adjudicate_sentinel(candidate(), [row, source_row()], "NUFORC")["proposal"] is None


def test_approximate_occurrence_calendar_is_not_promoted_to_exact_day():
    row = source_row()
    row["Occurred"] = "1980-05-10 18:00 Local - Approximate"
    assert adjudicate_sentinel(candidate(), [row], "NUFORC")["proposal"] is None
    occurrence_clause = "near Oscoda in the late summer of 1975"
    reviewed = dict(candidate(), source_id="S13010", description=candidate()["description"] + occurrence_clause)
    row.update(No="13010", Occurred="1975-09-01 00:00 Local - Approximate", Description="NUFORC UFO Sighting 13010" + reviewed["description"])
    decision = adjudicate_sentinel(reviewed, [row], "NUFORC")
    assert decision["proposal"]["datePrecision"] == "year"
    assert decision["proposal"]["startDate"] == "1975-01-01"
    assert decision["proposal"]["dateIso"] is None
    row["Description"] = row["Description"].replace(occurrence_clause, "An incidental follow-up in 1975")
    assert adjudicate_sentinel(reviewed, [row], "NUFORC")["proposal"] is None


def test_coordinate_holdout_is_reproducible_and_does_not_repair_or_apply_exclusions():
    points = [[1], [2], [3]]
    pairs = [[1, 2, 10, 0, 1], [2, 3, 20, 1, 0]]
    context_row = [0] * 23
    context_row[5] = 1
    other_row = list(context_row)
    other_row[5] = 3
    holdout = coordinate_holdout([{"eventId": "1"}, {"eventId": "4"}], points, pairs, [context_row, other_row])
    assert holdout["counts"]["reviewFlags"] == 2
    assert holdout["counts"]["flaggedQualifiedEndpoints"] == 1
    assert holdout["counts"]["remainingQualifiedEndpoints"] == 2
    assert holdout["counts"]["pairsTouchingFlags"] == 1
    assert holdout["counts"]["remainingPairs"] == 1
    assert holdout["counts"]["contextRowsTouchingFlags"] == 1
    assert holdout["qualifiedEndpointExclusionAllowlist"] == ["1"]
    assert holdout["pairExclusionAllowlist"][0]["rowIndex"] == 0
    assert not holdout["automaticExclusionApplied"]
    assert holdout["coordinateCorrections"] == []
    assert len(points) == 3 and len(pairs) == 2
