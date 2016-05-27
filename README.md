
# MiniDLNA Indicator

This indicator allows you to launch an instance of [MiniDLNA](https://help.ubuntu.com/community/MiniDLNA)
as a normal user, without the need to edit configuration files as `root`, or restart by command the
application if you have changed the configuration.
 
Some of the features this indicator provides are:

* Detect if the process has died, using a background thread
* Auto generation of a port and uuid to avoid conflicts with the default configuration
  ([check this](https://spremi.wordpress.com/2014/06/30/minidlna-multiple-instances/) to know the problem about uuid)
* Auto configuration when first run (adding the pictures, music, videos and downloads folder
of the user, if the exist, and generating a random, non-default, port)

Tested on [Ubuntu 16.04 (Xenial Xerus)](http://www.ubuntu.com) and [Linux Mint 17.3 (Rosa)](https://www.linuxmint.com)
with Python 2.7; some changes needed to run with Python 3 (see TODO).

Tested from these devices (tests from more devices are welcome):
 
* [Samsung UE32F5500 TV](http://www.samsung.com/nl/consumer/tv-audio-video/televisions/led-tv/UE32F5500AWXXN)


## Instalation

No `deb` or `rpm` packages available; only from Github; if someone want to contribute, it will be welcome.

To download and run the application, execute this commands:

```
git clone https://github.com/okelet/minidlnaindicator
cd minidlnaindicator
python2 minidlnaindicator.py &
```

The application will create a launcher in the menu in its first run.


## Configuration

The configuration is very basic. It will detect an existing user configuration in the `~/.minidlna/minidlna.conf`
file, check it, and use it. If it doesn't exist, it will generate a new one with the user images, music, videos and 
downloads folder of the current user.

The default application configuration, will launch the MiniDLNA process when the indicator starts, and it will
be stopped when the indicator finishes. Also, the own indicator will configure itself to run on every user logon.
All these 3 settings can be changed from the indicator configuration menu.

The MiniDLNA configuration has to be done by hand, but there are some shotcuts to open the file and edit it. You can also
open from the menu the LOG. If you change the configuration, please remember to restart the MiniDLNA process.



## TODO

* Translators needed
* Update system (from GitHub?)
* Detect external MiniDLAN configuration changes
* Allow some basic MiniDLNA configuration (media folders, port)
* Detect errors when launching the process (MiniDLNA returns 0 even when it exits because other
  application is listening in the same port); note, possible solution: when running in foreground
  mode (`-S` parameter), MiniDLNA does return 255 in case of problems.
* Make it run with Python 2 and 3


## Credits

Icons from:

* http://www.easyicon.net/language.en/1090748-dlna_icon.html
* http://www.easyicon.net/language.en/1088952-dlna_icon.html
