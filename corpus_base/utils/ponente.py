import re
from enum import Enum
from typing import NamedTuple

from sqlpyd import Connection
from unidecode import unidecode

IS_PER_CURIAM = re.compile(r"per\s+curiam", re.I)


class RawPonente(NamedTuple):
    writer: str | None = None
    per_curiam: bool = False

    @classmethod
    def extract(cls, text: str | None):
        if not text:
            return None
        if text:
            if IS_PER_CURIAM.search(text):
                return cls(per_curiam=True)
            else:
                return cls(writer=cls.clean(text))

    @classmethod
    def clean(cls, text: str) -> str | None:
        """Since most ponente strings from the case files are not uniform, clean this field by a variety of fixes such"""

        no_asterisk = re.sub(r"\[?(\*)+\]?", "", text)
        surname = init_surnames(no_asterisk)
        no_suffix = TitleSuffixClean.clean_end(surname).strip()
        repl = CommonTypos.replace_value(no_suffix).strip()
        res = repl + "." if repl.endswith((" jr", " sr")) else repl
        return res if 4 < len(res) < 20 else None


class TitleSuffixClean(Enum):
    """The order matters: will try to match the old style first."""

    CHIEF = re.compile(
        r"""
        ,?
        \s*
        (
            act
                (
                    g\.
                    |ing
                )
        )?
        \s+
        C
        \.?
        \s* # possible space
        J
        \.?
        ,?
        $ # end of string
    """,
        re.X | re.I,
    )

    ENDS_IN_J = re.compile(
        r"""
        (
            ( # e.g. ',   J.'
                \s*
                ,
                \s*
                J
                \.
            )|
            ( # e.g. ', J' # no period at end; see also ,j
                ,
                \s*
                J
            )|
            ( # e.g. ends in J after a space
                \s+
                J
            )
        )
        $
        """,
        re.I | re.X,
    )

    @classmethod
    def clean_end(cls, candidate: str):
        """If one of the members matches, return the replacement."""
        for _, member in cls.__members__.items():
            if member.value.search(candidate):
                return member.value.sub("", candidate)
        return candidate


