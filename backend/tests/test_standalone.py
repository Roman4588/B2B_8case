def test_storage_password_is_stable_and_existing_data_is_untouched(tmp_path):
    from app.standalone import prepare_storage

    original = tmp_path / "app.db"
    original.write_bytes(b"existing database must not be replaced")
    first = prepare_storage(tmp_path)
    second = prepare_storage(tmp_path)
    assert first == second
    assert len(first) >= 32
    assert original.read_bytes() == b"existing database must not be replaced"
    assert (tmp_path / "postgres").is_dir()
    assert (tmp_path / "redis").is_dir()


def test_empty_existing_password_is_an_error_not_silent_rotation(tmp_path):
    import pytest
    from app.standalone import prepare_storage

    (tmp_path / ".postgres-password").write_text("")
    with pytest.raises(ValueError):
        prepare_storage(tmp_path)
    assert (tmp_path / ".postgres-password").read_text() == ""
