#!/usr/bin/env python3

"""
 *****************************************************************************

     Copyright (c) 2022, Pleora Technologies Inc., All rights reserved.

 *****************************************************************************

 This sample shows how to receive images from a multiple cameras

 Don't use this code in production, it's Proof of Concept
"""

# from concurrent.futures import thread
import eBUS as eb
import PvSampleUtils as psu
import cv2
import re
from threading import Barrier, Thread

import utils


class Camera:
    """Class to work with the image sensors (sources) on the camera
    Returns:
        Object: use it to manage a source
    """

    _BUFFER_COUNT = 16

    _device = None
    _stream = None
    _pipeline = None
    _connection_id = None
    _thread = None
    _packet_delay = None
    _pixel_format = None
    _channel_size = None

    def __init__(self, device, connection_id, packet_delay):
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
        self._thread = None
        self._packet_delay = packet_delay

    def Open(self):
        """Opens a stream to a source

        Returns:
            boolean: Whether is was successful or not
        """
        # Select this source
        # stack = eb.PvGenStateStack(self._device.GetParameters())
        # self.SelectSource(stack)

        # Explicitly check for GEV or U3V types, required to configure channels
        #!TODO support U3V
        # if isinstance(self._device, eb.PvDeviceGEV):
        self._stream = eb.PvStreamGEV()
        result = self._stream.Open(self._connection_id, 0, 0)
        if result.IsFailure():
            print(
                "\t\tError opening ",
                str(self._connection_id.GetDisplayID()),
                "\n\t\tError: ",
                result.GetDescription(),
                ".",
                sep="",
            )
            return False

        local_ip = self._stream.GetLocalIPAddress()
        local_port = self._stream.GetLocalPort()

        print(
            "\t\tSetting Camera on ",
            local_ip,
            " to port ",
            local_port,
            ".",
            sep="",
        )
        self._device.SetStreamDestination(local_ip, local_port, 0)
        # elif isinstance(self._device, eb.PvDeviceU3V):
        #     self._stream = eb.PvStreamU3V
        #     if self._stream.Open(self._connection_id, 0).IsFailure():
        #         print("\tError opening stream to USB3 Vision Device")
        #         return False

        ####################################################################################
        #### START OF CUSTOM SETTINGS HERE.
        #### THESE SETTINGS ARE APPLIED TO ALL CONNECTED CAMERAS

        # Set Packet Delay
        self._device.GetParameters().SetIntegerValue("GevSCPD", self._packet_delay)
        print("\t\tPacket Delay: ", self._packet_delay, ".", sep="")

        # Set Pixel format to 8 bits
        result, pixel_format = self._device.GetParameters().GetEnumValueString(
            "PixelFormat"
        )
        print("\t\tPixel Format: ", pixel_format, ".", sep="")

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
        print("\t\tStarting pipeline thread.")
        self._pipeline.Start()
        return True

    def Close(self):
        """close the stream to a source"""
        print("Closing source ", self._connection_id.GetDisplayID(), ".", sep="")

        # Stopping pipeline thread
        self._pipeline.Stop()

        # Closing stream
        self._stream.Close()

    def StartAcquisition(self):
        """Starts acquisition of a source"""
        print("Start acquisition ", self._connection_id.GetDisplayID(), ".", sep="")
        self._running = True

        self._device.StreamEnable()

    def StopAcquisition(self):
        """Stops acquisition of a source"""
        print("Stop acquisition ", self._connection_id.GetDisplayID(), ".", sep="")
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

                # Check if conversion is need
                if not image.GetPixelType() == eb.PvPixelMono8:
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

                # Resize image
                if image_data.size != 0:
                    # Resize image
                    image_data = cv2.resize(
                        image_data, (800, 600), interpolation=cv2.INTER_LINEAR
                    )  # Display image
                    cv2.imshow(str(self._connection_id.GetDisplayID()), image_data)
                    cv2.waitKey(1)
                else:
                    print(
                        "camera ",
                        str(self._connection_id.GetDisplayID()),
                        " got image size = 0.",
                        sep="",
                    )
                    break

                self._pipeline.ReleaseBuffer(buffer)
            else:
                print(
                    "camera ",
                    str(self._connection_id.GetDisplayID()),
                    " failed to produce an image.",
                    sep="",
                )
                break


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
            print("Found:\t\t", lDI.GetDisplayID(), ".", sep="")
            result, device = eb.PvDevice.CreateAndConnect(lDI)
            if result.IsFailure():
                print(
                    "\t\tUnable to connect to ",
                    lDI.GetDisplayID(),
                    "\n\t\tError: ",
                    eb.PvResultCode(result.GetCode()),
                    ".",
                    sep="",
                )
            else:
                if not isinstance(device, eb.PvDeviceGEV):
                    print(
                        "\t\tThe selected device is not currently supported by this sample."
                    )
                else:
                    lDIVector.append(lDI)
                    deviceVector.append(device)
                    # print(f"added [{len(lDIVector) - 1}]\t{lDI.GetDisplayID()}")

    if len(lDIVector) == 0:
        print("No devices found, terminating Code.")
        return False

    packetDelay = utils.CalculatePacketDelay(len(lDIVector))

    print(
        "\nSuccessfully connected to ",
        "a device" if len(lDIVector) == 1 else "devices",
        ".",
        sep="",
    )
    sources = []
    for i in range(len(lDIVector)):
        cam = Camera(deviceVector[i], lDIVector[i], packetDelay)
        print("Opening:\t", lDIVector[i].GetDisplayID(), ".", sep="")
        if cam.Open():
            sources.append(cam)
    if sources == []:
        print("Couldn't open any cameras. Terminate code. ")
        return False

    software_trigger = Barrier(len(lDIVector))

    print("\nStaring Acquisition.")
    for cam in sources:
        cam.StartAcquisition()
        cam._thread = Thread(target=cam.run, args=[software_trigger])
        cam._thread.start()

    print("\n<Press a key to stop streaming>")
    kb = psu.PvKb()
    kb.start()
    while not kb.is_stopping():
        active_thread_count = 0
        for cam_thread in sources:
            if cam_thread._thread.is_alive():
                active_thread_count += 1
        if active_thread_count == 0:
            break
        if kb.kbhit():
            kb.getch()
            break

    print("Stopping Threads and ending application")
    for source in sources:
        source.StopAcquisition()
        source._thread.join()
        source.Close()

    return True


print("Multi Camera Display sample")
print("Acquire images from a GigE Vision device")
AcquireImages()
