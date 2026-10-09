from report import render_report


def test_render_report(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("the cat sat on the mat the cat slept")
    assert render_report(sample, n=3) == "the 3\ncat 2\nmat 1"
