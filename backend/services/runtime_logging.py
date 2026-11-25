"""Keep Windows console and frozen GUI logging safe for Unicode diagnostics."""
import os
import sys


def configure_text_streams():
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name)
        if stream is None:
            setattr(sys, name, open(os.devnull, 'w', encoding='utf-8', errors='backslashreplace'))
        elif hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
