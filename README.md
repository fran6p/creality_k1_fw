# Creality K1 firmwares

## Description
This repository keeps track of firmware releases made by *Creality* for their *K1* 3D printer series.

## License

*It's complicated.*

Sadly Creality does not respect the copyrights and licenses of open source projects and their contributors -among many others examples in this firmware include *klipper*, *mainsail*, *fluidd*, *moonraker*, *yolov5*.

I'm sure Creality is fine with their code and property being held to the same standard.

## Modifications

Aside from creating this README.md, no other changes have been made by me to any file in this repository.

## Contents

The folder *_sources* contains original firmware packages (sadly Creality does not provide checksums), installers for the Slicer, list of currently known passwords and a copy of the original exploit files.

The other folders represent the contents of the root filesystem as extracted from the firmware images.  
If you would like to do this yourself, unpack a firmware.img file using `7z x -pPASSWORD firmware.img`, go into the resulting directory and `cat root* > rootfs.sqfs` and finally mount it `sudo mount -o loop rootfs.sqfs somewhere/`.

## Thanks & Attribution

* [*k3d*](https://www.youtube.com/@SorkinDmitry) & friends - for making available the initial exploit to gain root access
* [*/u/destinal*](https://www.reddit.com/u/destinal/) - finding and providing the [password for logfiles](https://www.reddit.com/r/crealityk1/comments/14diw4i/password_for_logfiles/jovqrag/)
