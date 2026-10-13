# UNAM Website

The website runs on Python 3.10 or newer and the Python standard library; PHP
and third-party packages are not required.

## Run locally

From this directory, start the web server with:

```powershell
python app.py
```

Then open <http://127.0.0.1:8000/>. To use a different address or port, pass
`--host` and `--port`, or set the `HOST` and `PORT` environment variables.

The application also exports a WSGI callable named `application` in `app.py`,
which can be served by a Python-capable web host. The existing `bilder` folder
structure is read at request time, so adding an article or gallery folder does
not require rebuilding the site. Article folders use `artikel.txt` (title on
the first line, optional body after it) and may contain one supported image.

The former `.php` page URLs redirect to the corresponding Python route.

Before going live, update the legal defaults in `LEGAL_DEFAULTS` at the top of
`app.py` with the actual association name, contact details, and hosting
provider. The generated pages use those values for the imprint and privacy
notice.
