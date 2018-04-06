import uuid


def test_types(api):
    """
    Test activity types listing
    Non authenticated
    """
    types = api.load_activity_types()
    assert isinstance(types, dict)
    assert len(types) > 0
    assert 'all' in types
    assert 'running' in types
    assert 'track_cycling' in types


def test_rename(api, user, sample_activity):
    """
    Test renaming of a sample activity
    """
    assert user.authenticate()

    # Need to upload to get activity id
    sample_activity.id, _ = api.upload_activity(user.session, sample_activity)

    # Call rename api
    sample_activity.name = 'Test rename {}'.format(str(uuid.uuid4()))
    api.set_activity_name(user.session, sample_activity)

    # Cleanup
    sample_activity.id = None
