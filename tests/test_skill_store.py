from skill_factory.models import SkillMeta, SkillSpec, TestResult
from skill_factory.skill_store import SkillStore, slugify


def test_slugify():
    assert slugify("QNB Specialist Analyst!!") == "qnb-specialist-analyst"
    assert slugify("  Already-Kebab  ") == "already-kebab"
    assert slugify("a/b c") == "a-b-c"


def _spec(name="demo-skill"):
    return SkillSpec(name=name, description="Use when demoing.", tags=["t1"], skill_type="workflow")


def test_save_and_load_roundtrip(tmp_path):
    store = SkillStore(tmp_path)
    meta = SkillMeta.from_spec(_spec(), model="m")
    v = store.save_new_version("demo-skill", "---\nname: demo-skill\n---\nbody", meta)
    assert v == 1
    content, loaded = store.load("demo-skill")
    assert "body" in content
    assert loaded.name == "demo-skill"
    assert loaded.tags == ["t1"]
    assert loaded.model == "m"


def test_versioning_increments(tmp_path):
    store = SkillStore(tmp_path)
    meta = SkillMeta.from_spec(_spec())
    assert store.save_new_version("demo-skill", "a", meta) == 1
    assert store.save_new_version("demo-skill", "b", SkillMeta.from_spec(_spec())) == 2
    assert store.versions("demo-skill") == [1, 2]
    assert store.latest_version("demo-skill") == 2
    assert store.load_content("demo-skill", 1) == "a"
    assert store.load_content("demo-skill") == "b"  # latest


def test_library_listing(tmp_path):
    store = SkillStore(tmp_path)
    store.save_new_version("alpha", "x", SkillMeta.from_spec(_spec("alpha")))
    store.save_new_version("beta", "y", SkillMeta.from_spec(_spec("beta")))
    assert store.list_skills() == ["alpha", "beta"]
    lib = store.library()
    assert {m.name for m in lib} == {"alpha", "beta"}


def test_update_meta_records_tests(tmp_path):
    store = SkillStore(tmp_path)
    store.save_new_version("demo", "x", SkillMeta.from_spec(_spec("demo")))
    meta = store.load_meta("demo", 1)
    meta.test_results.append(
        TestResult(test_name="t", user_prompt="p", output="o", model="m", rating="up")
    )
    store.update_meta("demo", 1, meta)
    reloaded = store.load_meta("demo", 1)
    assert len(reloaded.test_results) == 1
    assert reloaded.test_results[0].rating == "up"


def test_overwrite_version(tmp_path):
    store = SkillStore(tmp_path)
    store.save_new_version("demo", "first", SkillMeta.from_spec(_spec("demo")))
    store.overwrite_version("demo", 1, "second", SkillMeta.from_spec(_spec("demo")))
    assert store.versions("demo") == [1]
    assert store.load_content("demo", 1) == "second"


def test_empty_store(tmp_path):
    store = SkillStore(tmp_path / "nonexistent")
    assert store.list_skills() == []
    assert store.latest_version("nope") is None
