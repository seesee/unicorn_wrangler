Pimoroni UnicornHD compatibility wrapper 
========================================

This part is NOT NEEDED if you are running the Unicorn Wrangler
on a pico-based Stellar/Galactic/Cosmic Unicorn.

Prior to these pico-based units, pimoroni released a version
called the UnicornHD which is/was a 16x16 led matrix, very
similar to the stellar unicorn, that plugs into the GPIO header
of a Raspberry Pi.

This is a little wrapper that makes the micropython code function
under regular python, and make the UnicornHD look like a stellar
unicorn.

You can completely ignore all this if you don't have a UnicornHD.
In fact I'm not even sure it'll install the right dependencies
since it's been ages since I downloaded the libraries from the
pimoroni website.

So you might need to install them from there if you run into
issues.

Finally, you will need to run the install.sh script. This will
symlink the code from the board_client (unicorn wrangler client)
into the right places, and try to install/check dependencies.



