from datetime import date

from app.geo import postal_code, postal_codes, region_for, unit_number
from app.models import ClosureReasonType, SafeGradeValue
from etl.hpb_sync import parse_feature
from etl.nea_sync import parse_date, parse_row
from etl.sfa_import import parse_grade

# Real record from data.gov.sg (Dates of Hawker Centres Closure)
ADAM = {
    "_id": 1, "serial_no": "1", "name": "Adam Road Food Centre",
    "q1_cleaningstartdate": "30/3/2026", "q1_cleaningenddate": "31/3/2026", "remarks_q1": "nil",
    "q2_cleaningstartdate": "8/6/2026", "q2_cleaningenddate": "8/6/2026", "remarks_q2": "nil",
    "q3_cleaningstartdate": "7/9/2026", "q3_cleaningenddate": "7/9/2026", "remarks_q3": "nil",
    "q4_cleaningstartdate": "7/12/2026", "q4_cleaningenddate": "8/12/2026", "remarks_q4": "nil",
    "other_works_startdate": "NA", "other_works_enddate": "NA", "remarks_other_works": "nil",
    "latitude_hc": "1.324131966", "longitude_hc": "103.8141632",
    "address_myenv": "2 Adam Road, Singapore 289876", "no_of_food_stalls": "32", "status": "Existing",
}


def test_parse_nea_row():
    centre, closures = parse_row(ADAM)
    assert centre["postal_code"] == "289876"
    assert centre["region"] == "Central"
    assert len(closures) == 4
    assert closures[3]["start_date"] == date(2026, 12, 7) and closures[3]["quarter"] == "Q4"
    assert all(c["reason_type"] == ClosureReasonType.SPRING_CLEANING for c in closures)


def test_other_works_rr_detection():
    row = {**ADAM, "other_works_startdate": "1/10/2026", "other_works_enddate": "31/12/2026",
           "remarks_other_works": "Repairs & Redecoration works"}
    _, closures = parse_row(row)
    assert closures[-1]["reason_type"] == ClosureReasonType.REPAIRS_AND_REDECORATION


def test_dates():
    assert parse_date("7/9/2026") == date(2026, 9, 7)
    assert parse_date("TBC") is None
    assert parse_date("31/2/2026") is None


def test_sfa_grades():
    assert parse_grade("A") == (SafeGradeValue.A, False)
    assert parse_grade("New (Under Review)") == (SafeGradeValue.NEW, True)
    assert parse_grade("Not Under SAFE") is None
    assert parse_grade("D") is None  # old system grade must not sneak in


def test_address_helpers():
    a = "15 JALAN TEPONG #03-19 JURONG FOOD HUB SINGAPORE 619336"
    assert postal_code(a) == "619336"
    assert unit_number(a) == "03-19"
    assert region_for(1.3483, 103.6831) == "West"
    assert region_for(1.3526, 103.9447) == "East"


def test_hpb_both_formats():
    flat = parse_feature({"geometry": {"coordinates": [103.8, 1.3]}, "properties": {
        "NAME": "Stall A", "ADDRESSPOSTALCODE": 69184, "ADDRESSFLOORNUMBER": "1", "ADDRESSUNITNUMBER": "23"}})
    assert flat["postal_code"] == "069184" and flat["unit_number"] == "01-23"
    kml = parse_feature({"geometry": {"coordinates": [103.8, 1.3, 0]}, "properties": {
        "Name": "kml_1", "Description": "<table><tr><th>NAME</th> <td>Stall B</td></tr><tr><th>ADDRESSPOSTALCODE</th><td>289876</td></tr></table>"}})
    assert kml["outlet_name"] == "Stall B" and kml["postal_code"] == "289876"


def test_hpb_live_format():
    # Shape of the live data.gov.sg feed: postal codes as strings (sometimes missing the
    # leading zero), unpadded floor/unit, double units, and the same DESCRIPTION everywhere
    o = parse_feature({"geometry": {"coordinates": [103.8, 1.3]}, "properties": {
        "NAME": "Stall C", "ADDRESSPOSTALCODE": "38983", "ADDRESSFLOORNUMBER": "1", "ADDRESSUNITNUMBER": "5, 12",
        "DESCRIPTION": "Choose healthier options from F&B outlets under HPB's Healthier Dining Programme"}})
    assert o["postal_code"] == "038983" and o["unit_number"] == "01-05"
    assert o["participation_category"] is None
    basement = parse_feature({"properties": {"NAME": "D", "ADDRESSFLOORNUMBER": "B1", "ADDRESSUNITNUMBER": "K7"}})
    assert basement["unit_number"] == "B1-K7"


def test_hpb_matches_by_postal_code_only():
    from sqlalchemy.orm import Session

    from app.db import Base, make_engine
    from app.models import HawkerCentre, ParticipatingStall
    from etl.hpb_sync import load

    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as db:
        db.add(HawkerCentre(id=1, centre_name="X", postal_code="440084", region="East", latitude=1.3025, longitude=103.9067))
        db.commit()
        here = {"geometry": {"coordinates": [103.9067, 1.3025]}, "properties": {"NAME": "In centre", "ADDRESSPOSTALCODE": "440084"}}
        next_door = {"geometry": {"coordinates": [103.9068, 1.3026]}, "properties": {"NAME": "Mall next door", "ADDRESSPOSTALCODE": "449408"}}
        assert load(db, [here, next_door]) == 1
        assert [p.outlet_name for p in db.query(ParticipatingStall)] == ["In centre"]


