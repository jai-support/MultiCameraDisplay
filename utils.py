import eBUS as eb
import cv2

## Calculate Packet delay:
packetSize = 9000
networkSpeed = 1


def CalculatePacketDelay(camerasConnected):
    withEthHeaders = packetSize + 14
    camerasDelayFactor = camerasConnected - 1
    transmissionTimePerPacket = withEthHeaders * 8 / networkSpeed

    minimumPacketDelay = camerasDelayFactor * transmissionTimePerPacket
    return int(minimumPacketDelay)


def ImageFormatting(image, image_data):
    match image.GetPixelType():
        case eb.PvPixelMono8:
            pass
        case eb.PvPixelBayerBG8:
            image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerBG2RGB)
        case eb.PvPixelBayerGB8:
            image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerGB2RGB)
        case eb.PvPixelBayerGR8:
            image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerGR2RGB)
        case eb.PvPixelBayerRG8:
            image_data = cv2.cvtColor(image_data, cv2.COLOR_BayerRG2RGB)
        case eb.PvPixelRGB8:
            image_data = cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR)
        case _:
            return None
    return image_data
