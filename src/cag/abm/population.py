"""CAG-specific construction of citizens from survey respondent rows."""

import pandas as pd

from gabm.abm.attributes.gender import GenderID

from cag.abm.agent import SurveyedCitizen
from cag.abm.environment import SurveyedNation
from cag.abm.attributes.education import EducationID
from cag.abm.attributes.ethnicity import EthnicityID
from cag.abm.attributes.family import FamilyID
from cag.abm.attributes.income import IncomeID
from cag.abm.attributes.narratives import rescale_1_6, rescale_1_7
from cag.abm.attributes.politics import PoliticsID
from cag.abm.attributes.region import RegionID
from cag.abm.democracy.elections.brexit import BrexitVoteID
from cag.abm.democracy.elections.ukge2019 import UKGE2019VoteID


def citizen_from_survey_row(
    row: pd.Series, *, environment: SurveyedNation, year: int,
) -> SurveyedCitizen:
    """Convert one row without filtering, sampling, or registering the citizen.

    Retains the supplied Series as original survey data. Missing columns use
    the historical defaults; invalid present values propagate conversion errors.
    """
    return SurveyedCitizen(
        agent_id=row.get("ID", None),
        environment=environment,
        year_of_birth=year - int(row.get("age", 0)),
        gender_id=GenderID.MALE if int(row.get("male_dummy", 0)) == 1 else GenderID.FEMALE,
        region_id=RegionID(int(row.get("tprofile_GOR", 0))),
        education_id=EducationID(int(row.get("profile_education_level", 0))),
        income_id=IncomeID(int(row.get("tprofile_gross_household", 0))),
        ethnicity_id=EthnicityID(int(row.get("ethnicity_R", 0))),
        family_id=FamilyID.PARENT if int(row.get("parent_dummy", 0)) == 1 else FamilyID.NOT_PARENT,
        ukge2019_vote_id=UKGE2019VoteID(int(row.get("Vote2019R", 0))),
        brexit_vote_id=BrexitVoteID(int(row.get("pastvote_EURef", 0))),
        politics_id=PoliticsID(int(row.get("Political_Left_Right", 0))),
        selftransc_id=rescale_1_6(int(row.get("Selftransc_Val", 0))),
        selfenh_id=rescale_1_6(int(row.get("Selfenh_Values", 0))),
        openness_id=rescale_1_6(int(row.get("Openness", 0))),
        conformtrad_id=rescale_1_6(int(row.get("ConformTrad", 0))),
        sdo_id=rescale_1_7(int(row.get("SDO", 0))),
        edo_id=rescale_1_7(int(row.get("EDO", 0))),
        rwa_id=rescale_1_6(int(row.get("RWA", 0))),
        original_survey_data=row,
    )
