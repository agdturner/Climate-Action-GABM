"""Synthetic characterization of the existing respondent-to-citizen path."""

import logging

import pandas as pd
import pytest

from cag import __main__ as cli
from cag.abm.population import citizen_from_survey_row
from cag.abm.attributes.narratives import HIGH, LOW, MODERATE, UNKNOWN
from cag.abm.attributes.opinion import (
    ClimatePolicyID, PRO_CLIMATE_INDEX_COLUMN, SURVEY_COLUMN_MAP,
)
from cag.io.survey import load


def _respondent(respondent_id=31, **overrides):
    row = {
        "ID": respondent_id,
        "age": 41,
        "male_dummy": 1,
        "tprofile_GOR": 1,
        "profile_education_level": 16,
        "tprofile_gross_household": 5,
        "ethnicity_R": 1,
        "parent_dummy": 1,
        "Vote2019R": 1,
        "pastvote_EURef": 1,
        "Political_Left_Right": 4,
        "Selftransc_Val": 1,
        "Selfenh_Values": 3,
        "Openness": 5,
        "ConformTrad": 6,
        "SDO": 3,
        "EDO": 6,
        "RWA": 4,
        **{column: 4 for column in SURVEY_COLUMN_MAP.values()},
        PRO_CLIMATE_INDEX_COLUMN: 4.0,
    }
    return {**row, **overrides}


def _write_rows(tmp_path, rows):
    path = tmp_path / "synthetic_respondents.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_loader_selects_columns_filters_rows_and_preserves_index(tmp_path, caplog):
    rows = [
        _respondent(31, extra_column="discard"),
        _respondent(32, age=None),
        _respondent(33, profile_education_level=19),
        _respondent(34, ethnicity_R=6),
        _respondent(35, pastvote_EURef=4),
        _respondent(7, profile_education_level=18, ethnicity_R=5,
                    pastvote_EURef=3, Political_Left_Right=8),
    ]

    with caplog.at_level(logging.INFO):
        data = load(_write_rows(tmp_path, rows))

    assert data is not None
    assert data["ID"].tolist() == [31, 7]
    assert data.index.tolist() == [0, 5]
    assert pd.api.types.is_integer_dtype(data["ID"])
    assert data.columns.tolist() == list(_respondent())
    assert "extra_column" not in data
    assert "Columns with NaN counts" in caplog.text
    assert "2 rows after filtering" in caplog.text


@pytest.mark.parametrize("column", ["age", "page5posttreatment6_5"])
def test_missing_required_value_excludes_the_whole_respondent(tmp_path, column):
    data = load(_write_rows(tmp_path, [_respondent(31, **{column: None})]))

    assert data is None


def test_loader_reports_missing_file_and_missing_columns(tmp_path, caplog):
    assert load(tmp_path / "absent.csv") is None
    assert "Survey data file not found" in caplog.text
    caplog.clear()
    assert load(_write_rows(tmp_path, [{"ID": 1}])) is None
    assert "Missing required columns" in caplog.text


def test_loader_keeps_unconvertible_respondent_ids_with_a_warning(tmp_path, caplog):
    data = load(_write_rows(tmp_path, [_respondent("synthetic-id")]))

    assert data is not None
    assert data["ID"].tolist() == ["synthetic-id"]
    assert "Could not convert 'ID' column to int" in caplog.text


def test_builder_maps_attributes_and_retains_original_response():
    data = pd.DataFrame([_respondent(), _respondent(7)], index=[80, 20])
    before = data.copy(deep=True)

    nation = cli.build_nation(data, year=2030)

    assert nation.year == 2030
    assert nation.place == "UK"
    assert list(nation.agents_active) == [31, 7]
    citizen = nation.agents_active[31]
    assert citizen.environment is nation
    assert citizen.id == data.iloc[0]["ID"]
    assert type(citizen.id) is type(data.iloc[0]["ID"])
    assert citizen.year_of_birth == 1989
    assert citizen.gender_id == cli.GenderID.MALE
    assert citizen.family_id == cli.FamilyID.PARENT
    for attribute, id_type, value in (
        ("region_id", cli.RegionID, 1),
        ("education_id", cli.EducationID, 16),
        ("income_id", cli.IncomeID, 5),
        ("ethnicity_id", cli.EthnicityID, 1),
        ("ukge2019_vote_id", cli.UKGE2019VoteID, 1),
        ("brexit_vote_id", cli.BrexitVoteID, 1),
        ("politics_id", cli.PoliticsID, 4),
    ):
        assert getattr(citizen, attribute) == id_type(value)
    assert (
        citizen.selftransc_id, citizen.selfenh_id, citizen.openness_id,
        citizen.conformtrad_id, citizen.sdo_id, citizen.edo_id, citizen.rwa_id,
    ) == (LOW, MODERATE, HIGH, HIGH, LOW, HIGH, MODERATE)
    assert isinstance(citizen.original_survey_data, pd.Series)
    pd.testing.assert_series_equal(citizen.original_survey_data, data.iloc[0])
    pd.testing.assert_frame_equal(data, before)
    assert citizen.get_real_survey_response(ClimatePolicyID.BAN_PETROL_CARS) == 0
    assert citizen.get_real_package_index() == 0
    assert citizen.opinion_history == {}
    assert citizen.network_neighbors == []
    assert citizen.political_exposure == "neither"


