"""
Unified reading order for sorted text extraction (``sort=True``).

All sorted extraction variants - "text", "words", "blocks", "dict", "json",
"rawdict" and "rawjson" - must share one ordering rule:

* two-column pages are read top-to-bottom, left column completely before
  the right column;
* single-column pages and tables stay top-to-bottom, table cells on the
  same row staying adjacent;
* the sequence is independent of the page /Rotate value;
* only the sequence changes: words, coordinates, spans and characters are
  neither added, dropped nor modified.

The test pages are generated in-memory, so no extra resource files are
needed.
"""
import json

import pymupdf


def _two_column_page(rotate=0):
    """Build a two-column page with independent line structure per column.

    The columns use different line counts and baseline grids, like real
    prose columns, and a wide fixed footer crosses the column gutter.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for i in range(20):  # dense left column
        page.insert_text((50, 60 + i * 18), f"L{i:02d} lorem ipsum dolor sit amet")
    for i in range(13):  # sparser right column, different grid
        page.insert_text((330, 67 + i * 27), f"R{i:02d} consectetur adipiscing elit")
    page.insert_text(
        (70, 815),
        "FOOTER PAGE 1 OF 9 - CONFIDENTIAL - SUPPLIER QUARTERLY STATEMENT",
    )
    if rotate:
        page.set_rotation(rotate)
    return doc, page


def _span_texts(d):
    """Flatten a dict/rawdict extraction to its ordered span texts."""
    out = []
    for block in d["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if "chars" in span:  # rawdict / rawjson
                    out.append("".join(c["c"] for c in span["chars"]))
                else:
                    out.append(span["text"])
    return out


def _table_page():
    """Two aligned columns that look like table rows, not prose columns."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for row in range(6):
        y = 100 + row * 40
        page.insert_text((60, y), f"ACC{row:03d}")
        page.insert_text((300, y), f"AMT{row:03d}")
    return doc, page


def test_two_column_words_left_before_right():
    doc, page = _two_column_page()
    words = page.get_text("words", sort=True)
    first_right = next(i for i, w in enumerate(words) if w[4].startswith("R"))
    last_left = max(i for i, w in enumerate(words) if w[4].startswith("L"))
    # the whole left column is emitted before the first right-column word
    assert last_left < first_right
    assert words[0][4] == "L00"
    # the wide footer is read after both columns
    footer = next(i for i, w in enumerate(words) if w[4] == "FOOTER")
    assert footer > first_right
    assert words[-1][4] == "STATEMENT"


def test_two_column_all_variants_share_order():
    doc, page = _two_column_page()

    words = [w[4] for w in page.get_text("words", sort=True)]

    text = page.get_text(sort=True)
    assert text.find("L00") < text.find("R00") < text.find("FOOTER")

    blocks = page.get_text("blocks", sort=True)
    block_text = "".join(b[4] for b in blocks)
    assert block_text.find("L00") < block_text.find("R00")
    assert block_text.find("R00") < block_text.find("FOOTER")

    d = page.get_text("dict", sort=True)
    j = json.loads(page.get_text("json", sort=True))
    rd = page.get_text("rawdict", sort=True)
    rj = json.loads(page.get_text("rawjson", sort=True))
    span_seq = _span_texts(d)
    # all four structured variants use the identical span sequence
    assert _span_texts(j) == span_seq
    assert _span_texts(rd) == span_seq
    assert _span_texts(rj) == span_seq
    # the words follow the same column rule as the spans
    first_right_span = next(i for i, t in enumerate(span_seq) if t.startswith("R"))
    assert all(not t.startswith("R") for t in span_seq[:first_right_span])
    assert all(not t.startswith("L") for t in span_seq[first_right_span:])
    # word extraction and span extraction contain the same text content
    assert " ".join(words).split() == " ".join(span_seq).split()


def test_single_column_is_top_to_bottom():
    doc = pymupdf.open()
    page = doc.new_page()
    for i in range(5):
        page.insert_text((72, 80 + i * 30), f"line{i}")
    words = [w[4] for w in page.get_text("words", sort=True)]
    assert words == [f"line{i}" for i in range(5)]


def test_table_rows_stay_top_to_bottom():
    doc, page = _table_page()
    expected = [
        cell for row in range(6) for cell in (f"ACC{row:03d}", f"AMT{row:03d}")
    ]
    words = [w[4] for w in page.get_text("words", sort=True)]
    # cells of one row stay adjacent and rows keep their vertical order
    assert words == expected


def test_order_independent_of_rotation():
    ref_doc, ref_page = _two_column_page()
    ref_words = [w[4] for w in ref_page.get_text("words", sort=True)]
    ref_text = ref_page.get_text(sort=True)
    ref_blocks = [b[4] for b in ref_page.get_text("blocks", sort=True)]
    ref_spans = _span_texts(ref_page.get_text("dict", sort=True))

    for rotation in (90, 180, 270):
        doc, page = _two_column_page(rotate=rotation)
        assert page.rotation == rotation
        assert [w[4] for w in page.get_text("words", sort=True)] == ref_words
        assert page.get_text(sort=True) == ref_text
        assert [b[4] for b in page.get_text("blocks", sort=True)] == ref_blocks
        assert _span_texts(page.get_text("dict", sort=True)) == ref_spans


def test_sorting_does_not_lose_or_change_content():
    doc, page = _two_column_page()

    # words: same tuples, different order only
    assert sorted(map(tuple, page.get_text("words"))) == sorted(
        map(tuple, page.get_text("words", sort=True))
    )
    # blocks: same tuples, different order only
    assert sorted(map(tuple, page.get_text("blocks"))) == sorted(
        map(tuple, page.get_text("blocks", sort=True))
    )

    def span_bag(d):
        return sorted(
            (
                tuple(round(v, 6) for v in span["bbox"]),
                span["text"],
                span["font"],
                round(span["size"], 6),
            )
            for block in d["blocks"]
            if block.get("type") == 0
            for line in block["lines"]
            for span in line["spans"]
        )

    assert span_bag(page.get_text("dict")) == span_bag(
        page.get_text("dict", sort=True)
    )

    def char_bag(d):
        return sorted(
            (tuple(round(v, 6) for v in char["bbox"]), char["c"])
            for block in d["blocks"]
            if block.get("type") == 0
            for line in block["lines"]
            for span in line["spans"]
            for char in span["chars"]
        )

    # rawdict keeps every character and its bbox
    assert char_bag(page.get_text("rawdict")) == char_bag(
        page.get_text("rawdict", sort=True)
    )


def test_tolerance_reaches_words_sort():
    doc = pymupdf.open()
    page = doc.new_page()
    # AAA sits higher and to the right; BBB sits 4 pt lower and to the left.
    page.insert_text((72, 100), "AAA")
    page.insert_text((60, 104), "BBB")
    # small tolerance: different lines -> vertical order (top first)
    assert [w[4] for w in page.get_text("words", sort=True, tolerance=1)] == [
        "AAA",
        "BBB",
    ]
    # large tolerance: one line -> horizontal order (left first)
    assert [w[4] for w in page.get_text("words", sort=True, tolerance=5)] == [
        "BBB",
        "AAA",
    ]


def test_sort_false_keeps_unsorted_output():
    doc, page = _two_column_page()
    # sort=False must not invoke the reading-order reordering
    words = [w[4] for w in page.get_text("words")]
    assert words == [w[4] for w in page.get_text("words", sort=False)]
