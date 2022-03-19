project('gytparse',
          version: '0.1.2',
    meson_version: '>= 0.59',
  default_options: [ 'warning_level=2',
                   ],
)

project_id = 'gr.oscillate.gytparse'
project_name = 'gytparse'

i18n = import('i18n')
prefix = get_option('prefix')
python = import('python')
gnome = import('gnome')
python_bin = python.find_installation('python3')
python_dir = python_bin.get_install_dir()
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
localedir = join_paths(prefix, get_option('localedir'))

if not python_bin.found()
  error('No python found')
endif

if not python_bin.language_version().version_compare('>=3.7')
  error('Need Python 3.7 or newer')
endif


dependency('gtk4', version: '>= 4.4.0')
dependency('libadwaita-1', version: '>= 0.90.0')

subdir('gytparse')
subdir('data')
subdir('po')

gnome.post_install(
  gtk_update_icon_cache: true,
  glib_compile_schemas: true,
  update_desktop_database: true,
)
