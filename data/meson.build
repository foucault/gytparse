pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
appdir = join_paths(get_option('prefix'), get_option('datadir'), 'applications')

gnome.compile_resources('gytparse',
  'gytparse.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

install_data('gr.oscillate.gytparse.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'))

install_data('gr.oscillate.gytparse.desktop', install_dir: appdir)
