"""Catalog model + store CRUD + JSON persistence tests."""

from curriculum.catalog import CatalogStore, Course, Module, Program


def test_course_crud():
    store = CatalogStore()
    c = store.create_course(Course(title="Algebra I", subject="math",
                                   modules=[Module(title="Intro", deck_id="d1")]))
    assert store.get_course(c.course_id).title == "Algebra I"
    assert len(store.list_courses()) == 1
    assert store.delete_course(c.course_id) is True
    assert store.get_course(c.course_id) is None


def test_program_crud_and_rules():
    store = CatalogStore()
    c1 = store.create_course(Course(title="Basics", subject="math"))
    c2 = store.create_course(Course(title="Advanced", subject="math"))
    p = store.create_program(Program(
        title="Math Track", audience="grade-9",
        course_ids=[c1.course_id, c2.course_id],
        adaptive_rules={"prereq_mastery": {c2.course_id: 0.7}},
    ))
    got = store.get_program(p.program_id)
    assert got.course_ids == [c1.course_id, c2.course_id]
    assert got.adaptive_rules["prereq_mastery"][c2.course_id] == 0.7


def test_persistence_roundtrip(tmp_path):
    path = str(tmp_path / "catalog.json")
    store = CatalogStore(path=path)
    c = store.create_course(Course(title="Bio", subject="biology"))
    store.create_program(Program(title="Sci", course_ids=[c.course_id]))
    # _autosave wrote the file; reload into a fresh store.
    reloaded = CatalogStore(path=path)
    assert reloaded.get_course(c.course_id).subject == "biology"
    assert len(reloaded.list_programs()) == 1


def test_module_references_deck_or_scene():
    m = Module(title="Slide deck", deck_id="deck-123")
    assert m.deck_id == "deck-123" and m.scene_id is None
