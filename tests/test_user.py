def test_authenticate(user):
    """
    Test Garmin API authentication
    with "real" user
    """
    assert user.authenticate()
    assert user.session is not None
