pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'gytparse.in',
  output: 'gytparse',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

gytparse_sources = [
  '__init__.py',
  'main.py',
  'operation.py',
  'youtube.py',
  'settings.py'
]

install_subdir(
  meson.current_source_dir(),
  exclude_directories: ['__pycache__'],
  exclude_files: ['gytparse.in',
    'meson.build',
    'gr.oscillate.gytparse.gschema.xml'],
  install_dir: python_dir
)

settings_schemas = [ 'gr.oscillate.' + meson.project_name() + '.gschema.xml' ]
install_data(settings_schemas, install_dir: schemas_dir)
