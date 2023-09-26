# MultiCamera.py
This application is developed on windows 11 and hasn't been tested for linux. but it should be really easy to follow along for linux user who uses python on linux 
There is no certainty that this code will execute without problems. Since computers have different specs. 

## Packet Delay and Threading
The code will calculate its own packet delay based on the packet size and network speed written in config.py.
Once the code have have found all the cameras available and have a connection. It will call config.CalculatePacketDelay(...) with the amount of cameras connected and passed to the Source Class when Open is called.

To acquire images from the camera, we spawn a tread to handle each source. Since each thread aren't created at the same time, we utilize a barrier to sync the threads. When the last thread arrive, They will execute AcquisitionStart command, sending all cameras in capture mode.

## Pixel format
This code is made to handle color channels with 8 bit. The code will convert it into a 8 bit pixel format that OpenCv can read. 
This happens in MultiCamera.py at line 100
If you wanna work with larger channels you need to make a few corrections to the code.


## Installation
Since this project uses some of the packages from the python eBUS SDK, we'll just install it into a Venv to easily link to these files.
If its the first time running scripts in powershell you might need to change your ExecutionPolicy (needs admin privileges)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned
```


### Setup Env
First we create an env, then we activate it
```powershell
py -m venv env
env\Scripts\activate.ps1
```

### Install eBUS
Download the correct version of eBUS python from our website: https://www.jai.com/support-software/jai-software

Then install it in the terminal that you activated the venv
```powershell 
pip install .\ebus_python-<EBUS VERSION>-6343_jai-py<PYTHON VERSION>-none-win_amd64.whl
pip install -r requirements.txt
```

Verify that was install into venv by checking this path
MultiCameraDisplay\env\Lib\site-packages\ebus-python\samples\PvStreamSample.py


## Run the Code
Lastly run the code 
```powershell
python MultiCamera.py
```