class CommonTypos(Enum):

    AVANC = (
        re.compile(
            r"""
            ^ava
            n?
            (
                (cea'a)|
                (cena)
            )
            """,
            re.I | re.X,
        ),
        "avancena",
    )

    BENGZON = (
        re.compile(
            r"""
            ^bengzon[,\s]+j\W+p\W+
            """,
            re.I | re.X,
        ),
        "bengzon",
    )

    GONZAGA = (
        re.compile(
            r"""
            ^gonzaga(-|_)reyes
            """,
            re.I | re.X,
        ),
        "gonzaga-reyes",
    )

    MELENCIO = (
        re.compile(
            r"""
            ^melencio[\s-]+her
            """,
            re.I | re.X,
        ),
        "melencio-herrera",
    )

    CAMPOS = (
        re.compile(
            r"""
            ^campos[\s,]+jr
            """,
            re.I | re.X,
        ),
        "campos jr.",
    )

    TORRES = (
        re.compile(
            r"""
            ^torres[\s,]+jr
            """,
            re.I | re.X,
        ),
        "torres jr.",
    )

    VILLARAMA = (
        re.compile(
            r"""
            ^villarama[\s,]+jr
            """,
            re.I | re.X,
        ),
        "villarama jr.",
    )

    CONCEPCION_JR = (
        re.compile(
            r"""
            ^conce
            (
                pc|cp # typo
            )
            ion[\s,]+jr
            """,
            re.I | re.X,
        ),
        "concepcion jr.",
    )

    GRINO_AQUINO = (
        re.compile(
            r"""
            gri(n|r)o[\s-]+a?quino
            """,
            re.I | re.X,
        ),
        "grino-aquino",
    )

    CARPIO_MORALES = (
        re.compile(
            r"""
            carpio[\s-]+morales
            """,
            re.I | re.X,
        ),
        "carpio-morales",
    )

    GUTIERREZ_JR = (
        re.compile(
            r"""
            ^gutierrez[\s;,]+jr
            """,
            re.I | re.X,
        ),
        "gutierrez jr.",
    )

    DELEON_JR = (
        re.compile(
            r"""
            ^de[\s]+leon[\s;,]+jr
            """,
            re.I | re.X,
        ),
        "de leon jr.",
    )

    DAVIDE_JR = (
        re.compile(
            r"""
            ^davide[\s,]+jr
            """,
            re.I | re.X,
        ),
        "davide jr.",
    )

    VELASCO_JR = (
        re.compile(
            r"""
            ^velasco[\s,]+jr
            """,
            re.I | re.X,
        ),
        "velasco jr.",
    )

    YNARES_SANTIAGO = (
        re.compile(
            r"""
            ynares[_\s-]+san?tiago
            """,
            re.I | re.X,
        ),
        "ynares-santiago",
    )

    CHICO_NAZARIO = (
        re.compile(
            r"""
            chico[_\s-]+nazario
            """,
            re.I | re.X,
        ),
        "chico-nazario",
    )

    LEONARDO_DE_CASTRO = (
        re.compile(
            r"""
            leonardo[\s-]+de[\s-]castro
            """,
            re.I | re.X,
        ),
        "leonardo-de castro",
    )

    AUSTRIA_MARTINEZ = (
        re.compile(
            r"""
            austria[\s-]+martinez
            """,
            re.I | re.X,
        ),
        "austria-martinez",
    )

    PERLAS_BERNABE = (
        re.compile(
            r"""
            perlas[\s-]+bernabe
            """,
            re.I | re.X,
        ),
        "perlas-bernabe",
    )

    JBL = (
        re.compile(
            r"""
            (
                j
                \W+
                b
                \W+
                l
                \W* # can be without period
            )
            """,
            re.I | re.X,
        ),
        "reyes, j.b.l.",
    )

    AREYES = (
        re.compile(
            r"""
            (
                (a\.\s+)?
                (reyes,\s)
                jr
            )|
            (
                (reyes,\s)a\W+jr
            )
            """,
            re.I | re.X,
        ),
        "reyes, a. jr.",
    )

    RTREYES = (
        re.compile(
            r"""
            ^reyes,\sr\.t\.?$
            """,
            re.I | re.X,
        ),
        "reyes, r.t.",
    )

    DEL_CASTILLO = (
        re.compile(
            r"""
            ^del[\s,-]+castillo
            """,
            re.I | re.X,
        ),
        "del castillo",
    )

    BAUTISTA_ANGELO = (
        re.compile(
            r"""
            ^bautista[\s,-]+a(n|u)gelo
            """,
            re.I | re.X,
        ),
        "bautista angelo",
    )

    TEEHANKEE = (
        re.compile(
            r"""
            ^teehankee
            """,
            re.I | re.X,
        ),
        "teehankee",
    )

    CALLEJO = (
        re.compile(
            r"""
            ^callejo
            """,
            re.I | re.X,
        ),
        "callejo",
    )

    BELLOSILLO = (
        re.compile(
            r"""
            ^bellosi?illo
            """,
            re.I | re.X,
        ),
        "bellosillo",
    )

    MAKALINTAL = (
        re.compile(
            r"""
            ^ma?kalintal
            """,
            re.I | re.X,
        ),
        "makalintal",
    )

    VITUG = (
        re.compile(
            r"""
            ^v(i|l)tug
            """,
            re.I | re.X,
        ),
        "vitug",
    )

    MAKASIAR = (
        re.compile(
            r"""
            ^makasiar
            """,
            re.I | re.X,
        ),
        "makasiar",
    )

    BRION = (
        re.compile(
            r"""
            ^brion
            """,
            re.I | re.X,
        ),
        "brion",
    )

    HERMOSISIMA = (
        re.compile(
            r"""
            ^hermosisima
            """,
            re.I | re.X,
        ),
        "hermosisima",
    )

    VILLAMOR = (
        re.compile(
            r"""
            ^v(i|l)llamor
            """,
            re.I | re.X,
        ),
        "villamor",
    )

    GAERLAN = (
        re.compile(
            r"""
            ^gaerlan[\s,]+s
            """,
            re.I | re.X,
        ),
        "gaerlan",
    )

    CAGUIOA = (
        re.compile(
            r"""
            ^caguioa
            """,
            re.I | re.X,
        ),
        "caguioa",
    )

    PADILLA = (
        re.compile(
            r"""
            ^padilll?a
            """,
            re.I | re.X,
        ),
        "padilla",
    )

    WILLARD = (
        re.compile(
            r"""
            (willl?ard)
            |(wlllard)
            """,
            re.I | re.X,
        ),
        "willard",
    )

    FRANCISCO = (
        re.compile(
            r"""
            ^francisco
            """,
            re.I | re.X,
        ),
        "francisco",
    )

    CRUZ = (
        re.compile(
            r"""
            ^cruz\.?$
            """,
            re.I | re.X,
        ),
        "cruz",
    )

    YULO = (
        re.compile(
            r"""
        ^yulo\.?$
            """,
            re.I | re.X,
        ),
        "yulo",
    )

    ARELLANO = (
        re.compile(
            r"""
            ^arr?ell?ano
            """,
            re.I | re.X,
        ),
        "arellano",
    )

    ZALAMEDA = (
        re.compile(
            r"""
            ^zalameda
            """,
            re.I | re.X,
        ),
        "zalameda",
    )

    VILLAREAL = (
        re.compile(
            r"""
            ^villa[\s-]*real
            """,
            re.I | re.X,
        ),
        "villa-real",
    )

    ZALDIVAR = (
        re.compile(
            r"""
            ^zaldivar
            """,
            re.I | re.X,
        ),
        "zaldivar",
    )

    SANDOVAL_GUTIERREZ = (
        re.compile(
            r"""
            ^sandoval[\s-]+gutierrez
            """,
            re.I | re.X,
        ),
        "sandoval-gutierrez",
    )

    PABLO_M = (
        re.compile(
            r"""
            ^pablo[,\s]+m\.?
            """,
            re.I | re.X,
        ),
        "pablo",
    )

    HORRILENO_M = (
        re.compile(
            r"""
            ^horrilleno[,\s]+m\.?
            """,
            re.I | re.X,
        ),
        "horrilleno",
    )

    DIOKNO_M = (
        re.compile(
            r"""
            ^diokno[,\s]+m\.?
            """,
            re.I | re.X,
        ),
        "diokno",
    )

    @classmethod
    def replace_value(cls, candidate: str):
        """If one of the members matches, return the replacement that is specified in the value."""
        for _, member in cls.__members__.items():
            if member.value[0].search(candidate):
                return member.value[1]
        return candidate


def init_surnames(text: str):
    """Remove unnecessary text and make uniform accented content."""
    text = unidecode(text)
    text = text.lower()
    text = text.strip(",.: ")
    return text


def most_popular(c: Connection):
    from corpus_base.decision import DecisionRow

    return c.db.execute(
        f"""--sql
        select min(date), max(date), raw_ponente, count(*) num
        from {DecisionRow.__tablename__}
        where raw_ponente is not null and per_curiam is 0
        group by raw_ponente
        order by num desc
    ;"""
    ).fetchall()
