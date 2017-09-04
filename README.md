
# MiniDLNA Indicator

[![Code Health](https://landscape.io/github/okelet/minidlnaindicator/master/landscape.svg?style=flat)](https://landscape.io/github/okelet/minidlnaindicator/master)

This indicator allows you to launch an instance of [MiniDLNA](https://help.ubuntu.com/community/MiniDLNA)
as a normal user, without the need to edit configuration files as `root`, or restart by command the
application if you have changed the configuration.
 
Some of the features this indicator provides are:

* Detect if the process has died, using a background thread
* Auto generation of a port and uuid to avoid conflicts with the default configuration
  ([check this](https://spremi.wordpress.com/2014/06/30/minidlna-multiple-instances/) to know the problem about uuid)
* Auto configuration when first run (adding the pictures, music, videos and downloads folder
of the user, if the exist, and generating a random, non-default, port)

Tested operating systems:

- [Ubuntu 16.04 (Xenial Xerus)](http://www.ubuntu.com)
- [Linux Mint 17.3 (Rosa)](https://www.linuxmint.com)
- [Fedora 26](https://getfedora.org) (with the [KStatusNotifierItem/AppIndicator Support](https://extensions.gnome.org/extension/615/appindicator-support/) Gnome Shell extension)

It should work with any operating system that supports Python 3.5+, AppIndicator and the required dependencies. If you have problems,
please, open an issue.


Tested from these devices (tests from more devices are welcome):
 
* [Samsung UE32F5500 TV](http://www.samsung.com/nl/consumer/tv-audio-video/televisions/led-tv/UE32F5500AWXXN)
* [Android BubbleUPnP](https://play.google.com/store/apps/details?id=com.bubblesoft.android.bubbleupnp)


## What is MiniDLNA?

In brief, MiniDLNA is a small program that allows you to share multimedia content (audio, video, pictures, etc.) easily with
[DLNA](https://en.wikipedia.org/wiki/Digital_Living_Network_Alliance)/[UPnP](https://en.wikipedia.org/wiki/Universal_Plug_and_Play)
compatible devices (for example, smart TVs, phones, XBMC, etc.). This also could be done with some type of share services,
like Windows/Samba/CIFS, NFS, etc. but DLNA is easier to configure (you just need to run the program and select the folders 
you want to share); it is faster, no need to configure security. 


## Requirements

You will need this software to run the indicator, considering a standard initial installation of Ubuntu/Mint:

```bash
sudo apt install minidlna python3-setuptools python3-pip python3-gi python3-yaml python3-psutil
```

For Fedora, you will need [RPM Fusion](https://rpmfusion.org/) repository:

```bash
sudo dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
```

And then install these dependencies:

```bash
sudo dnf install minidlna python3-setuptools python3-pip python3-gobject python3-yaml python3-psutil libappindicator-gtk3
```

Also remember to install the [KStatusNotifierItem/AppIndicator Support](https://extensions.gnome.org/extension/615/appindicator-support/) Gnome Shell extension
from the web or using these commands:

```bash
sudo dnf install chrome-gnome-shell gnome-tweak-tool jq
curl -s https://raw.githubusercontent.com/okelet/minidlnaindicator/master/gnome-ext-install.md | bash -s -- install appindicatorsupport@rgcjonas.gmail.com
```


## Instalation

No `deb` or `rpm` packages available; only from Github; if someone wants to contribute, it will be welcome.

Although the application is ready to publish it on PyPi, and perhaps, it would be easy to create a `deb` or `rpm`, 
installation, must be done using `pip` with this repository:

```
python3 -m pip install --user git+https://github.com/okelet/minidlnaindicator.git
```

`pip` will create a shortcut in the applications menu.


## Configuration

The configuration is very basic. It will detect an existing user configuration in the `~/.minidlna/minidlna.conf`
file, check it, and use it. If it doesn't exist, it will generate a new one with the user images, music, videos and 
downloads folder of the current user.

The default application configuration, will launch the MiniDLNA process when the indicator starts, and it will
be stopped when the indicator finishes. Also, the own indicator will configure itself to run on every user logon.
All these 3 settings can be changed from the indicator configuration menu.

The MiniDLNA configuration has to be done by hand, but there are some shortcuts to open the file and edit it. You can also
open from the menu the LOG. If you change the configuration, please remember to restart the MiniDLNA process.


## How it looks

Entry in the applications menu (Ubuntu 16.04):

![Applications menu](https://raw.githubusercontent.com/okelet/minidlnaindicator/master/apps_menu.png)

Indicator menu:

![Indicator menu](https://raw.githubusercontent.com/okelet/minidlnaindicator/master/screenshot_english.png)

Indicator menu (in spanish):

![Indicator menu](https://raw.githubusercontent.com/okelet/minidlnaindicator/master/screenshot_spanish.png)


# License

I don't know. This is a very small program done for myself and published just to help other people with the same problems. 

In brief, this is my idea. You can use the program freely; you don't have to pay me or somebody anything.
You can modify it, and redistribute it, as long as you keep this "license", attach the base source code,
and mention the original author (me).

Anyway, I wish (but this is not mandatory, as long as you accomplish the previous sentence) there weren't lots of forks spread over Internet,
so, I would prefer if you have fixes or new features, do a pull request; this is something just to have the code centralized
and ordered; I hate when I search a program or library and there are lots of forks, each one with different fixes or features.

Additionaly, as I do, you can't sell this program or get any economic benefit of it.

If you like the program, you can send a bottle of good wine (I don't like beer 😊).

Fixes or suggestions about this "license" are welcome.


## TODO

* Translators needed
* Update system (from GitHub?)
* Detect external MiniDLNA configuration changes
* Allow some basic MiniDLNA configuration (media folders, port)


## Type checking

Validated with MyPy:

```
mypy --python-version 3.5 --ignore-missing-imports --strict . 
```


## Me

Website (in spanish): https://okelet.github.io

Email: okelet@gmail.com


## Credits

Icons from:

* http://www.easyicon.net/language.en/1090748-dlna_icon.html
* http://www.easyicon.net/language.en/1088952-dlna_icon.html
