"""
WSGI entry point used by hosting platforms that expect a module-level
`application` object (e.g. PythonAnywhere's web app config).

On PythonAnywhere: in the "Web" tab, edit your WSGI configuration file so it
ends with:

    import sys
    path = '/home/YOURUSERNAME/fohow_app'
    if path not in sys.path:
        sys.path.append(path)
    from wsgi import application

(Point `path` at wherever you uploaded this project's folder.)
"""
from app import app as application
