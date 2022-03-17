pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
appdir = join_paths(get_option('prefix'), get_option('datadir'), 'applications')
metainfodir = join_paths(get_option('prefix'), get_option('datadir'), 'metainfo')

gnome.compile_resources('gr.oscillate.gytparse',
  'gr.oscillate.gytparse.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

install_data('gr.oscillate.gytparse.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'))

install_data('gr.oscillate.gytparse.desktop', install_dir: appdir)
install_data('gr.oscillate.gytparse.metainfo.xml', install_dir: metainfodir)
