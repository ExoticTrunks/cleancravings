from etl.hpb_partners_sync import (
    FUZZY_MIN,
    Candidate,
    distinctive,
    drop_duplicates,
    fuzzy_accepts,
    match_outlets,
    normalise,
    parse_row,
    read_overrides,
)

# Shape of a hawker row in data.gov.sg d_c475b9170c08f90580f4041bffd51639
ROW = {
    "_id": 1, "Company_Name": None, "Brand_Name": "Fu Zhou Fishball wanton Noodles", "FnB_Setting": "Hawker",
    "Dining_Concept": "Non-Halal", "Category": "Hawker Food", "Name_of_Outlet": "Maxwell Food Centre",
    "Outlet_Address": "1 Kadayanallur Street #01-01 Singapore 069184", "Regions": "Central",
    "Menu_Item_Endorsement_Criteria": "Lower in calories,  Lower in calories and sodium",
}


def outlet(oid: int, name: str, postal: str = "069184") -> dict:
    return {"outlet_id": oid, "outlet_name": name, "postal_code": postal}


def test_normalise_ignores_case_punctuation_spacing():
    assert normalise("Ah Hock's Mee-Pok") == normalise("AH HOCKS MEE POK") == "ahhocksmeepok"
    assert normalise("Amy’s Laksa") == normalise("Amy's Laksa")
    assert normalise("Ban Mian. Fish Soup") == normalise("Ban Mian Fish Soup")
    assert normalise(None) == ""


def test_normalise_strips_company_suffixes():
    for name in ("Poona Punjabi Dhaba Pte Ltd", "Poona Punjabi Dhaba Pte. Ltd.", "Poona Punjabi Dhaba LLP",
                 "Poona Punjabi Dhaba Enterprise", "Poona Punjabi Dhaba Trading", "Poona Punjabi Dhaba Enterprise Pte Ltd"):
        assert normalise(name) == "poonapunjabidhaba", name
    assert normalise("Trading Post Kopi") == "tradingpostkopi"  # only a trailing suffix is stripped


def test_distinctive_drops_generic_food_words():
    assert distinctive("Mei Xing Yong Tau Foo") == "meixing"
    assert distinctive("Hong Heng Teo Chew Fishball Noodle") == "hongheng"
    assert distinctive("Tihir Indian Muslim Food Pte Ltd") == "tihir"
    assert distinctive("Hainanese Chicken Rice, Porridge, Noodle") == ""


def test_fuzzy_threshold():
    assert not fuzzy_accepts("Kun Kee", "Kun Kee", FUZZY_MIN - 0.001, 0.0)
    assert fuzzy_accepts("Kun Kee", "Kun Kee", FUZZY_MIN, 0.0)
    assert not fuzzy_accepts("Kun Kee", "Kun Kee", 0.95, 0.90)  # not clearly better than the runner-up
    # Full names score 0.93, but the names without dish words ("hongxing" vs "hongheng") don't agree
    assert not fuzzy_accepts("Hong Xing Teochew Fishball Noodle", "Hong Heng Teo Chew Fishball Noodle", 0.931, 0.632)
    assert fuzzy_accepts("Zheng Tian Tian Yong Tau Fu", "Zheng Tian Tian Yong Tau Foo", 0.933, 0.389)
    # Nothing distinctive on one side: the full-name score decides
    assert fuzzy_accepts("Hainanese Chicken Rice, Porridge, Noodle", "Xiang Ji Hainanese Chicken Rice. Porridge. Noodle", 0.907, 0.407)


def test_drop_duplicates_only_drops_exact_copies():
    rows = [ROW, {**ROW, "_id": 2}, {**ROW, "_id": 3, "Menu_Item_Endorsement_Criteria": "Lower in calories"}]
    assert [r["_id"] for r in drop_duplicates(rows)] == [1, 3]


def test_parse_row():
    o = parse_row(ROW)
    assert o["outlet_name"] == "Fu Zhou Fishball wanton Noodles" and o["postal_code"] == "069184"
    assert o["participation_category"] == "Lower in calories, Lower in calories and sodium"
    assert o["halal"] is False and "cuisine" not in o  # Category is always "Hawker Food", so it isn't used
    assert parse_row({**ROW, "FnB_Setting": "Hawker "}) is not None  # setting values have stray spaces
    assert parse_row({**ROW, "FnB_Setting": "Bakery "}) is None
    assert parse_row({**ROW, "Dining_Concept": "Halal"})["halal"] is True
    assert parse_row({**ROW, "Dining_Concept": None})["halal"] is None  # unknown stays None, never False
    assert parse_row({**ROW, "Dining_Concept": "Muslim-owned"})["halal"] is None


