"""Profile avatar catalog and legacy ID resolver."""

from aoep_shared.avatars import (
    AVATAR_CATALOG,
    DEFAULT_AVATAR_ID,
    LEGACY_AVATAR_ALIASES,
    avatar_asset_path,
    avatar_catalog_list,
    avatar_styles,
    get_avatar,
    resolve_avatar,
    resolve_avatar_id,
)


def test_catalog_has_realistic_and_cute():
    styles = {e.style for e in AVATAR_CATALOG.values()}
    assert styles == {"realistic", "cute"}
    assert len(AVATAR_CATALOG) >= 16
    realistic = [e for e in AVATAR_CATALOG.values() if e.style == "realistic"]
    cute = [e for e in AVATAR_CATALOG.values() if e.style == "cute"]
    assert len(realistic) >= 8
    assert len(cute) >= 8


def test_default_avatar_exists():
    assert DEFAULT_AVATAR_ID in AVATAR_CATALOG
    assert get_avatar(None).id == DEFAULT_AVATAR_ID
    assert get_avatar("").id == DEFAULT_AVATAR_ID


def test_resolve_known_id():
    assert resolve_avatar_id("c-peach") == "c-peach"
    r = resolve_avatar("r-amir")
    assert r["id"] == "r-amir"
    assert r["path"] == "/avatars/r-amir.svg"
    assert r["style"] == "realistic"
    assert "Amir" in r["alt"]


def test_legacy_aliases_migrate():
    assert resolve_avatar_id("logo") == "c-sunny"
    assert resolve_avatar_id("mascot") == "c-sunny"
    assert resolve_avatar_id("presenter-male") == "r-amir"
    assert resolve_avatar_id("initials") == DEFAULT_AVATAR_ID
    assert resolve_avatar_id("avatar:logo") == "c-sunny"
    assert resolve_avatar_id("totally-unknown-xyz") == DEFAULT_AVATAR_ID


def test_asset_path_and_catalog_list():
    assert avatar_asset_path("r-nova") == "/avatars/r-nova.svg"
    items = avatar_catalog_list()
    assert len(items) == len(AVATAR_CATALOG)
    cute_only = avatar_catalog_list(style="cute")
    assert all(i["style"] == "cute" for i in cute_only)
    assert {s["id"] for s in avatar_styles()} == {"realistic", "cute"}


def test_every_catalog_id_has_unique_label():
    labels = [e.label for e in AVATAR_CATALOG.values()]
    assert len(labels) == len(set(labels))
    assert all(e.alt for e in AVATAR_CATALOG.values())
    # Legacy targets must point at real catalog entries.
    for target in LEGACY_AVATAR_ALIASES.values():
        assert target in AVATAR_CATALOG


def test_live_room_join_accepts_avatar_id():
    from aoep_shared.live_room import LiveRoomStore

    store = LiveRoomStore()
    room = store.open_room(
        title="Avatar room",
        room_size=4,
        creator_name="Host",
        room_id="avatar-room-1",
        class_id="",
        session_id="sess-avatar",
        lesson_id="lesson-avatar",
    )
    p = store.join(room.room_id, "Ada", identity="ada", avatar_id="presenter-female")
    assert p.avatar_id == "r-sofia"
    assert p.to_dict()["avatar_id"] == "r-sofia"
