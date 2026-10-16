"""M2: real photo upload, the checks on pickup and delivery, location pings and the track."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from tests.helpers import (
    ADMIN,
    FACTORY,
    OTHER_FACTORY,
    T1,
    T2,
    accept_first_offer,
    fund,
    leg,
    photo,
    scalar,
)

WEIGHT_HELP = "Weight must be a whole number of kilograms between 1 and 100,000"


def fields(r):
    body = r.json()
    assert isinstance(body["detail"], str)
    return {e["field"]: e["message"] for e in body["errors"]}


async def accepted(api, world):
    await fund(api, world)
    await accept_first_offer(api, world)


async def upload_url(api, world, kind="pickup", content_type="image/jpeg", headers=T1):
    r = await api.post(
        f"/api/jobs/{world.job_id}/photos/upload-url",
        headers=headers,
        json={"kind": kind, "content_type": content_type},
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- the dev upload route ---------------------------------------------------------------


async def test_a_photo_really_uploads_and_comes_back(api, world):
    await accepted(api, world)
    up = await upload_url(api, world, content_type="image/png")
    assert up["path"].endswith(".png") and up["upload_url"] == f"/api/dev-upload/{up['path']}"
    png = {**T1, "Content-Type": "image/png"}
    put = await api.put(up["upload_url"], headers=png, content=b"png!")
    assert put.status_code == 204
    got = await api.get(up["upload_url"])  # an img tag sends no token
    assert got.status_code == 200 and got.content == b"png!"
    assert got.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    "content_type, size, message",
    [
        ("text/plain", 1, "Add a photo (JPEG, PNG or WebP, up to 5 MB)"),
        ("image/png", 1, "Add a photo (JPEG, PNG or WebP, up to 5 MB)"),  # path says jpg
        ("image/jpeg", 0, "The photo file is empty"),
        ("image/jpeg", 5 * 1024 * 1024 + 1, "Photo must be 5 MB or smaller"),
    ],
    ids=["not-an-image", "type-differs-from-path", "empty", "over-5mb"],
)
async def test_the_upload_route_checks_type_and_size(api, world, content_type, size, message):
    data = b"x" * size
    await accepted(api, world)
    up = await upload_url(api, world)
    r = await api.put(up["upload_url"], headers={**T1, "Content-Type": content_type}, content=data)
    assert r.status_code == 422
    assert fields(r) == {"photo": message}


async def test_only_good_photo_paths_are_served_and_never_on_cloud_run(api, world, monkeypatch):
    assert (await api.get("/api/dev-upload/../../.env")).status_code == 404
    assert (await api.get("/api/dev-upload/jobs/x/pickup/y.jpg")).status_code == 404
    await accepted(api, world)
    up = await upload_url(api, world)
    monkeypatch.setenv("K_SERVICE", "residue-api")
    assert (await api.get(up["upload_url"])).status_code == 404


async def test_a_content_type_that_is_not_an_image_is_refused_with_the_valid_ones(api, world):
    await accepted(api, world)
    r = await api.post(
        f"/api/jobs/{world.job_id}/photos/upload-url", headers=T1,
        json={"kind": "pickup", "content_type": "image/gif"},
    )
    assert r.status_code == 422
    assert fields(r)["content_type"].startswith("Content type must be one of")


# --- pickup and delivery checks ---------------------------------------------------------


async def test_pickup_needs_the_photo_to_be_uploaded_first(api, world):
    await accepted(api, world)
    up = await upload_url(api, world)  # a path, but nothing was uploaded to it
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(up["path"], 2400))
    assert r.status_code == 422
    assert fields(r) == {"photo_path": "Upload the photo first"}
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=ADMIN)).json()["state"] == "accepted"


async def test_an_empty_or_oversized_file_is_refused_at_pickup(api, world):
    await accepted(api, world)
    path = await photo(api, world, "pickup", T1)
    api.storage.blobs[path] = b""
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(path, 2400))
    assert fields(r) == {"photo_path": "The photo file is empty"}
    api.storage.blobs[path] = b"x" * (5 * 1024 * 1024 + 1)
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(path, 2400))
    assert fields(r) == {"photo_path": "Photo must be 5 MB or smaller"}


async def test_a_photo_for_the_wrong_step_is_explained(api, world):
    await accepted(api, world)
    delivery = await photo(api, world, "delivery", T1)
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(delivery, 2400))
    assert "not an upload for this pickup step" in fields(r)["photo_path"]


@pytest.mark.parametrize("weight", [0, -5, 100_001, 12.5, "heavy", None])
async def test_weights_must_be_whole_kilograms_in_range(api, world, weight):
    await accepted(api, world)
    path = await photo(api, world, "pickup", T1)
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(path, weight))
    assert r.status_code == 422
    assert fields(r) == {"weight_kg": WEIGHT_HELP}


async def test_location_is_required_and_must_be_real(api, world):
    await accepted(api, world)
    path = await photo(api, world, "pickup", T1)
    body = leg(path, 2400)
    del body["lat"], body["lon"]
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=body)
    assert fields(r) == {
        "lat": "Allow location access to record this step",
        "lon": "Allow location access to record this step",
    }
    r = await api.post(
        f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(path, 2400, lat=95, lon=200)
    )
    assert fields(r) == {
        "lat": "Latitude must be between -90 and 90",
        "lon": "Longitude must be between -180 and 180",
    }
    r = await api.post(
        f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(path, 2400, accuracy_m=-1)
    )
    assert "accuracy_m" in fields(r)


async def test_a_refused_pickup_changes_nothing(api, world):
    await accepted(api, world)
    path = await photo(api, world, "pickup", T1)
    await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(path, 0))
    job = uuid.UUID(world.job_id)
    assert await scalar(api, "SELECT count(*) FROM photos WHERE job_id = :j", j=job) == 0
    assert await scalar(api, "SELECT count(*) FROM job_locations WHERE job_id = :j", j=job) == 0


# --- where the transporter was ------------------------------------------------------------


async def test_pickup_and_delivery_store_where_the_truck_was(api, world):
    await accepted(api, world)
    farm = await api.session.execute(
        text("SELECT lat, lon FROM lots WHERE id = :l"), {"l": uuid.UUID(world.lot_id)}
    )
    lat, lon = farm.one()
    p = await photo(api, world, "pickup", T1)
    r = await api.post(
        f"/api/jobs/{world.job_id}/pickup",
        headers=T1,
        json=leg(p, 2400, lat=lat, lon=lon, accuracy_m=12),
    )
    assert r.status_code == 200, r.text
    d = await photo(api, world, "delivery", T1)
    far = await api.post(  # 150 km from the factory
        f"/api/jobs/{world.job_id}/deliver", headers=T1, json=leg(d, 2450, lat=32.75, lon=74.38)
    )
    assert far.status_code == 200  # never blocked
    rows = (
        await api.session.execute(
            text("SELECT kind, distance_from_target_m, accuracy_m FROM job_locations "
                 "WHERE job_id = :j ORDER BY recorded_at"),
            {"j": uuid.UUID(world.job_id)},
        )
    ).all()
    assert [r.kind for r in rows] == ["pickup", "delivery"]
    assert rows[0].distance_from_target_m < 5 and rows[0].accuracy_m == 12
    assert rows[1].distance_from_target_m > 100_000


async def test_the_job_lists_its_photos_with_a_url(api, world):
    await accepted(api, world)
    up = await upload_url(api, world)
    await api.put(up["upload_url"], headers={**T1, "Content-Type": "image/jpeg"}, content=b"jpg")
    await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(up["path"], 2400))
    job = (await api.get(f"/api/jobs/{world.job_id}", headers=FACTORY)).json()
    assert [(p["kind"], p["weight_kg"], p["url"]) for p in job["photos"]] == [
        ("pickup", 2400, up["upload_url"])
    ]


# --- live pings ---------------------------------------------------------------------------


async def ping(api, world, headers=T1, **over):
    return await api.post(
        f"/api/jobs/{world.job_id}/location", headers=headers,
        json={"lat": 31.41, "lon": 74.39, "accuracy_m": 20, **over},
    )


async def test_a_ping_is_recorded_then_throttled_then_recorded_again(api, world):
    await accepted(api, world)
    assert (await ping(api, world)).json() == {"recorded": True}
    assert (await ping(api, world)).json() == {"recorded": False}  # too soon
    await api.session.execute(
        text("UPDATE job_locations SET recorded_at = :t WHERE job_id = :j"),
        {"t": datetime.now(UTC) - timedelta(seconds=30), "j": uuid.UUID(world.job_id)},
    )
    assert (await ping(api, world)).json() == {"recorded": True}
    pings = await scalar(
        api,
        "SELECT count(*) FROM job_locations WHERE kind = 'ping' AND job_id = :j",
        j=uuid.UUID(world.job_id),
    )
    assert pings == 2


async def test_pings_are_only_for_the_assigned_transporter_while_the_job_is_moving(api, world):
    await fund(api, world)  # offered, not accepted yet
    assert (await ping(api, world)).status_code == 404  # not yet their job
    await accept_first_offer(api, world)
    assert (await ping(api, world, headers=T2)).status_code == 404
    assert (await ping(api, world, lat=123)).status_code == 422
    assert (await ping(api, world)).status_code == 200


async def test_no_pings_once_the_load_is_delivered(api, world):
    from tests.helpers import move_to_delivered

    await move_to_delivered(api, world)
    r = await ping(api, world)
    assert r.status_code == 409
    assert "in progress" in r.json()["detail"]


# --- the track and the map data -----------------------------------------------------------


async def test_the_track_gives_the_map_its_points_and_a_rough_arrival_time(api, world):
    await accepted(api, world)
    await ping(api, world)
    track = (await api.get(f"/api/jobs/{world.job_id}/track", headers=ADMIN)).json()
    assert track["heading_to"] == "pickup" and track["state"] == "accepted"
    assert len(track["points"]) == 1 and track["last"]["kind"] == "ping"
    assert track["distance_to_target_km"] is not None and track["eta_minutes"] >= 1
    assert track["factory"]["name"] == "Test Factory"
    p = await photo(api, world, "pickup", T1)
    await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(p, 2400))
    after = (await api.get(f"/api/jobs/{world.job_id}/track", headers=FACTORY)).json()
    assert (after["heading_to"], len(after["points"])) == ("factory", 2)
    assert after["pickup_off_site_m"] is not None and after["delivery_off_site_m"] is None


async def test_who_may_see_a_track(api, world):
    await accepted(api, world)
    url = f"/api/jobs/{world.job_id}/track"
    assert (await api.get(url, headers=ADMIN)).status_code == 200
    assert (await api.get(url, headers=FACTORY)).status_code == 200
    assert (await api.get(url, headers=OTHER_FACTORY)).status_code == 404
    assert (await api.get(url, headers=T1)).status_code == 403


async def test_the_overview_lists_moving_loads_and_a_factory_sees_only_its_own(api, world):
    await accepted(api, world)
    await ping(api, world)
    rows = (await api.get("/api/tracking/active", headers=ADMIN)).json()
    mine = next(r for r in rows if r["job_id"] == world.job_id)
    assert mine["heading_to"] == "pickup" and mine["last"]["lat"] == 31.41
    own = (await api.get("/api/tracking/active", headers=FACTORY)).json()
    assert [r["job_id"] for r in own] == [
        world.job_id
    ]
    assert (await api.get("/api/tracking/active", headers=OTHER_FACTORY)).json() == []


# --- weighbridge confirmation messages ----------------------------------------------------


async def test_confirm_reports_the_weight_and_reason_fields(api, world):
    from tests.helpers import move_to_delivered

    await move_to_delivered(api, world)
    url = f"/api/jobs/{world.job_id}/confirm"
    bad = await api.post(url, headers=FACTORY, json={"accept": True, "final_weight_kg": 0})
    assert fields(bad) == {"final_weight_kg": WEIGHT_HELP}
    short = await api.post(url, headers=FACTORY, json={"accept": False, "reason": "ab"})
    assert fields(short) == {"reason": "Give a reason of at least 3 characters (at most 500)"}
