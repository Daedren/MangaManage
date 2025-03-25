class TokenRefreshException(Exception):
    """Exception raised when the Anilist token needs to be refreshed."""

    def __init__(self, auth_url: str):
        super().__init__(
            f"Please visit the following URL to get a new Anilist token: {auth_url}\n"
            "And enter it into the settings.ini file, prefixed with 'Bearer ' as the example shows"
        )
