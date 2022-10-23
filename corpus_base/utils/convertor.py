import re
from dataclasses import dataclass
from pathlib import Path

from markdownify import markdownify

MD_FOOTNOTE_LEFT = re.compile(
    r"""
    \^\[ # start with ^[ enclosing digits ending in ], targets the "^["
    (?=\d+\])
    """,
    re.X,
)

MD_FOOTNOTE_RIGHT_POST_LEFT = re.compile(
    r"""
    (?<=\^\d)(\]\^)| # single digit between ^ and ]^ targets the "]^"
    (?<=\^\d{2})(\]\^)| # double digit between ^ and ]^ targets the "]^"
    (?<=\^\d{3})(\]\^) # triple digit between ^ and ]^ targets the "]^"
    """,
    re.X,
)

MD_FOOTNOTE_AFTER_LEFT_RIGHT = re.compile(
    r"""
    (?<=\^\d\])\s| # single digit between ^[ and ], targets the space \s after
    (?<=\^\d{2}\])\s| # double digit between ^[ and ], targets the space \s after
    (?<=\^\d{3}\])\s # triple digit between ^[ and ], targets the space \s after
    """,
    re.X,
)


@dataclass
class DecisionHTMLConvertMarkdown:
    """Utilizes the `ponencia.html`, `fallo.html`, and `annex.html` to eventually create a formatted markdown file."""

    folder: Path

    @property
    def result(self):
        """Add a header on top of the text, then supply the body of the ponencia, followed by the fallo and the annex of footnotes."""
        txt = "# Ponencia\n\n"

        if base := self.convert_html_content("ponencia.html"):
            txt += f"{base.strip()}"

        if fallo := self.convert_html_content("fallo.html"):
            txt += f"\n\n{fallo.strip()}"

        if annex := self.convert_html_content("annex.html"):
            annex_footnoted = MD_FOOTNOTE_AFTER_LEFT_RIGHT.sub(": ", annex)
            txt += f"\n\n{annex_footnoted.strip()}"

        return txt.strip()

    def convert_html_content(self, htmlfilename: str) -> str | None:
        p = self.folder / f"{htmlfilename}"
        if p.exists():
            html_content = p.read_text()
            md_content = self.from_html_to_md(html_content)
            return md_content
        return None

    def revise_md_footnotes(self, raw: str):
        partial = MD_FOOTNOTE_LEFT.sub("[^", raw)
        replaced = MD_FOOTNOTE_RIGHT_POST_LEFT.sub("]", partial)
        return replaced

    def from_html_to_md(self, raw: str) -> str:
        options = dict(
            sup_symbol="^",  # footnote pattern which will be replaced
            escape_asterisks=False,
            escape_underscores=False,
        )
        initial_pass = markdownify(raw, **options)
        revised_pass = self.revise_md_footnotes(initial_pass)
        return revised_pass


def add_markdown_file(p: Path, text: str):
    opinions_path = p / "opinions"
    opinions_path.mkdir(exist_ok=True)
    ponencia_path = opinions_path / "ponencia.md"
    # if not ponencia_path.exists():
    ponencia_path.write_text(text)
