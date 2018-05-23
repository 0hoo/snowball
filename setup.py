from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
buildOptions = dict(packages = [
    'idna',
    'jinja2.ext',
    ], excludes = [])

base = 'Console'

executables = [
    Executable('app.py', base=base),
    Executable('script.py', base=base),
]

setup(name='snowball',
      version = '1.0',
      description = '',
      options = dict(build_exe = buildOptions),
      executables = executables)
