"""APT repository package identifiers, not shell commands or local paths."""
import re

PACKAGE=re.compile(r'[a-z0-9][a-z0-9+.-]+(?::[a-z0-9][a-z0-9-]*)?\Z',re.ASCII)
def valid_package(value):
    return isinstance(value,str) and 2<=len(value)<=200 and PACKAGE.fullmatch(value) is not None

def version_for(package,versions):
    # APT may omit the native architecture suffix in its simulation output.
    exact=[item.split('=',1)[1] for item in versions if item.split('=',1)[0]==package]
    if exact:return exact[0]
    native=[item.split('=',1)[1] for item in versions if item.split('=',1)[0]==package.split(':',1)[0]]
    if native:return native[0]
    raise ValueError('Missing requested package')
