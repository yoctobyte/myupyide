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
pip install wx serial pygments pyserial pyboard
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
This project was born out of necessity. While working on an Arduino BLE, I decided to transition to MicroPython. However, the available tools presented challenges. The Arduino-provided IDE for MicroPython, 'Arduino Lab', was not functioning as expected. I also tried OpenMV's editor, the officially supported one by Arduino, but faced issues there too.
In response, I created this IDE tailored for MicroPython. The primary goals were to keep files locally on the PC, ensure easy synchronization with the microcontroller, and provide access to the REPL. The serial port needed to be shared between the REPL terminal and various IO functions. With AI's assistance, I developed an editor that allows opening multiple Python files, synchronizing them to the microcontroller, and testing functionalities within the terminal. This streamlined the development process, reducing the time between code changes and testing.
Having used this editor for several months, I recognized its quirks but also its value. When I transitioned my hardware to an ESP32, the editor remained consistent, requiring no changes. I've decided to release it in its current state, believing it could be beneficial to others. This background serves as a testament to the project's journey and its adaptability.

## Disclaimer
This project was crafted with the aid of AI to hasten development.

## License
GPL