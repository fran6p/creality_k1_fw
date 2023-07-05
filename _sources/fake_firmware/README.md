# Create a fake firmware image

As of writing (July 5th 2023), it's possible to create a fake firmware image with a lower number posing as a higher, thus allowing firmware version .21 to be downgraded.

# Dependencies
It's provided as a shellscript which should work on pretty much any standard installation of GNU+Linux and likely, but untested, also on Mac OSX and *BSD.

~~I have no access to MS Windows, but I'm willing to add a version for it here if someone provides it. Meanwhile, I heard good things about WSL (Windows Subsystem for Linux), so that might work.~~

MS Windows version for PowerShell kindly provided by [/u/KorayA](https://reddit.com/u/KorayA) originally in [this post](https://www.reddit.com/r/crealityk1/comments/14r4ezx/script_to_generate_fake_firmware_to_downgrade/jqqpo20/).

Needed to get this to work on GNU+Linux/*nix are

`bin/sh`, `sed`, `7z`

For MS Windows `7z` needs to be in your *PATH*.

# Usage

GNU+Linux/*nix:

* Make this script executable by running `chmod +x fakefirmwarek1.sh`
* put the script together with the firmware.img you want to downgrade to
* adjust *FW_IN* and *FW_OUT* to your needs
* run the script

MS Windows:  

* put script and firmware package into same folder
* make sure `7z` is in your *PATH*
* execute script

If all works well you should find an update package in the same folder as well as the unpacked contents to check

# Note
I'm just an internet stranger, as such please don't execute code you don't understand. As such, I'm providing no binaries, the process takes 2 minutes and your safety should be worth that time!

If you'd like to help and say thanks, there is a donation link on the main page. Thank you :)