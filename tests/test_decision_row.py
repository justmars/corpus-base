import datetime
from pathlib import Path

import pytest
from citation_utils import Citation
from citation_utils.__main__ import DocketCategory

from corpus_base import DecisionRow
from corpus_base.utils import (
    CourtComposition,
    DecisionCategory,
    DecisionSource,
)


@pytest.mark.parametrize(
    "paths, obj",
    [
        (
            ["tests", "decisions", "sc", "62206", "details.yaml"],
            DecisionRow(
                id="62206",
                created=1666593067.491151,
                modified=1666593067.4911053,
                origin="62206",
                source=DecisionSource.sc,
                citation=Citation(
                    docket=None,
                    docket_category=None,
                    docket_serial=None,
                    docket_date=None,
                    phil="792 Phil. 133",
                    scra=None,
                    offg=None,
                ),
                emails="bot@lawsql.com",
                title="Jocelyn S. Limkaichong, Petitioner, Vs. Land Bank Of The Philippines, Department Of Agrarian Reform, Represented By The Secretary Of Agrarian Reform, Through The Provincial Agrarian Reform Officer, Respondents.",
                description="792 Phil. 133",
                date=datetime.date(2016, 8, 2),
                raw_ponente="bersamin",
                justice_id=163,
                per_curiam=False,
                composition=CourtComposition.enbanc,
                category=DecisionCategory.decision,
                fallo="**WHEREFORE**, we **GRANT** the petition for review on *certiorari*, and **REVERSE** the decision of the Court of Appeals dated November 22, 2002; and **DIRECT** the Regional Trial Court, Branch 30, in Dumaguete City to resume the proceedings in Civil Case No. 12558 for the determination of just compensation of petitioner Jocelyn S. Limkaichong's expropriated property.  \nNo pronouncement on costs of suit.  \n\n",
                voting="Sereno, C.J., Leonardo-De Castro, Peralta, Del Castillo, Perez, Mendoza, Reyes, Perlas-Bernabe, Jardeleza, and Caguioa, JJ., concur.\nCarpio, J., I join the Separate Opinion of Justice Velasco.\nVelasco, Jr., J., Please see Separate Concurring Opinion.\nBrion, J., on leave.\nLeonen, J., see separate concurring opinion.\nJardeleza, J., see separate concurring opinion.",
            ),
        ),
        (
            ["tests", "decisions", "sc", "62055", "details.yaml"],
            DecisionRow(
                id="62055",
                created=1666592969.7779906,
                modified=1666592969.7779157,
                origin="62055",
                source=DecisionSource.sc,
                citation=Citation(
                    docket=None,
                    docket_category=None,
                    docket_serial=None,
                    docket_date=None,
                    phil="787 Phil. 665",
                    scra=None,
                    offg=None,
                ),
                emails="bot@lawsql.com",
                title="Myrna M. Deveza, Complainant, Vs. Atty. Alexander M. Del Prado, Respondent.",
                description="787 Phil. 665",
                date=datetime.date(2016, 6, 21),
                raw_ponente=None,
                justice_id=None,
                per_curiam=True,
                composition=CourtComposition.enbanc,
                category=DecisionCategory.decision,
                fallo="**WHEREFORE**, finding respondent Atty. Alexander Del Prado **GUILTY** of violating Rule 1.01 of Canon 1 and Canon 7 of the Code of Professional Responsibility, the Court hereby **SUSPENDS** him from the practice of law for Five (5) years effective upon receipt of this decision with a **WARNING** that a repetition of the same or a similar act will be dealt with more severely.  \nLet copies of this decision be furnished all courts in the country and the Integrated Bar of the Philippines for their information and guidance. Let also a copy of this decision be appended to the personal record Atty. Alexander Del Prado in the Office of the Bar Confidant.  \n\n",
                voting="Sereno, C. J., Carpio, Velasco, Jr., Leonardo-De Castro, Brion, Peralta, Bersamin, Perez, Mendoza, Reyes, Perlas-Bernabe, Leonen, Jardeleza, and Caguioa, JJ., concur.\nDel Castillo, J., on official leave.",
            ),
        ),
        (
            ["tests", "decisions", "legacy", "c343d", "details.yaml"],
            DecisionRow(
                id="gr-l-7529-oct-31-1955-97-phil-825",
                created=1666592918.0018396,
                modified=1666592918.0017762,
                origin="c343d",
                source=DecisionSource.legacy,
                citation=Citation(
                    docket="GR L-7529, Oct. 31, 1955",
                    docket_category=DocketCategory.GR,
                    docket_serial="L-7529",
                    docket_date=datetime.date(1955, 10, 31),
                    phil="97 Phil. 825",
                    scra=None,
                    offg=None,
                ),
                emails="bot@lawsql.com",
                title="The People Of The Philippines, Plaintiff And Appellee, Vs. Felix Kho, Alias Co Cam, Et Al., Defendants And Appellants.",
                description="GR L-7529, Oct. 31, 1955, 97 Phil. 825",
                date=datetime.date(1955, 10, 31),
                raw_ponente="paras",
                justice_id=38,
                per_curiam=False,
                composition=CourtComposition.other,
                category=DecisionCategory.decision,
                fallo="Wherefore, the appealed order is hereby reversed, and the case remanded to the Court of First Instance of Rizal for further proceedings. So ordered without costs. *Bengzon, Padilla, Montemayor, Jugo, Reyes, A., Bautista Angelo*, and \n\n\n",
                voting="Labrador, JJ., concur.\nConcepcion, J., concurs in the result.",
            ),
        ),
    ],
)
def test_path_to_obj(paths, obj):
    path = Path.cwd().joinpath("/".join(paths))
    assert DecisionRow.from_path(path) == obj
