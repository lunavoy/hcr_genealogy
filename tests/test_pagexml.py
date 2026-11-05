from pathlib import Path

from database.pagexml import load_pagexml


def test_load_pagexml_preserves_polygons_baselines_and_words(tmp_path: Path):
    source = tmp_path / "page.xml"
    source.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
  <Page imageFilename="page.jpg">
    <TextRegion id="r1">
      <Coords points="10,20 200,20 200,100 10,100"/>
      <TextLine id="l1">
        <Coords points="12,30 198,30 198,55 12,55"/>
        <Baseline points="12,50 198,50"/>
        <Word id="w1">
          <Coords points="15,32 40,32 40,52 15,52"/>
          <TextEquiv><Unicode>Maria</Unicode></TextEquiv>
        </Word>
      </TextLine>
    </TextRegion>
  </Page>
</PcGts>
""",
        encoding="utf-8",
    )

    records = load_pagexml(source, "page.jpg")

    assert records[0]["source_image"] == "page.jpg"
    assert records[0]["polygon"] == [[10, 20], [200, 20], [200, 100], [10, 100]]
    assert records[0]["lines"][0]["baseline"] == [[12, 50], [198, 50]]
    assert records[0]["words"][0]["text"] == "Maria"
    assert records[0]["words"][0]["points"][0] == [15, 32]