def test_load_sample_build_retains_selected_respondent_order(tmp_path):
    data = load(_write_rows(tmp_path, [_respondent(i) for i in [31, 7, 42, 18, 9]]))
    selected = data.sample(n=3, random_state=42).reset_index(drop=True)

    nation = cli.build_nation(selected)

    assert selected["ID"].tolist() == [7, 9, 42]
    assert list(nation.agents_active) == [7, 9, 42]
    for citizen, (_, row) in zip(nation.agents_active.values(), selected.iterrows()):
        pd.testing.assert_series_equal(citizen.original_survey_data, row)


def test_builder_missing_columns_use_existing_defaults():
    nation = cli.build_nation(pd.DataFrame([{"ID": "synthetic-id"}]))
    citizen = nation.agents_active["synthetic-id"]

    assert citizen.year_of_birth == 2026
    assert citizen.gender_id == cli.GenderID.FEMALE
    assert citizen.family_id == cli.FamilyID.NOT_PARENT
    assert citizen.education_id == cli.EducationID(0)
    assert citizen.selftransc_id == UNKNOWN


def test_builder_truncates_numeric_scores_and_preserves_binary_flag_rules():
    data = pd.DataFrame([_respondent(
        age=41.9, male_dummy=2, parent_dummy=2,
        Selftransc_Val=2.9, Selfenh_Values=8, SDO=5.9, EDO=0,
    )])

    citizen = next(iter(cli.build_nation(data).agents_active.values()))

    assert citizen.year_of_birth == 1985
    assert citizen.gender_id == cli.GenderID.FEMALE
    assert citizen.family_id == cli.FamilyID.NOT_PARENT
    assert citizen.selftransc_id == LOW
    assert citizen.selfenh_id == UNKNOWN
    assert citizen.sdo_id == MODERATE
    assert citizen.edo_id == UNKNOWN


def test_builder_duplicate_ids_replace_earlier_agent_without_reordering():
    data = pd.DataFrame([
        _respondent(31, age=20), _respondent(7), _respondent(31, age=50),
    ])

    nation = cli.build_nation(data)

    assert list(nation.agents_active) == [31, 7]
    assert nation.agents_active[31].year_of_birth == 1976
    pd.testing.assert_series_equal(
        nation.agents_active[31].original_survey_data, data.iloc[2],
    )


@pytest.mark.parametrize("age", [None, "not-an-age"])
def test_builder_does_not_apply_loader_missing_value_policy(age):
    with pytest.raises((TypeError, ValueError)):
        cli.build_nation(pd.DataFrame([_respondent(age=age)]))


def test_builder_empty_population_is_allowed():
    nation = cli.build_nation(pd.DataFrame())

    assert nation.agents_active == {}


def test_row_factory_retains_row_identity_without_registering_or_mutating():
    row = pd.Series(_respondent(), name=80)
    before = row.copy(deep=True)
    nation = cli.build_nation(pd.DataFrame(), year=2030)

    citizen = citizen_from_survey_row(row, environment=nation, year=2030)

    assert citizen.original_survey_data is row
    assert citizen.environment is nation
    assert nation.agents_active == {}
    pd.testing.assert_series_equal(row, before)
    expected = cli.build_nation(pd.DataFrame([row]), year=2030).agents_active[citizen.id]
    assert citizen.get_persona() == expected.get_persona()
    assert citizen.year_of_birth == expected.year_of_birth


def test_builder_delegates_rows_to_factory_in_positional_order(monkeypatch):
    from unittest.mock import Mock

    data = pd.DataFrame([_respondent(31), _respondent(7)], index=[80, 20])
    factory = Mock(wraps=citizen_from_survey_row)
    monkeypatch.setattr(cli, "citizen_from_survey_row", factory)

    nation = cli.build_nation(data, year=2030)

    assert factory.call_count == 2
    for index, invocation in enumerate(factory.call_args_list):
        assert invocation.kwargs == {"environment": nation, "year": 2030}
        pd.testing.assert_series_equal(invocation.args[0], data.iloc[index])
    assert list(nation.agents_active) == [31, 7]
