
from setuptools import setup


setup(
    name='minidlnaindicator',
    version='0.1',
    description='MiniDLNA Indicator',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: X11 Applications',
        'Environment :: X11 Applications :: Gnome',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'Natural Language :: English',
        'Natural Language :: Spanish',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.5',
        'Topic :: Desktop Environment :: Gnome',
        'Topic :: Internet',
        'Topic :: Utilities',
    ],
    url='http://github.com/okelet/minidlnaindicator',
    author='Juan A. S.',
    author_email='okelet@gmail.com',
    # license='MIT',
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
        # "yaml",
        "psutil"
    ],
    entry_points = {
        'gui_scripts': [
            'minidlnaindicator = minidlnaindicator.indicator:main'
        ],
    },
    data_files = [
        ("share/icons", ["minidlnaindicator.png"]),
        ("share/applications", ["minidlnaindicator.desktop"])
    ],
    zip_safe=False,
)
