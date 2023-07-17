# What is this?
These are binaries for various needs compiled to run on the K1.

They  are **not optimized** in any way as of yet, the goal for now is to have something dirty to work on.

*Note*, these are only the binaries, you need to setup configfiles or similar yourself obviously. If in doubt, read the official documentations.

# How where they made?
Cross compiling using [buildroot](https://buildroot.org/) and the .config provided above. They are statically linked against uclibc, not stripped, debug_info untouched. Compile yours differently if needed.

# How to do it yourself?
Grab a copy of buildroot, unpack it somewhere, place the .config in it, run `make menuconfig` and make changes as needed, run `make` and finally export the binaries.

# Why do it yourself?
You should not run untrusted code that has not been checked as it could be harmful at worst in this case physically destroying your machine.

# How to use?
Transfer the files to the K1 via USB or network, put them in places they are expected to be, make sure they are executable.

# Future additions?
I might add more over time, no promises though. This should be enough to get you started.
