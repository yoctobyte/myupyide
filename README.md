## myupyide - A micropython IDE
An IDE to develop micropython on a microcontroller, with built in terminal and file sync, sharing the same serial connection.

## Pre-release
This version is anything but finished. It is a very rough gem. It is functional. It has dozens of quircks.
I figured i might as well track changes and bring it into the public, since, well, i am using it for a couple of month already for my uC project.

## Manual & instructions
To-do. For now, please figure it out, it is not complicated. All you need is attach a microcontroller that has micropython flashed to it to your PC, launch the editor, and point to a working folder. The buttons and menu should be self-explanatory.

## Install
Install a recenty version of Python for your platform. (At the time of writing, this project was made and tested using Python 3.10)

Install needed libraries. This project mostly uses the standard libraries but i may have overlooked some.
```
pip install serial
pip install <any library i forgot to mention>
```

Run the editor main file:
```
python mypyide.py
```

## To-do
Pick a better name

## Remarks on the release
I used visual studio code for this project, but i did not include visual studio's files to the repository.

## Background
This project was born out of necessity. I was working on an arduino BLE. Decided that, for my codebase and development progress, it would be better to port it to micropython.
However, the arduino-provided IDE for micropython, 'arduino lab', was simply not working. At least not properly. I took a look at openMV's editor. Which is the officially supported one (by arduino). But had issues as well.
So, long story short, i ended up writing an IDE to use for micropython.
Assumptions are: i want my files local (on PC), yet easy to sync to the uC. I need access to the REPL. The serial port should be shared by both the REPL terminal as the various IO (file upload) functions.
So, with the help of AI, i crafted a quick and dirty editor. It allows opening a bunch of python files in a folder. Can sync files to the uC with a push of the button. Can test functionality in the terminal. And thus have a very low turn-around time between making code changes and testing.
Once i had the editor, i lived with it quircks since i have another project to finish (the project that initiated writing this editor in the first place).
It's been sitting on my dekstop for some months now. There is a lot to improve. But i figured i might as well release it, even if i consider it 'unfinished' because, well, it is of great use to me, so maybe to someone else as well.
As a proof of 'right approach' or 'just works': I changed my uC hardware to an ESP32, which is slightly inferior hardware but not such m&nt&l f&&k&p as the arduino BLE. And didn't touch the editor at all, i ported my micropython files and went on where i was.
So, this just as background info note for the initial release. Surely i will word it nicer in the future. But i thought would be nice to mention where i came from.

## Disclaimer
This project was crafted with the aid of AI to hasten development.

## License
GPL