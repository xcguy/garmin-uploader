import pytest

@pytest.fixture(scope='session')
def api():
    """
    Garmin API Instance
    """
    from garmin_uploader.api import GarminAPI
    return GarminAPI()

@pytest.fixture(scope='session')
def empty_activities(tmpdir_factory):
    """
    Build empty activities file
    Used to test cli listing functions
    """
    workdir = tmpdir_factory.mktemp('activities')

    # Build csv
    csv = workdir.join('a.csv')

    # Build a fit file

    # Build a tcx file

    # Build an invalid file

    return workdir