def test_address_helpers_real_sfa_and_nea_formats():
    assert unit_number("1 KADAYANALLUR STREET 056,Singapore 069184") == "056"
    assert unit_number("51 OLD AIRPORT ROAD #01-121,Singapore 390051") == "01-121"
    assert unit_number("21 BEDOK NORTH STREET 4,Singapore 460021") is None  # street number, not a stall
    assert postal_codes("Blk 13/14, Haig Road, Singapore 430013/430014") == ["430013", "430014"]
    assert postal_code("Blk 13/14, Haig Road, Singapore 430013/430014") == "430013"


# Three rows as openpyxl returns them from SFA's real "Export to Excel" file: every cell
# OOXML-escaped, no postal code column, an SNO column and a "Last updated" footer.
SFA_EXPORT = (
    "SNO,Establishment Address,Grade,Licence Number,Licensee Name,Business Name,Type of Food Business\n"
    "1,14_x0020_HAIG_x0020_ROAD_x0020__x0023_01-15_x002C_Singapore_x0020_430014,A,HR40115001,"
    "TAN_x0020_AH_x0020_HOCK,Ah_x0020_Hock_x0020_Fried_x0020_Hokkien_x0020_Mee_x0020__x0026__x0020_Orh_x0020_Luak,"
    "NEA_x0020_Managed_x0020_Foodstall\n"
    "2,1_x0020_KADAYANALLUR_x0020_STREET_x0020_056_x002C_Singapore_x0020_069184,New,KS10056002,"
    "LIM_x0020_MEI_x0020_LING,NA,NEA_x0020_Managed_x0020_Foodstall\n"
    "3,335_x0020_SMITH_x0020_STREET_x0020__x0023_02-219_x002C_CHINATOWN_x0020_COMPLEX_x002C_Singapore_x0020_050335,"
    "B,SM102219004,ONG_x0020_KIM_x0020_SENG,Kim_x0027_s_x0020_Kway_x0020_Chap,NEA_x0020_Managed_x0020_Foodstall\n"
    "Last_x0020_updated_x0020_on_x0020_20_x0020_October_x0020_2026,,,,,,\n"
)


def test_sfa_real_export_format(tmp_path):
    from sqlalchemy.orm import Session

    from app.controllers.hygiene_controller import HygieneController
    from app.db import Base, make_engine
    from app.models import HawkerCentre, Stall
    from etl.sfa_import import load, read_rows

    path = tmp_path / "LicensedFoodEstablishmentsSearch.csv"
    path.write_text(SFA_EXPORT, encoding="utf-8")
    rows = read_rows(path)
    assert len(rows) == 3  # footer has no licence number
    assert rows[0]["establishmentaddress"] == "14 HAIG ROAD #01-15,Singapore 430014"

    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as db:
        db.add_all([
            # Two-block centre: NEA's primary postal code is 430013, the stall is in block 14
            HawkerCentre(id=54, centre_name="Haig Road Blk 13/14", postal_code="430013", region="East",
                         street_address="Blk 13/14, Haig Road, Singapore 430013/430014", latitude=1.31, longitude=103.9),
            HawkerCentre(id=2, centre_name="Maxwell Food Centre", postal_code="069184", region="Central",
                         street_address="1, Kadayanallur Street, Singapore 069184", latitude=1.28, longitude=103.84),
        ])
        db.commit()
        assert load(db, rows, date(2026, 10, 20)) == 2  # Chinatown Complex isn't loaded here, so skipped

        haig = db.query(Stall).filter_by(licence_number="HR40115001").one()
        assert (haig.centre_id, haig.unit_number) == (54, "01-15")
        assert haig.stall_name == "Ah Hock Fried Hokkien Mee & Orh Luak"
        assert haig.licensee.licensee_name == "TAN AH HOCK"
        assert HygieneController.current_grade(haig.licensee).grade_value == SafeGradeValue.A

        maxwell = db.query(Stall).filter_by(licence_number="KS10056002").one()
        assert maxwell.unit_number == "056"
        assert maxwell.stall_name == "LIM MEI LING"  # business name "NA" falls back to licensee
        assert HygieneController.current_grade(maxwell.licensee).grade_value == SafeGradeValue.NEW


def test_not_under_safe_in_latest_export_clears_current_grade():
    from sqlalchemy.orm import Session

    from app.controllers.hygiene_controller import HygieneController
    from app.db import Base, make_engine
    from app.models import HawkerCentre, Stall
    from etl.sfa_import import load

    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as db:
        db.add(HawkerCentre(id=1, centre_name="X", postal_code="289876", region="Central", latitude=1.3, longitude=103.8))
        db.commit()
        row = {"postalcode": "289876", "establishmentaddress": "2 ADAM RD #01-02 SINGAPORE 289876", "licencenumber": "L1", "businessname": "S", "grade": "B"}
        load(db, [row], date(2026, 8, 1))
        stall = db.query(Stall).one()
        assert HygieneController.current_grade(stall.licensee).grade_value == SafeGradeValue.B
        load(db, [{**row, "grade": "Not Under SAFE"}], date(2026, 10, 1), suspended={"L1"})
        db.refresh(stall.licensee)
        assert HygieneController.current_grade(stall.licensee) is None
        tr = HygieneController.track_record(stall)
        assert tr.suspended_past_year and tr.last_updated == date(2026, 10, 1)
        assert [g.grade_value for g in tr.grade_history] == [SafeGradeValue.B]
