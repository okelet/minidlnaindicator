
from setuptools import setup

import minidlnaindicator

setup(
    name='minidlnaindicator',
    version=minidlnaindicator.__version__,
    description='MiniDLNA Indicator',
    classifiers=[
        # https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications',
        'Environment :: X11 Applications :: Gnome',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'Natural Language :: Spanish',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Topic :: Communications :: File Sharing',
        'Topic :: Desktop Environment :: Gnome',
        'Topic :: Multimedia :: Graphics',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Video',
        'Topic :: Utilities',
    ],
    url='http://github.com/okelet/minidlnaindicator',
    author='Juan A. S.',
    author_email='okelet@gmail.com',
    packages=[
        'minidlnaindicator',
        'minidlnaindicator.ui',
        'minidlnaindicator.exceptions',
    ],
    package_data={
        "minidlnaindicator": [
            "icons/*.png",
            "locale/*/LC_MESSAGES/*.po",
            "locale/*/LC_MESSAGES/*.mo"
        ],
    },
    setup_requires=['setuptools-markdown'],
    long_description_markdown_filename='README.md',
    install_requires=[
        "distro",
        "psutil",
        "requests",
    ],
    entry_points = {
        'gui_scripts': [
            'minidlnaindicator = minidlnaindicator.runner:indicator'
        ],
    },
    data_files = [
        ("share/icons", ["minidlnaindicator.png"]),
        ("share/applications", ["minidlnaindicator.desktop"])
    ],
    zip_safe=False,
)
