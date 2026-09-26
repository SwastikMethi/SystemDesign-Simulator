from backend.content import load_challenge
from backend.workloads import bundle_hash, generate_case, workload_hash


def test_seed_repeatability_and_boundaries():
    challenge = load_challenge("product-catalogue")
    a = generate_case(challenge, "burst", 101)
    b = generate_case(challenge, "burst", 101)
    assert workload_hash(a) == workload_hash(b)
    assert bundle_hash([a]) == bundle_hash([b])
    assert [r.time_us for r in a.arrivals[:5]] == [21756, 86174, 92211, 121687, 123511]
    assert all(0 <= r.time_us < 360_000_000 for r in a.arrivals)
    assert all(r.segment_id == "120-180" for r in a.arrivals if 180_000_000 <= r.time_us < 240_000_000)
    assert all(r.segment_id == "180-300" for r in a.arrivals if 240_000_000 <= r.time_us < 360_000_000)
    assert all(r.time_us < 180_000_000 for r in a.arrivals if r.segment_id == "0-120")
    assert all(r.time_us < 240_000_000 for r in a.arrivals if r.segment_id == "120-180")


def test_uniform_and_zipf_keys():
    uniform = generate_case(load_challenge("team-notes"), "steady", 101)
    zipf = generate_case(load_challenge("product-catalogue"), "steady", 101)
    assert len({r.key for r in uniform.arrivals}) > 800
    assert sum(r.key == "products:0" for r in zipf.arrivals) > sum(r.key == "products:999" for r in zipf.arrivals)


def test_write_payload_stable_and_unique_creates():
    case = generate_case(load_challenge("url-shortener"), "steady", 101)
    writes = [r for r in case.arrivals if r.operation_id == "create_code"]
    assert len({r.key for r in writes}) == len(writes)
    assert all(r.payload_id for r in writes)
    photo = generate_case(load_challenge("photo-delivery"), "steady", 101)
    uploads = [r for r in photo.arrivals if r.operation_id == "put_photo"]
    assert len({r.key for r in uploads}) == len(uploads)
