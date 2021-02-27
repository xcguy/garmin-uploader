# -*- coding: utf-8 -*-
def test_authenticate(user):
    """
    Test Garmin API authentication
    with "real" user
    """
    assert user.authenticate()
    assert user.session is not None


def test_upload(user, sample_activity):
    """
    Test upload of a sample activity
    """
    # user is already authenticated by test above
    assert sample_activity.upload(user)
