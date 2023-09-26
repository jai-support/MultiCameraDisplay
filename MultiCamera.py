#!/usr/bin/env python3

"""
 *****************************************************************************

     Copyright (c) 2022, Pleora Technologies Inc., All rights reserved.

 *****************************************************************************

 This sample shows how to receive images from a multi-source device using PvPipeline.
"""

# from concurrent.futures import thread

import time
import eBUS as eb
import PvSampleUtils as psu
import cv2
import re
from threading import Barrier, Thread

import config


class Source:
    """Class to work with the image sensors (sources) on the camera
    Returns:
        Object: use it to manage a source
    """

    _BUFFER_COUNT = 16

    _device = None
    _stream = None
    _pipeline = None
    _connection_id = None
    _source = None
    _thread = None
    _packet_delay = None
    _pixel_format = None
    _channel_size = None

    def __init__(self, device, connection_id, source, packet_delay):
        """Class to stream from source on device to a OpenCV frame

        Args:
            device (PvDevice):
                Reference to the device, to change parameter and such
            connection_id (str):
                With multiple cameras connected. connection_id is used to open the
                source of a camera
            source (int):
                Used to select the right source on a device with multiple sources
            packet_delay (int):
                packet delay to adjust for multiple cameras on the same switch
        """
        self._running = False
        self._device = device
        self._connection_id = connection_id
        self._source = source
        self._thread = None
        self._packet_delay = packet_delay

    def Open(self):
        """Opens a stream to a source

        Returns:
            boolean: Whether is was successful or not
        """
        # Select this source
        stack = eb.PvGenStateStack(self._device.GetParameters())
        self.SelectSource(stack)

        # Explicitly check for GEV or U3V types, required to configure channels
        if isinstance(self._device, eb.PvDeviceGEV):
            self._stream = eb.PvStreamGEV()
            if self._stream.Open(self._connection_id, 0, 0).IsFailure():
                print("\tError opening ", str(self._source), " to GigE Vision device")
                return False

            local_ip = self._stream.GetLocalIPAddress()
            local_port = self._stream.GetLocalPort()

            print(
                "\tSetting source destination on device (channel",
                0,
                ") to",
                local_ip,
                "port",
                local_port,
            )
            self._device.SetStreamDestination(local_ip, local_port, 0)
        elif isinstance(self._device, eb.PvDeviceU3V):
            self._stream = eb.PvStreamU3V
            if self._stream.Open(self._connection_id, 0).IsFailure():
                print("\tError opening stream to USB3 Vision Device")
                return False

        ####################################################################################
        #### START OF CUSTOM SETTINGS HERE.
        #### THESE SETTINGS ARE APPLIED TO ALL CONNECTED CAMERAS

        # Set Packet Delay
        self._device.GetParameters().SetIntegerValue("GevSCPD", 144224)
        print("\tPacket Delay:", "144224")

        # Set Pixel format to 8 bits
        result, pixel_format = self._device.GetParameters().GetEnumValueString(
            "PixelFormat"
        )
        print("\tPixel Format:", pixel_format)

        self._pixel_format = re.search(r"\D+", pixel_format).group()
        self._channel_size = pixel_format[len(self._pixel_format) : len(pixel_format)]

        if int(self._channel_size) > 8:
            self._device.GetParameters().SetEnumValue(
                "PixelFormat", self._pixel_format + "8"
            )
            self._channel_size = "8"

        #### END OF CUSTOM SETTINGS HERE
        ####################################################################################

        payload_size = self._device.GetPayloadSize()

        self._pipeline = eb.PvPipeline(self._stream)
        self._pipeline.SetBufferSize(payload_size)
        self._pipeline.SetBufferCount(self._BUFFER_COUNT)
        print("\tStarting pipeline thread")
        self._pipeline.Start()
        return True

    def Close(self):
        """close the stream to a source"""
        print("Closing source ", self._source)

        # Stopping pipeline thread
        self._pipeline.Stop()

        # Closing stream
        self._stream.Close()

    def StartAcquisition(self):
        """Starts acquisition of a source"""
        print("Start acquisition", self._source)
        stack = eb.PvGenStateStack(self._device.GetParameters())
        self.SelectSource(stack)
        self._running = True

        self._device.StreamEnable()

    def StopAcquisition(self):
        """Stops acquisition of a source"""
        print("Stop acquisition ", self._source)
        stack = eb.PvGenStateStack(self._device.GetParameters())
        self.SelectSource(stack)
        self._running = False

        # Sending AcquisitionStop command to device
        self._device.GetParameters().Get("AcquisitionStop").Execute()

        self._device.StreamDisable()

    def run(self, software_trigger):
        """Thread running Acquisition on from a device source"""

        ## Wait for all threads before starting
        software_trigger.wait()

        # Sending AcquisitionStart command to device
        self._device.GetParameters().Get("AcquisitionStart").Execute()

        while self._running:
            result, buffer, operational_result = self._pipeline.RetrieveNextBuffer(1000)
            if not result.IsFailure():
                image = buffer.GetImage()
                image_data = image.GetDataPointer()

                # print(image.GetPixelType())
                if int(self._channel_size) != 8:
                    print("conversion need to display on source", self._source)
                else:
                    if image.GetPixelType() == eb.PvPixelBayerBG8:
                        image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerBG2RGB)
                    elif image.GetPixelType() == eb.PvPixelBayerGB8:
                        image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerGB2RGB)
                    elif image.GetPixelType() == eb.PvPixelBayerGR8:
                        image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerGR2RGB)
                    elif image.GetPixelType() == eb.PvPixelBayerRG8:
                        image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerRG2RGB)
                    elif image.GetPixelType() == eb.PvPixelRGB8:
                        image_data = cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR)
                    # elif image.GetPixelType() == eb.PvPixelMono8:
                    # do nothin

                # Resize image
                if image_data.size != 0:
                    image_data = cv2.resize(
                        image_data, (800, 600), interpolation=cv2.INTER_LINEAR
                    )  # Display image
                    cv2.imshow(str(self._source), image_data)
                    cv2.waitKey(1)

                self._pipeline.ReleaseBuffer(buffer)

    def SelectSource(self, stack):
        """changes the selected source.
        This needs to run before any source interfacing. EX.
        Before we can send AcquisitionStop to a source, we need to tell the camera,
        we want to make changes to this source otherwise we can end up making changes
        to a difference source

        Args:
            stack (PvGenStateStack):
            Performs changes to a GenICam node map, tracks them and restores the
            previous state on destruction.
        """
        if self._source:
            stack.SetEnumValue("SourceSelector", self._source)


