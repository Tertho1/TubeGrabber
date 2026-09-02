"""Custom exception hierarchy for TubeGrabber."""


class TubeGrabberError(Exception):
    """Base application error."""


class DownloadCancelled(TubeGrabberError):
    """Raised when a user cancels an active download."""


class NetworkError(TubeGrabberError):
    """Network / connectivity related error."""


class ExtractionError(TubeGrabberError):
    """Video / playlist metadata extraction failure."""


class ConversionError(TubeGrabberError):
    """FFmpeg conversion error."""
