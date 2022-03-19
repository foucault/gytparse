appdir = join_paths(get_option('prefix'), get_option('datadir'), 'applications')
metainfodir = join_paths(get_option('prefix'), get_option('datadir'), 'metainfo')
schemas_dir = join_paths(get_option('prefix'), get_option('datadir'), 'glib-2.0', 'schemas')

# settings
settings_schemas = [ 'gr.oscillate.' + meson.project_name() + '.gschema.xml' ]
install_data(settings_schemas, install_dir: schemas_dir)

# resources
gnome.compile_resources('gr.oscillate.gytparse',
  'gr.oscillate.gytparse.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

# app icon
install_data('gr.oscillate.gytparse.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'))

# desktop file
i18n.merge_file(
  input: 'gr.oscillate.gytparse.desktop.in',
  output: 'gr.oscillate.gytparse.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: appdir
)

# appstream file
i18n.merge_file(
  input: 'gr.oscillate.gytparse.metainfo.xml.in',
  output: 'gr.oscillate.gytparse.metainfo.xml',
  type: 'xml',
  po_dir: '../po',
  install: true,
  install_dir: metainfodir
)