STALLS = [
    Candidate(1, 2, "FU JI FISHBALL WANTON NOODLE", "KS10101001"),
    Candidate(2, 2, "Zheng Tian Tian Yong Tau Foo", "KS10102001"),
    Candidate(3, 2, "Wang Wang", "KS10103001"),
    Candidate(4, 2, "Economic Food", "KS10104001"),
    Candidate(5, 2, "Economic Food", "KS10105001"),
]
CENTRES = {"069184": 2}


def test_match_outlets_methods():
    results = match_outlets(
        [outlet(10, "WANG-WANG"), outlet(11, "Zheng Tian Tian Yong Tau Fu"), outlet(12, "Fu Zhou Fishball Wanton Noodles"),
         outlet(13, "Economic Food"), outlet(14, "Wang Wang"), outlet(15, "Seah Im Stall", postal="099114")],
        CENTRES, STALLS,
    )
    got = {m.outlet["outlet_id"]: (m.method, m.stall.stall_id if m.stall else None) for m in results}
    assert got[10] == ("exact", 3)
    assert got[11] == ("fuzzy", 2)
    assert got[12] == ("centre", None)  # 0.86 overall, and "fuzhou" vs "fuji" differ
    assert got[13] == ("centre", None)  # two SFA stalls with this name at the centre: ambiguous
    assert got[14] == ("centre", None)  # stall 3 already claimed by outlet 10
    assert got[15] == ("unmatched", None)


def test_overrides_beat_the_algorithm(tmp_path):
    outlets = [outlet(10, "Wang Wang"), outlet(12, "Fu Zhou Fishball Wanton Noodles"), outlet(20, "Renamed Stall")]
    path = tmp_path / "overrides.csv"
    path.write_text(
        "outlet_id,outlet_name,sfa_licence_number,decision,reason\n"
        "10,Wang Wang,KS10103001,reject,wrong stall\n"
        "12,Fu Zhou Fishball Wanton Noodles,ks10101001,accept,same owner per HPB\n"
        "20,Old Name,KS10102001,accept,outlet id now points at a different outlet\n",
        encoding="utf-8",
    )
    decisions = read_overrides(outlets, path)
    assert decisions == {(10, "KS10103001"): "reject", (12, "KS10101001"): "accept"}  # stale row 20 skipped
    got = {m.outlet["outlet_id"]: (m.method, m.stall.stall_id if m.stall else None)
           for m in match_outlets(outlets, CENTRES, STALLS, decisions)}
    assert got[10] == ("centre", None)
    assert got[12] == ("override", 1)


def test_load_writes_links_halal_and_method():
    from sqlalchemy.orm import Session

    from app.db import Base, make_engine
    from app.models import HawkerCentre, Licensee, ParticipatingStall, Stall
    from etl.hpb_partners_sync import load

    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as db:
        db.add(HawkerCentre(id=2, centre_name="Maxwell Food Centre", postal_code="069184", region="Central",
                            latitude=1.28, longitude=103.84))
        for lic, name, licensee in [("L1", "Wang Wang", "TAN AH KOW"), ("L2", "Kun Kee", "LIM BEE"), ("L3", "LIM MEI LING", "LIM MEI LING")]:
            db.add(Licensee(licence_number=lic, licensee_name=licensee))
            db.add(Stall(centre_id=2, licence_number=lic, stall_name=name, halal=True))
        db.commit()
        outlets = [
            {**outlet(1, "Wang Wang"), "participation_category": "Lower in calories", "halal": False},
            {**outlet(2, "Kun Kee"), "participation_category": None, "halal": None},
            # Matches only the stall whose name is the licensee's own name: never a candidate
            {**outlet(3, "Lim Mei Ling"), "participation_category": None, "halal": True},
            {**outlet(4, "Elsewhere", postal="099114"), "participation_category": None, "halal": True},
        ]
        counts = load(db, outlets, overrides=None)
        assert (counts["exact"], counts["centre"], counts["unmatched"]) == (2, 1, 1)
        stalls = {s.licence_number: s for s in db.query(Stall)}
        assert stalls["L1"].halal is False
        assert stalls["L2"].halal is None  # unknown in the feed: reset, not left at the old True
        assert stalls["L3"].halal is None
        rows = {p.outlet_name: p for p in db.query(ParticipatingStall)}
        assert set(rows) == {"Wang Wang", "Kun Kee", "Lim Mei Ling"}
        assert rows["Wang Wang"].match_method == "exact" and rows["Wang Wang"].stall_id == stalls["L1"].id
        assert rows["Lim Mei Ling"].stall_id is None and rows["Lim Mei Ling"].match_method is None
