"""One-off generator for synthetic sample PDFs used by tests. Run: python scripts/generate_sample_pdfs.py

All content below is invented placeholder text — no real worksheets, no student data.
"""

from pathlib import Path

import pymupdf as fitz

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "sample_pdfs"

WORKSHEETS: list[tuple[str, list[str]]] = [
    (
        "year9_quadratics_worksheet.pdf",
        [
            "Year 9 Mathematics\nQuadratic Word Problems - Practice Set A\n\n"
            "1. A rectangle has length (x + 3) metres and width x metres. Its area is\n"
            "   40 square metres. Form a quadratic equation and solve for x.\n\n"
            "2. A ball is thrown upward. Its height in metres is h = -5t^2 + 20t.\n"
            "   Find the times at which the ball is at height 15 metres.",
            "3. The product of two consecutive positive integers is 132. Find the integers.\n\n"
            "4. A farmer has 40 metres of fencing to enclose a rectangular pen against a\n"
            "   wall. Find the dimensions that maximise the enclosed area.",
        ],
    ),
    (
        "year9_trig_test_term2.pdf",
        [
            "Year 9 Mathematics\nTrigonometry Test - Term 2\n\n"
            "1. Find the length of the hypotenuse of a right triangle with legs 6cm and 8cm.\n\n"
            "2. A ladder 5m long leans against a wall, reaching 4m up. Find the angle\n"
            "   between the ladder and the ground.",
            "3. Calculate sin(30 degrees), cos(60 degrees) and tan(45 degrees) without a\n"
            "   calculator.\n\n4. A kite string is 20m long and makes an angle of 40 degrees\n"
            "   with the ground. How high is the kite?",
        ],
    ),
    (
        "year8_fractions_homework.pdf",
        [
            "Year 8 Mathematics\nFractions Homework\n\n"
            "1. A pizza is cut into 8 equal slices. Sam eats 3 slices and Priya eats 2.\n"
            "   What fraction of the pizza is left?\n\n"
            "2. Simplify: 3/4 + 1/6\n\n3. Simplify: 5/8 - 1/4\n\n4. Calculate 2/3 of 90.",
        ],
    ),
    (
        "year10_algebra_revision.pdf",
        [
            "Year 10 Mathematics\nAlgebra Revision Sheet\n\n"
            "1. Expand and simplify (2x + 3)(x - 5).\n\n"
            "2. Factorise fully: 6x^2 + 9x.\n\n3. Solve for x: 3(x - 2) = 2(x + 4).",
            "4. Make y the subject of the formula: 3x + 2y = 12.\n\n"
            "5. Simplify: (x^2 - 9) / (x + 3).",
        ],
    ),
    (
        "year9_geometry_quiz.pdf",
        [
            "Year 9 Mathematics\nGeometry Quiz\n\n"
            "1. Find the sum of interior angles of a regular hexagon.\n\n"
            "2. A circle has radius 7cm. Calculate its circumference and area.\n\n"
            "3. Two triangles are similar. One has sides 3cm, 4cm, 5cm; the other has a\n"
            "   shortest side of 6cm. Find the other two sides.",
        ],
    ),
    (
        "year10_probability_worksheet.pdf",
        [
            "Year 10 Mathematics\nProbability Worksheet\n\n"
            "1. A bag contains 4 red, 3 blue and 5 green marbles. Find the probability of\n"
            "   drawing a blue marble.\n\n"
            "2. Two coins are tossed. Find the probability of getting exactly one head.",
            "3. A die is rolled twice. Find the probability that the sum of the two rolls\n"
            "   is 7.\n\n4. Draw a tree diagram for choosing 2 balls without replacement from\n"
            "   a bag of 3 red and 2 white balls.",
        ],
    ),
]


def build_pdf(path: Path, pages_text: list[str]) -> None:
    document = fitz.open()
    for text in pages_text:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    document.save(str(path))
    document.close()


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for filename, pages_text in WORKSHEETS:
        build_pdf(SAMPLES_DIR / filename, pages_text)
        print(f"wrote {filename} ({len(pages_text)} pages)")


if __name__ == "__main__":
    main()
