import pytest

from corpus_cite import RawPonente

data = [
    (
        [
            "AVACEÑA, J.",
            "AVANCEÑA J., with whom concurs MALCOLM, J.",
            "AVANCEÑA, J.",
            "AVANCEÃ'A, C.J.",
            "AVANCEÃ'A, J.",
        ],
        "avancena",
    ),
    (
        [
            "MELENCIO HERRERA, J.",
            "MELENCIO-HERRERA. J.",
            "MELENCIO-HERRRERA, J.",
            "MELENCIO-HERERRA, J.",
            "MELENCIO-HERERA, J.",
        ],
        "melencio-herrera",
    ),
    (
        [
            "REYES, J, B. L. J.",
            "REYES, J. B. L., Actg. C.J.",
            "Reyes, J. B. L. J.",
            "REYES, J. B. L., .J.",
            "REYES , J.B.L, Acting C.J.",
            "REYES, J, B. L., J.",
            "REYES, J.B.L., Actg. C.J.",
        ],
        "reyes, j.b.l.",
    ),
    (
        [
            "Ynares-Santiago",
            "Ynares-Santiago, J.",
            "Ynares-Satiago",
            "Ynares_Santiago",
        ],
        "ynares-santiago",
    ),
]


@pytest.mark.parametrize("orig_samples, fix", data)
def test_clean_raw_ponente(orig_samples, fix):
    for o in orig_samples:
        assert RawPonente.clean(o) == fix
