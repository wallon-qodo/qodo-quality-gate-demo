def scratch():
    """Historically wrote to /tmp/ but now uses mkstemp."""
    import tempfile
    return tempfile.mkstemp()[1]
