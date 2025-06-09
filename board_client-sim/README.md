Pimoroni Unicorn Simulator for Mac/Linux/Windows 
================================================

This part is NOT NEEDED if you are running the Unicorn Wrangler
on a pico-based Stellar/Galactic/Cosmic Unicorn.

This is a little wrapper that makes the micropython code function
under regular python, mostly to aid debugging and creation of
new animations (please be aware that it's not 100% compatible,
fonts don't work currently). Also, code will run a lot slower on
a real device, and you won't have as much memory to play with
so don't get carried away.

You can completely ignore this if you don't want to run a 
simulated Unicorn device.

Finally, you will need to run the install.sh script. This will
symlink the code from the board_client (unicorn wrangler client)
into the right places, and try to install/check dependencies.
