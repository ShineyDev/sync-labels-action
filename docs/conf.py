import re


author = "ShineyDev"
project = "sync-labels-action"

copyright = f"2021-present, {author}"

_version_regex = r"^version = ('|\")((?:[0-9]+\.)*[0-9]+(?:\.?([a-z]+)(?:\.?[0-9])?)?)\1$"

with open("../script.py") as stream:
    match = re.search(_version_regex, stream.read(), re.MULTILINE)

release = "v" + match.group(2)
version = release

if match.group(3) is not None:
    try:
        import subprocess

        process = subprocess.Popen(["git", "rev-list", "--count", "HEAD"], stdout=subprocess.PIPE)
        out, _ = process.communicate()
        if out:
            release += out.decode("utf-8").strip()

        process = subprocess.Popen(["git", "rev-parse", "--short", "HEAD"], stdout=subprocess.PIPE)
        out, _ = process.communicate()
        if out:
            release += "+g" + out.decode("utf-8").strip()
    except (Exception) as e:
        pass


extensions = [
    "sphinx.ext.extlinks",
    "sphinx_rtd_theme",
]

extlinks = {
    "issue": (f"https://github.com/{author}/{project}/issues/%s", "#"),
}


highlight_language = "none"
pygments_style = "friendly"
root_doc = "index"
source_suffix = ".rst"


html_favicon = "favicon.svg"
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": False,
    "includehidden": False,
    "navigation_depth": -1,
    "prev_next_buttons_location": None,
    "titles_only": True,
}
html_title = f"{project} {version}"
