conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', localedir)
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'gytparse.in',
  output: 'gytparse',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

install_subdir(
  meson.current_source_dir(),
  exclude_directories: ['__pycache__'],
  exclude_files: ['gytparse.in',
    'meson.build'],
  install_dir: python_dir
)