def AcquireImages():
    """Main function to start acquiring images

    Returns:
        boolean: Successful or not
    """

    print("\nDetecting devices.")
    lSystem = eb.PvSystem()
    lSystem.Find()

    # Detect, select device.
    lDIVector = []
    deviceVector = []
    for i in range(lSystem.GetInterfaceCount()):
        lInterface = lSystem.GetInterface(i)
        for j in range(lInterface.GetDeviceCount()):
            lDI = lInterface.GetDeviceInfo(j)
            result, device = eb.PvDevice.CreateAndConnect(lDI)
            if result.IsFailure():
                print("Unable to connect to device.")
            else:
                if not isinstance(device, eb.PvDeviceGEV):
                    print(
                        "The selected device is not currently supported by this sample."
                    )
                else:
                    lDIVector.append(lDI)
                    deviceVector.append(device)
                    print(f"added [{len(lDIVector) - 1}]\t{lDI.GetDisplayID()}")

    if len(lDIVector) == 0:
        print("No devices found, terminating Code")
        return False

    packetDelay = config.CalculatePacketDelay(len(lDIVector))

    print("Successfully connected to devices")
    sources = []
    for i in range(len(lDIVector)):
        source = Source(deviceVector[i], lDIVector[i], i, packetDelay)
        if source.Open():
            sources.append(source)

    software_trigger = Barrier(len(lDIVector))

    print("\nstaring Acquisition")
    for source in sources:
        source.StartAcquisition()
        source._thread = Thread(target=source.run, args=[software_trigger])
        source._thread.start()

    print("\n<press a key to stop streaming>")
    kb = psu.PvKb()
    kb.start()
    while not kb.is_stopping():
        if kb.kbhit():
            kb.getch()
            break

    print("Stopping Threads and ending application")
    for source in sources:
        source.StopAcquisition()
        source._thread.join()
        source.Close()

    return True


print("MultiSource sample")
print("Acquire images from a GigE Vision device")
AcquireImages()
