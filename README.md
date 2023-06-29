# Creality K1 firmwares

# WARNING
As of June 29 2023 the firmware update 1.2.9.21 is out and people report losing access to their machines after updating!  
Do not update if you are not ok with possibly losing functionality! [Related thread on Reddit](https://www.reddit.com/r/crealityk1/comments/14m4fff/warning_firmware_12921_removes_root_and_fluidd/).

## Description
This repository keeps track of firmware releases made by *Creality* for their *K1* 3D printer series.

## License

*It's complicated.*

Sadly Creality does not respect the copyrights and licenses of open source projects and their contributors -among many others examples in this firmware include *klipper*, *mainsail*, *fluidd*, *moonraker*, *yolov5*.

I'm sure Creality is fine with their code and property being held to the same standard.

## Modifications

Aside from creating this README.md, no other changes have been made by me to any file in this repository. However Creality shipped some *.git* repository folders which have been stripped.

## Contents

The folder *_sources* contains original firmware packages (sadly Creality does not provide checksums), installers for the Slicer, list of currently known passwords and a copy of the original exploit files.

The other folders represent the contents of the root filesystem as extracted from the firmware images.  
If you would like to do this yourself, unpack a firmware.img file using `7z x -pPASSWORD firmware.img`, go into the resulting directory and `cat root* > rootfs.sqfs` and finally mount it `sudo mount -o loop rootfs.sqfs somewhere/`.

## Missing files

Creality deleted older revisions of their Slicer from their downloads page, if any are missing and you can provide it, upload it somewhere and send a link to it.

## Support

If you'd like to support me for doing this work, some coffee money is always welcome. Thank you :)  
https://ko-fi.com/a_v_x

## Thanks & Attribution

* [*k3d*](https://www.youtube.com/@SorkinDmitry) & friends - for making available the initial exploit to gain root access
* [*/u/destinal*](https://www.reddit.com/u/destinal/) - finding and providing the [password for logfiles](https://www.reddit.com/r/crealityk1/comments/14diw4i/password_for_logfiles/jovqrag/)
