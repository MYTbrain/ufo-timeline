from pathlib import Path

from scripts.summarize_coordinate_residual_risk import summarize_coordinate_residual_risk


def test_coordinate_residual_risk_flags_western_positive_longitude_group(tmp_path: Path) -> None:
    input_path = tmp_path / "summary.csv"
    json_output = tmp_path / "risk.json"
    csv_output = tmp_path / "risk.csv"
    input_path.write_text(
        "\n".join(
            [
                "country,source_name,state_or_region,raw_region,count,min_lat,max_lat,min_lon,max_lon",
                "Brazil,ufocat,BRA,SA,281,-38.72,-0.92,-73.33,94.83",
                "United States of America,ufocat,FL,US,859,24.5,30.67,-87.28,-79.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_residual_risk(
        input_path=input_path,
        json_output=json_output,
        csv_output=csv_output,
    )

    assert report["canonical_outputs_mutated"] is False
    assert report["risk_counts"]["critical"] == 1
    assert report["risk_counts"]["low"] == 1
    assert report["top_groups"][0]["country"] == "Brazil"
    assert "positive_longitude_for_western_hemisphere_country" in report["top_groups"][0]["risk_reasons"]
    assert json_output.exists()
    assert csv_output.exists()


def test_coordinate_residual_risk_flags_raw_region_country_conflict(tmp_path: Path) -> None:
    input_path = tmp_path / "summary.csv"
    json_output = tmp_path / "risk.json"
    csv_output = tmp_path / "risk.csv"
    input_path.write_text(
        "\n".join(
            [
                "country,source_name,state_or_region,raw_region,count,min_lat,max_lat,min_lon,max_lon",
                "Georgia,majestic,Georgia,USA,159,30.78,34.91,-85.17,-80.85",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_residual_risk(
        input_path=input_path,
        json_output=json_output,
        csv_output=csv_output,
    )

    assert report["risk_counts"]["critical"] == 1
    assert report["top_groups"][0]["recommendation"] == "repair_or_quarantine_next"
    assert "raw_region_conflicts_declared_country" in report["top_groups"][0]["risk_reasons"]


def test_coordinate_residual_risk_does_not_escalate_region_conflict_inside_country_bounds(tmp_path: Path) -> None:
    input_path = tmp_path / "summary.csv"
    json_output = tmp_path / "risk.json"
    csv_output = tmp_path / "risk.csv"
    input_path.write_text(
        "\n".join(
            [
                "country,source_name,state_or_region,raw_region,count,min_lat,max_lat,min_lon,max_lon",
                "Russia,ufocat,RUS,EU,1,55.75,55.75,37.62,37.62",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_residual_risk(
        input_path=input_path,
        json_output=json_output,
        csv_output=csv_output,
    )

    assert report["risk_counts"]["low"] == 1
    assert "critical" not in report["risk_counts"]
    assert "raw_region_conflicts_declared_country" in report["top_groups"][0]["risk_reasons"]


def test_coordinate_residual_risk_does_not_escalate_wide_span_without_direct_failure(tmp_path: Path) -> None:
    input_path = tmp_path / "summary.csv"
    json_output = tmp_path / "risk.json"
    csv_output = tmp_path / "risk.csv"
    input_path.write_text(
        "\n".join(
            [
                "country,source_name,state_or_region,raw_region,count,min_lat,max_lat,min_lon,max_lon",
                "Russia,ufocat,RUS,AS,12,47.78,76.65,66.72,155.82",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_residual_risk(
        input_path=input_path,
        json_output=json_output,
        csv_output=csv_output,
    )

    assert report["risk_counts"]["low"] == 1
    assert "high" not in report["risk_counts"]
    assert report["top_groups"][0]["recommendation"] == "likely_polygon_coastal_false_positive"


def test_coordinate_residual_risk_allows_bermuda_high_seas_and_chilean_antarctic_source_regions(tmp_path: Path) -> None:
    input_path = tmp_path / "summary.csv"
    json_output = tmp_path / "risk.json"
    csv_output = tmp_path / "risk.csv"
    input_path.write_text(
        "\n".join(
            [
                "country,source_name,state_or_region,raw_region,count,min_lat,max_lat,min_lon,max_lon",
                "Bermuda,majestic,Bermuda,Atlantic Ocean + islands,4,29.666668,32.333335,-67.46667,-64.76667",
                "Chile,majestic,CHL,Antarctic below 70 degrees South,3,-65.16667,-62.483336,-60.600003,-59.61667",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_coordinate_residual_risk(
        input_path=input_path,
        json_output=json_output,
        csv_output=csv_output,
    )

    assert report["risk_counts"]["low"] == 2
    assert "medium" not in report["risk_counts"]
